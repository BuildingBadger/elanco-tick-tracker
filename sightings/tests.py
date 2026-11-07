from unittest.mock import Mock, patch

import requests
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.db.models import Max, Min
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Sighting
from .services import ingest_sightings


class SampleSightingsCommandTests(TestCase):
    def test_command_loads_sample_sightings_without_duplicating_them(self):
        call_command("load_sample_sightings", verbosity=0)
        first_count = Sighting.objects.filter(source="sample").count()
        call_command("load_sample_sightings", verbosity=0)

        self.assertEqual(first_count, 100)
        self.assertEqual(Sighting.objects.filter(source="sample").count(), first_count)
        self.assertEqual(Sighting.objects.count(), first_count)
        self.assertGreater(
            Sighting.objects.aggregate(
                spread=Max("latitude") - Min("latitude")
            )["spread"],
            7,
        )
        self.assertGreater(
            Sighting.objects.aggregate(
                spread=Max("longitude") - Min("longitude")
            )["spread"],
            7,
        )
        self.assertTrue(
            Sighting.objects.filter(
                source="sample",
                description__startswith="Illustrative sample report",
            ).exists()
        )

    def test_command_can_clear_all_sightings_before_loading_samples(self):
        Sighting.objects.create(
            sighting_at="2026-10-01T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
            source="user",
        )
        Sighting.objects.create(
            sighting_at="2026-10-01T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
            source="external",
            source_id="external-example",
        )

        call_command("load_sample_sightings", clear_all=True, verbosity=0)

        self.assertEqual(Sighting.objects.count(), 100)
        self.assertEqual(
            set(Sighting.objects.values_list("source", flat=True)), {"sample"}
        )

    def test_command_adds_requested_samples_without_changing_existing_sightings(self):
        call_command("load_sample_sightings", verbosity=0)
        original_sighting = Sighting.objects.get(
            source="sample",
            source_id="sample-001",
        )
        original_coordinates = (original_sighting.latitude, original_sighting.longitude)
        user_sighting = Sighting.objects.create(
            sighting_at="2026-10-01T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
            source="user",
        )

        call_command("load_sample_sightings", additional=3, verbosity=0)

        self.assertEqual(Sighting.objects.count(), 104)
        self.assertTrue(Sighting.objects.filter(pk=user_sighting.pk).exists())
        original_sighting.refresh_from_db()
        self.assertEqual(
            (original_sighting.latitude, original_sighting.longitude),
            original_coordinates,
        )
        self.assertEqual(
            set(
                Sighting.objects.filter(source="sample").values_list(
                    "source_id", flat=True
                )
            ) & {"sample-101", "sample-102", "sample-103"},
            {"sample-101", "sample-102", "sample-103"},
        )


class SightingGuideTests(TestCase):
    def test_home_page_displays_supplied_tick_guide_images_in_order(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="themeToggle"', content)
        self.assertIn('href="#mainContent"', content)
        self.assertIn('<nav class="site-navigation" aria-label="Page sections">', content)
        self.assertIn('href="#sightingsSection">Sightings list</a>', content)
        self.assertIn("Marker key:", content)
        self.assertIn("aria-pressed", content)
        self.assertIn('id="map"', content)
        self.assertIn('id="sightingTableBody"', content)
        self.assertIn('id="speciesMonthBreakdown"', content)
        self.assertIn(".species-month-grid {", content)
        self.assertIn("grid-template-columns: repeat(12, minmax(0, 1fr));", content)
        self.assertNotIn("monthly-species-table", content)
        self.assertIn('id="totalSightingCount"', content)
        self.assertIn('id="locateCoordinates"', content)
        self.assertIn("leaflet-control-sighting-count", content)
        self.assertIn('button.dataset.location = region.location', content)
        self.assertIn('getElementById("locationFilter").value =', content)
        self.assertIn("lastGeocodeStartedAt + 1100 - Date.now()", content)
        self.assertIn("nominatim.openstreetmap.org/reverse", content)
        self.assertIn("Sighting date cannot be in the future.", content)
        self.assertEqual(content.count('aria-live="polite"'), 1)
        self.assertIn("leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js", content)
        self.assertIn("L.markerClusterGroup(", content)
        self.assertIn("map.fitBounds(markerCluster.getBounds()", content)
        self.assertIn("Cluster counts show nearby reports", content)
        self.assertIn('<details class="region-dropdown">', content)
        self.assertIn("<summary>Show sightings by region</summary>", content)
        self.assertIn('<ul id="regionList"></ul>', content)
        self.assertIn('scrollIntoView({ block: "start" })', content)
        self.assertIn("Further information can be found at", content)
        self.assertIn(
            'href="https://www.rspca.org.uk/adviceandwelfare/pets/general/ticks"',
            content,
        )
        self.assertIn("Tick treatment options", content)
        self.assertIn(
            'href="https://mypetandi.elanco.com/en_gb/our-products?issues=Ticks"',
            content,
        )
        self.assertIn("Explore Elanco tick products", content)
        names = [
            "Sheep Tick",
            "Hedgehog Tick",
            "Ornate Cow Tick",
            "Fox Tick",
            "Costal Red",
        ]
        positions = [
            content.index(f'<th scope="row">{name}</th>') for name in names
        ]
        self.assertEqual(positions, sorted(positions))
        for image in (
            "sheep-tick.png",
            "hedgehog-tick.png",
            "ornate-cow-tick.png",
            "fox-tick.png",
            "costal-red-tick.png",
        ):
            self.assertContains(response, f"/static/sightings/ticks/{image}")
            self.assertIsNotNone(finders.find(f"sightings/ticks/{image}"))


class SightingSubmissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_species_filter_only_offers_species_in_database(self):
        Sighting.objects.create(
            sighting_at="2026-04-15T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
        )
        Sighting.objects.create(
            sighting_at="2026-04-16T12:00:00Z",
            species="Dermacentor reticulatus",
            latitude=51.6,
            longitude=-0.2,
        )
        Sighting.objects.create(
            sighting_at="2026-04-17T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.7,
            longitude=-0.3,
        )
        Sighting.objects.create(
            sighting_at="2026-04-18T12:00:00Z",
            species="Ixodes hexagonus",
            latitude=51.8,
            longitude=-0.4,
        )

        response = self.client.get("/")
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        filter_options = content.split('<select id="speciesFilter">', 1)[1].split(
            "</select>", 1
        )[0]
        self.assertIn('<option value="">All species</option>', filter_options)
        self.assertIn(
            '<option value="Dermacentor reticulatus">Ornate cow tick (Dermacentor reticulatus)</option>',
            filter_options,
        )
        self.assertIn(
            '<option value="Ixodes ricinus">Sheep tick (Ixodes ricinus)</option>',
            filter_options,
        )
        self.assertIn(
            '<option value="Ixodes hexagonus">Hedgehog tick (Ixodes hexagonus)</option>',
            filter_options,
        )
        self.assertEqual(filter_options.count('value="Ixodes ricinus"'), 1)
        self.assertIn(".filter-field select {", content)
        self.assertIn("height: 44px;", content)

    def test_report_form_offers_species_choices_and_other_entry(self):
        response = self.client.get("/")
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="speciesSelect" name="species"', content)
        self.assertIn('value="Ixodes ricinus"', content)
        self.assertIn('value="Ixodes hexagonus"', content)
        self.assertIn('value="Dermacentor reticulatus"', content)
        self.assertIn('value="Fox Tick"', content)
        self.assertIn('value="Costal Red"', content)
        self.assertIn('value="other">Other</option>', content)
        self.assertIn('name="other_species"', content)
        self.assertIn(".report-panel input[hidden] {", content)
        self.assertIn("display: none;", content)
        self.assertIn(".report-panel select {", content)
        self.assertIn("height: 44px;", content)

    def test_submitted_sighting_is_returned_by_list_endpoint(self):
        response = self.client.post(
            "/api/sightings/",
            {
                "sighting_at": "2026-11-03T11:00:00Z",
                "species": "Ixodes ricinus",
                "latitude": "51.5074",
                "longitude": "-0.1278",
                "location": "London",
                "description": "Found in a garden",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        sighting_id = response.data["id"]

        list_response = self.client.get("/api/sightings/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data], [sighting_id])

    def test_custom_species_can_be_submitted(self):
        response = self.client.post(
            "/api/sightings/",
            {
                "sighting_at": "2026-11-03T11:00:00Z",
                "species": "Argas reflexus",
                "latitude": "51.5074",
                "longitude": "-0.1278",
                "location": "London",
                "description": "Unlisted species",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["species"], "Argas reflexus")

    def test_sightings_can_be_filtered_by_date_range_and_location(self):
        Sighting.objects.create(
            sighting_at="2026-04-15T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
            location="London",
        )
        Sighting.objects.create(
            sighting_at="2026-05-15T12:00:00Z",
            species="Ixodes ricinus",
            latitude=53.4,
            longitude=-2.2,
            location="Manchester",
        )

        response = self.client.get(
            "/api/sightings/",
            {"from": "2026-04-01", "to": "2026-04-30", "location": "london"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["location"], "London")

    def test_invalid_date_filter_returns_validation_error(self):
        response = self.client.get("/api/sightings/", {"from": "not-a-date"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("from", response.data)

    def test_reversed_date_range_returns_validation_error(self):
        response = self.client.get(
            "/api/sightings/", {"from": "2026-05-01", "to": "2026-04-01"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("to", response.data)

    def test_future_sighting_date_is_rejected(self):
        response = self.client.post(
            "/api/sightings/",
            {
                "sighting_at": "2099-11-03T11:00:00Z",
                "species": "Ixodes ricinus",
                "latitude": "51.5074",
                "longitude": "-0.1278",
                "location": "London",
                "description": "Future date should be rejected",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sighting_at", response.data)
        self.assertIn("future", response.data["sighting_at"][0].lower())

    def test_invalid_submission_returns_field_errors(self):
        response = self.client.post(
            "/api/sightings/",
            {
                "sighting_at": "2026-11-03T11:00:00Z",
                "species": "Ixodes ricinus",
                "latitude": "91",
                "longitude": "-0.1278",
                "location": "London",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.data)


class SightingInsightsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Sighting.objects.create(
            sighting_at="2026-04-15T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.5,
            longitude=-0.1,
            location="London",
        )
        Sighting.objects.create(
            sighting_at="2026-04-20T12:00:00Z",
            species="Ixodes ricinus",
            latitude=51.6,
            longitude=-0.2,
            location="London",
        )
        Sighting.objects.create(
            sighting_at="2026-05-15T12:00:00Z",
            species="Dermacentor reticulatus",
            latitude=53.4,
            longitude=-2.2,
            location="Manchester",
        )

    def test_insights_include_regions_monthly_trends_and_seasonality(self):
        response = self.client.get("/api/insights/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["regions"],
            [
                {"location": "London", "count": 2},
                {"location": "Manchester", "count": 1},
            ],
        )
        self.assertEqual(
            response.data["trends"],
            [
                {"period": "2026-04-01", "count": 2},
                {"period": "2026-05-01", "count": 1},
            ],
        )
        self.assertEqual(
            response.data["seasonality"],
            [{"month": 4, "count": 2}, {"month": 5, "count": 1}],
        )
        self.assertEqual(response.data["total_count"], 3)
        self.assertEqual(
            response.data["species_by_month"],
            [
                {"species": "Dermacentor reticulatus", "month": 5, "count": 1},
                {"species": "Ixodes ricinus", "month": 4, "count": 2},
            ],
        )

    def test_insights_support_weekly_trends_and_filtering(self):
        response = self.client.get(
            "/api/insights/",
            {"interval": "weekly", "location": "London", "species": "Ixodes ricinus"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [trend["count"] for trend in response.data["trends"]], [1, 1]
        )
        self.assertEqual(
            sum(trend["count"] for trend in response.data["trends"]), 2
        )
        self.assertEqual(response.data["total_count"], 2)
        self.assertEqual(
            response.data["species_by_month"],
            [{"species": "Ixodes ricinus", "month": 4, "count": 2}],
        )
        self.assertEqual(response.data["regions"], [{"location": "London", "count": 2}])

    def test_insights_reject_unsupported_interval(self):
        response = self.client.get("/api/insights/", {"interval": "daily"})

        self.assertEqual(response.status_code, 400)


class SightingIngestionTests(TestCase):
    @patch("sightings.services.requests.get")
    def test_ingestion_upserts_duplicates_and_skips_incomplete_records(self, get):
        response = Mock()
        response.json.return_value = [
            {
                "id": "external-1",
                "date": "2026-04-15T12:00:00Z",
                "latitude": 51.5,
                "longitude": -0.1,
                "location": "London",
                "species": "Older name",
            },
            {
                "id": "external-1",
                "date": "2026-04-15T12:00:00Z",
                "latitude": 51.5,
                "longitude": -0.1,
                "location": "London",
                "species": "Updated name",
            },
            {"id": "incomplete", "latitude": 91, "longitude": 0},
        ]
        get.return_value = response

        result = ingest_sightings()

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(result, {"imported": 2, "skipped": 1})
        self.assertEqual(Sighting.objects.filter(source="external").count(), 1)
        self.assertEqual(
            Sighting.objects.get(source_id="external-1").species, "Updated name"
        )

    @patch("sightings.services.requests.get")
    def test_ingestion_propagates_external_api_failures(self, get):
        get.side_effect = requests.RequestException("Source unavailable")

        with self.assertRaises(requests.RequestException):
            ingest_sightings()
