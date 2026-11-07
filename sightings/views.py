from django.db.models import Count
from django.db.models.functions import ExtractMonth, TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Sighting
from .serializers import SightingSerializer


def filtered_sightings(params):
    queryset = Sighting.objects.all()
    parsed_dates = {}

    for parameter, lookup in (("from", "gte"), ("to", "lte")):
        value = params.get(parameter)
        if value:
            parsed_date = parse_date(value)
            if parsed_date is None:
                raise ValidationError(
                    {parameter: "Enter a valid date in YYYY-MM-DD format."}
                )
            if parsed_date > timezone.now().date():
                raise ValidationError({parameter: "Date cannot be in the future."})
            parsed_dates[parameter] = parsed_date
            queryset = queryset.filter(**{f"sighting_at__date__{lookup}": parsed_date})

    if (
        "from" in parsed_dates
        and "to" in parsed_dates
        and parsed_dates["from"] > parsed_dates["to"]
    ):
        raise ValidationError({"to": "End date must be on or after start date."})

    if params.get("species"):
        queryset = queryset.filter(species__iexact=params["species"])
    if params.get("location"):
        queryset = queryset.filter(location__icontains=params["location"])

    bounds = {
        "latitude__gte": params.get("min_lat"),
        "latitude__lte": params.get("max_lat"),
        "longitude__gte": params.get("min_lng"),
        "longitude__lte": params.get("max_lng"),
    }
    return queryset.filter(**{key: value for key, value in bounds.items() if value})


class SightingListCreateView(generics.ListCreateAPIView):
    serializer_class = SightingSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return filtered_sightings(self.request.query_params)

    def perform_create(self, serializer):
        serializer.save(source="user")


class SightingInsightsView(APIView):
    def get(self, request):
        interval = request.query_params.get("interval", "monthly")
        if interval not in {"weekly", "monthly"}:
            raise ValidationError(
                {"interval": "Choose either 'weekly' or 'monthly'."}
            )

        sightings = filtered_sightings(request.query_params)
        period = (
            TruncWeek("sighting_at")
            if interval == "weekly"
            else TruncMonth("sighting_at")
        )
        trends = (
            sightings.annotate(period=period)
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )
        regions = (
            sightings.values("location")
            .annotate(count=Count("id"))
            .order_by("-count", "location")
        )
        seasonality = (
            sightings.annotate(month=ExtractMonth("sighting_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        species_by_month = (
            sightings.annotate(month=ExtractMonth("sighting_at"))
            .values("species", "month")
            .annotate(count=Count("id"))
            .order_by("species", "month")
        )

        return Response(
            {
                "total_count": sightings.count(),
                "regions": [
                    {
                        "location": item["location"] or "Unknown",
                        "count": item["count"],
                    }
                    for item in regions
                ],
                "trends": [
                    {
                        "period": item["period"].date().isoformat(),
                        "count": item["count"],
                    }
                    for item in trends
                ],
                "seasonality": [
                    {"month": item["month"], "count": item["count"]}
                    for item in seasonality
                ],
                "species_by_month": [
                    {
                        "species": item["species"] or "Unknown",
                        "month": item["month"],
                        "count": item["count"],
                    }
                    for item in species_by_month
                ],
            }
        )
