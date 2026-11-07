import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from sightings.models import Sighting


LOCATIONS = [
    ("Penzance", 50.1186, -5.5371),
    ("Truro", 50.2632, -5.0510),
    ("Plymouth", 50.3755, -4.1427),
    ("Exeter", 50.7184, -3.5339),
    ("Taunton", 51.0149, -3.1029),
    ("Bristol", 51.4545, -2.5879),
    ("Swansea", 51.6214, -3.9436),
    ("Cardiff", 51.4816, -3.1791),
    ("Aberystwyth", 52.4153, -4.0829),
    ("Llandudno", 53.3245, -3.8275),
    ("Hereford", 52.0567, -2.7160),
    ("Oxford", 51.7520, -1.2577),
    ("Southampton", 50.9097, -1.4044),
    ("Brighton", 50.8225, -0.1372),
    ("Canterbury", 51.2759, 1.0753),
    ("London", 51.5074, -0.1278),
    ("Cambridge", 52.2053, 0.1218),
    ("Norwich", 52.6309, 1.2974),
    ("Birmingham", 52.4862, -1.8904),
    ("Nottingham", 52.9548, -1.1581),
    ("Leicester", 52.6369, -1.1398),
    ("Sheffield", 53.3811, -1.4701),
    ("Leeds", 53.8008, -1.5491),
    ("Manchester", 53.4808, -2.2426),
    ("Liverpool", 53.4084, -2.9916),
    ("Chester", 53.1930, -2.8931),
    ("Lancaster", 54.0466, -2.8007),
    ("Keswick", 54.6013, -3.1347),
    ("Carlisle", 54.8951, -2.9382),
    ("Newcastle upon Tyne", 54.9783, -1.6178),
    ("Berwick-upon-Tweed", 55.7693, -2.0021),
    ("Edinburgh", 55.9533, -3.1883),
    ("Glasgow", 55.8642, -4.2518),
    ("Oban", 56.4127, -5.4706),
    ("Inverness", 57.4778, -4.2247),
    ("Aberdeen", 57.1497, -2.0943),
    ("Dundee", 56.4620, -2.9707),
    ("Belfast", 54.5973, -5.9301),
    ("Derry", 54.9966, -7.3086),
    ("Newry", 54.1751, -6.3402),
]

SPECIES = [
    "Ixodes ricinus",
    "Ixodes hexagonus",
    "Dermacentor reticulatus",
    "Unknown",
]

REPORT_CONTEXTS = [
    "from a local green space",
    "after a woodland walk",
    "near a public footpath",
    "during a routine garden check",
    "after checking a pet",
]


def build_sample_sightings(start_index=0, count=100):
    samples = []
    rng = random.Random(100)
    for index in range(start_index + count):
        location_index = rng.randrange(len(LOCATIONS))
        location, latitude, longitude = LOCATIONS[location_index]
        latitude += rng.uniform(-0.035, 0.035)
        longitude += rng.uniform(-0.05, 0.05)
        if index < start_index:
            continue
        samples.append(
            {
                "id": f"sample-{index + 1:03}",
                "days_ago": index * 3 + 1,
                "species": SPECIES[index % len(SPECIES)],
                "latitude": latitude,
                "longitude": longitude,
                "location": location,
                "description": (
                    "Illustrative sample report "
                    f"{REPORT_CONTEXTS[index % len(REPORT_CONTEXTS)]}; "
                    "species identification is unconfirmed."
                ),
            }
        )
    return samples


SAMPLE_SIGHTINGS = build_sample_sightings()


class Command(BaseCommand):
    help = "Load or refresh 100 illustrative UK tick sightings for local demonstration."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--clear-all",
            action="store_true",
            help="Delete all existing sightings before loading the sample dataset.",
        )
        group.add_argument(
            "--additional",
            type=int,
            metavar="COUNT",
            help="Add COUNT new sample sightings without changing existing records.",
        )

    def handle(self, *args, **options):
        additional = options["additional"]
        if additional is not None and additional < 1:
            raise CommandError("--additional must be a positive number.")

        if additional is None:
            samples = SAMPLE_SIGHTINGS
        else:
            existing_ids = Sighting.objects.filter(
                source="sample",
                source_id__startswith="sample-",
            ).values_list("source_id", flat=True)
            last_sample_number = max(
                (
                    int(source_id.removeprefix("sample-"))
                    for source_id in existing_ids
                    if source_id.removeprefix("sample-").isdigit()
                ),
                default=0,
            )
            samples = build_sample_sightings(last_sample_number, additional)

        now = timezone.now()
        created = 0
        updated = 0

        with transaction.atomic():
            if options["clear_all"]:
                deleted, _ = Sighting.objects.all().delete()
            elif additional is None:
                sample_ids = [sample["id"] for sample in samples]
                deleted, _ = Sighting.objects.filter(source="sample").exclude(
                    source_id__in=sample_ids
                ).delete()
            else:
                deleted = 0

            for sample in samples:
                record = sample.copy()
                source_id = record.pop("id")
                days_ago = record.pop("days_ago")
                _, was_created = Sighting.objects.update_or_create(
                    source="sample",
                    source_id=source_id,
                    defaults={
                        **record,
                        "sighting_at": now - timedelta(days=days_ago),
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        if options["clear_all"]:
            self.stdout.write(f"Deleted {deleted} existing sighting(s).")
        self.stdout.write(
            self.style.SUCCESS(
                f"Sample sightings complete: {created} created, {updated} refreshed."
            )
        )
