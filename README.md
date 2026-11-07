# UK Tick Tracker

> **Benjamin Jordan**

## AI use disclosure

AI assistance was used during development to help with code, prepare this
project’s README and walkthrough materials, and suggest wording for the Lyme
disease information in the educational section. The project author is
responsible for reviewing the application, its documentation, and all
submitted content for accuracy.

UK Tick Tracker is a full-stack web application MVP for exploring and reporting
community tick sightings across the UK. Users can view reports on an interactive
map, filter them by date, species, and location, explore aggregate activity
insights, and submit a sighting with an optional image.

Sightings are community reports. They are not verified identifications,
diagnoses, or a clinical assessment of disease risk.

## Features

### Explore sightings

- Leaflet map centered on the UK, with clustered sighting markers.
- Marker styling distinguishes recent reports (within 30 days) from older
  reports.
- Marker popups show sighting details, an optional image, a directions link, and
  a share action.
- Search and filter by location, species, and date range. The map, sighting
  list, and insights use the active filters.
- Shareable map links can reopen a sighting location.
- Light and dark themes, keyboard focus styling, a skip link, and accessible
  labels/status messages.

### Report a sighting

- Submit a date and time, species, coordinates, location, and optional
  description and image.
- Choose coordinates by clicking the map or dragging the report marker, or
  enter them directly.
- Reverse-geocode coordinates to a place name using OpenStreetMap Nominatim.
- The form and API validate dates, coordinate ranges, and report content, and
  display submission or error feedback.

### Insights and education

- Aggregate total sightings, monthly seasonality, species counts by month,
  trends, and sightings by region.
- Expandable tick photo guide with five supplied example images.
- Tick bite prevention and removal advice, Lyme disease guidance, and links to
  the RSPCA and Elanco.

## Technology choices

- **Python and Django** provide the application, page rendering, data model,
  and management commands.
- **Django REST Framework** provides the JSON and multipart API.
- **SQLite** is the default local database to keep the MVP simple to run.
- **Leaflet and Leaflet.markercluster** provide the interactive map and marker
  clustering. They are loaded from a CDN.
- **OpenStreetMap** provides map tiles and Nominatim reverse geocoding.
- The frontend is a Django template with CSS and JavaScript; no separate
  frontend build step is required.

## Requirements

- Python 3.10 or later (Django 5.2 requires Python 3.10+).
- pip.
- Network access for the external sightings source, map tiles, Leaflet CDN, and
  Nominatim features.

## Run locally

From the project root:

1. Create and activate a virtual environment:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, activate it with:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```sh
   python -m pip install -r requirements.txt
   ```

3. Apply database migrations:

   ```sh
   python manage.py migrate
   ```

4. (Optional) Load illustrative local reports for a populated demo:

   ```sh
   python manage.py load_sample_sightings
   ```

5. Start the development server:

   ```sh
   python manage.py runserver
   ```

6. Open <http://127.0.0.1:8000/>.

The sample loader creates 100 clearly labeled illustrative reports distributed
across the UK. Running it again refreshes its own sample records without
duplicating them or changing user-submitted and externally imported reports.
To add more sample records without changing existing records:

```sh
python manage.py load_sample_sightings --additional 50
```

The `--clear-all` option deletes **all** existing sightings, including user and
external records, before loading the sample set:

```sh
python manage.py load_sample_sightings --clear-all
```

## External data ingestion

The ingestion command retrieves data from the Elanco task endpoint configured
as `ELANCO_SOURCE_URL` in `config/settings.py`:

```sh
python manage.py ingest_sightings
```

The importer accepts a top-level list or a `data`/`results` list in the
response. It normalizes supported alternative field names, parses dates and
coordinates, checks for required IDs and valid coordinate ranges, and skips
incomplete or invalid records. Valid records are upserted using the external
source ID, so a later import updates an existing external report rather than
creating a duplicate. The operation runs in a database transaction, and the
command reports imported and skipped record counts.

HTTP errors, invalid response JSON, and other import failures are reported by
the management command as a failed ingestion rather than being presented as a
successful import.

### Data-volume and ingestion considerations

The current importer requests and processes one complete API response in a
single run. It does not yet follow pagination or process bounded batches. If the
source becomes large or paginated, the importer should be extended to follow
the source's documented pagination mechanism, fetch bounded pages, and
bulk-upsert records while preserving validation and source-ID uniqueness.

The local database includes indexes for sighting date, species, and coordinates,
and a conditional uniqueness constraint for non-null `(source, source_id)`
pairs. These support common queries and prevent duplicate identified source
records. The app does not currently implement a background job queue,
incremental synchronization, or configurable retention policy.

## API

API routes are mounted under `/api/`.

### `GET /api/sightings/`

Returns sighting records ordered by sighting date, newest first.

Optional query parameters:

| Parameter | Meaning |
| --- | --- |
| `from` | Inclusive start date in `YYYY-MM-DD` format |
| `to` | Inclusive end date in `YYYY-MM-DD` format |
| `location` | Case-insensitive partial match on location |
| `species` | Case-insensitive exact species match |
| `min_lat`, `max_lat` | Optional latitude bounds |
| `min_lng`, `max_lng` | Optional longitude bounds |

Example:

```text
/api/sightings/?from=2026-01-01&to=2026-06-30&location=London&species=Ixodes%20ricinus
```

### `POST /api/sightings/`

Creates a user-submitted sighting. Send JSON or multipart form data; use
`multipart/form-data` when attaching an image.

Fields include `sighting_at`, `species`, `latitude`, `longitude`, `location`,
`description`, and optional `image`. The API rejects future sighting dates,
coordinates outside latitude `-90..90` or longitude `-180..180`, and reports
that provide neither species nor description. The source is set by the server
for user submissions.

### `GET /api/insights/`

Returns a JSON object with:

- `total_count`: total sightings matching the filters.
- `regions`: sighting counts grouped by location.
- `trends`: counts per week or month.
- `seasonality`: counts by calendar month.
- `species_by_month`: counts by species and calendar month.

It accepts the same date, location, species, and coordinate-bound filters as
the sightings endpoint, plus `interval=weekly` or `interval=monthly` for the
trend series (monthly by default). Invalid dates, reversed date ranges, future
dates, and unsupported intervals return validation errors.

## Architecture

```text
Browser
  ├── Django-rendered page: sightings/templates/sightings/home.html
  │     ├── Leaflet map and filters
  │     ├── report form and insights UI
  │     └── fetch requests to the API
  └── Django REST Framework endpoints
        ├── sightings/views.py: filtering, create/list, aggregations
        ├── sightings/serializers.py: API input/output and validation
        ├── sightings/models.py: persisted sighting data and constraints
        └── sightings/services.py: external data normalization and ingestion
```

Key files:

| File | Responsibility |
| --- | --- |
| `config/urls.py` | Homepage, admin, API mounting, and local static/media serving |
| `config/settings.py` | Django configuration, SQLite, media, and source URL |
| `sightings/models.py` | Sighting fields, ordering, indexes, uniqueness, model validation |
| `sightings/serializers.py` | API serialization, coordinate/date/content validation |
| `sightings/views.py` | Filtered list/create API and aggregate insights |
| `sightings/services.py` | External source parsing, validation, and upsert |
| `sightings/pages.py` | Homepage view and species filter choices |
| `sightings/templates/sightings/home.html` | User interface, map, forms, styles, and client-side behavior |
| `sightings/management/commands/` | External ingestion and illustrative sample-data commands |
| `sightings/tests.py` | Django tests for pages, API, validation, and management commands |

## Requirement coverage

The task brief asks for at least two frontend requirements from each feature
area. The implementation covers these areas as follows:

| Brief area | Implemented examples |
| --- | --- |
| Interactive map visualization | UK map; recent/older marker styling; clustering; species/date/location filters |
| Sighting information | Detailed marker popups; timeline trends; directions and share actions |
| Educational content | Tick identification photo guide; bite-prevention advice; seasonal activity chart |
| Report a sighting | User report form; field and API validation with status feedback; image upload |

Backend coverage includes external API ingestion and normalization, a
list/create endpoint, server-side filtering, aggregate insights, and validation
and error reporting for invalid submissions or source failures.

## Tests and checks

Run the app tests and Django system check:

```sh
python manage.py test sightings
python manage.py check
```

## Limitations and production considerations

- This is an MVP intended for local demonstration, not a production deployment.
- The default SQLite setup is suitable for local development; evaluate a
  production database and operational backup strategy before deployment.
- Uploaded images are served from the local media directory only while
  `DEBUG` is enabled. Use managed media/object storage in production.
- Before deploying, configure a production secret key, set `DEBUG=False`,
  configure `ALLOWED_HOSTS`, and review Django's deployment checklist.
- Leaflet assets, map tiles, and reverse geocoding rely on external services.
  Nominatim use is rate-limited in the browser implementation; production use
  should follow the provider's current usage policy.
- The current external importer handles one response rather than paginated,
  bounded batches.
- Sightings are unverified community submissions. Tick identification and
  health guidance in the application are informational and are not a substitute
  for advice from a healthcare or veterinary professional.

## Walkthrough video

[Watch the project walkthrough on YouTube](https://www.youtube.com/watch?v=Jj06l1mnXds).
