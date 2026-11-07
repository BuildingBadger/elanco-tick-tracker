import logging
from datetime import datetime

import requests
from django.conf import settings
from django.db import transaction

from .models import Sighting

logger = logging.getLogger(__name__)


def _first(record, *keys):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalise(record):
    source_id = _first(record, "id", "_id", "uuid")
    sighting_at = _parse_datetime(_first(record, "date", "sightingAt", "sighting_at"))
    latitude = _first(record, "latitude", "lat")
    longitude = _first(record, "longitude", "lng", "lon")

    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None

    if not source_id or not sighting_at or not (-90 <= latitude <= 90):
        return None
    if not -180 <= longitude <= 180:
        return None

    return {
        "source": "external",
        "source_id": str(source_id),
        "sighting_at": sighting_at,
        "species": str(_first(record, "species", "commonName", "name") or "").strip(),
        "latitude": latitude,
        "longitude": longitude,
        "location": str(_first(record, "location", "region", "county") or "").strip(),
        "description": str(_first(record, "description", "notes") or "").strip(),
    }


def ingest_sightings():
    url = settings.ELANCO_SOURCE_URL
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    payload = response.json()
    records = payload if isinstance(payload, list) else payload.get("data", payload.get("results", []))

    imported, skipped = 0, 0
    with transaction.atomic():
        for raw_record in records:
            record = _normalise(raw_record)
            if not record:
                skipped += 1
                continue
            source_id = record.pop("source_id")
            Sighting.objects.update_or_create(
                source="external",
                source_id=source_id,
                defaults=record,
            )
            imported += 1

    return {"imported": imported, "skipped": skipped}
