from django.core.management.base import BaseCommand, CommandError

from sightings.services import ingest_sightings


class Command(BaseCommand):
    help = "Import and upsert sightings from the Elanco source API."

    def handle(self, *args, **options):
        try:
            result = ingest_sightings()
        except Exception as exc:
            raise CommandError(f"Ingestion failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result['imported']} sightings; skipped {result['skipped']} invalid records."
            )
        )
