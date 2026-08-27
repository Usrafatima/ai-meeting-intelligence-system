# Module 3: Meeting & File Management

The third module in the project order (Authentication, Frontend, then this one). It owns
everything about a meeting record and its uploaded audio or video files, and it is the
module every later stage of the pipeline (Speech-to-Text, Speaker ID, AI Analysis,
Dashboard) reads from and writes back to.

It is integrated directly into the shared `backend/` FastAPI app rather than running as a
separate service, so it reuses the Authentication module's users, JWT settings and
database session.

## What this module does

- Create, update, list, search and delete meetings
- Upload audio or video files against a meeting, with type and size validation
- Store files either on local disk or in an S3-compatible bucket, chosen by an
  environment variable, so it can move to real cloud storage without code changes
- Track a meeting's processing status as it moves through the pipeline (uploaded,
  queued, processing, transcribed, analyzed, completed, failed)
- Manage participants attached to a meeting
- Expose internal, service-key-protected endpoints so the Speech-to-Text and AI Analysis
  modules can fetch a meeting's file paths and push status updates, without giving them
  direct database access

## Where the code lives

```
backend/app/
  core/config.py              storage, upload-limit and service-key settings
  db/models.py                Meeting, MeetingFile, Participant (alongside User)
  schemas/meeting.py          Pydantic request and response models
  services/storage.py         local disk and S3 storage backends
  api/routes/meetings.py      user-facing meeting and file endpoints
  api/routes/internal.py      service-to-service endpoints for the AI pipeline
  api/api.py                  router registration
```

## API endpoints

User-facing, all require an `Authorization: Bearer <jwt>` header issued by the
Authentication module:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/meetings` | Create a meeting, optionally with participants |
| GET | `/api/v1/meetings` | List meetings, with search, status filter and pagination |
| GET | `/api/v1/meetings/{id}` | Get full meeting detail, including files and participants |
| PATCH | `/api/v1/meetings/{id}` | Update title, description, date or status |
| DELETE | `/api/v1/meetings/{id}` | Delete a meeting and its stored files |
| POST | `/api/v1/meetings/{id}/files` | Upload an audio or video file |
| GET | `/api/v1/meetings/{id}/files` | List files attached to a meeting |
| DELETE | `/api/v1/meetings/{id}/files/{file_id}` | Remove a file |

Internal, require an `x-service-key` header shared with the pipeline modules:

| Method | Path | Purpose |
|---|---|---|
| PATCH | `/api/v1/internal/meetings/{id}/status` | Update processing status and duration |
| GET | `/api/v1/internal/meetings/{id}/file-paths` | Fetch stored file paths for processing |

## Data model

- **Meeting** — owned by a `User` (`owner_id` FK), carries `status`, `duration_seconds`,
  `meeting_date`, and cascades to its files and participants.
- **MeetingFile** — `file_type` (audio/video), `original_filename`, `storage_path`,
  `storage_backend`, `content_type`, `size_bytes`, `checksum_sha256`.
- **Participant** — `name`, `email`, and a `speaker_label` left empty for the Speaker ID
  module to fill in.

## Configuration

Added to `backend/.env` (see `backend/.env.example`):

```
STORAGE_BACKEND=local          # or "s3"
LOCAL_UPLOAD_DIR=./uploads
STORAGE_BUCKET=
STORAGE_REGION=
STORAGE_ENDPOINT=              # set for MinIO or another S3-compatible host
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=
MAX_UPLOAD_SIZE_MB=1024
PIPELINE_SERVICE_KEY=replace-with-internal-service-key
```

## Running it

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # then fill in DATABASE_URL, SECRET_KEY, PIPELINE_SERVICE_KEY
uvicorn app.main:app --reload
```

Interactive API docs are then at `http://localhost:8000/docs`.

## Notes for the team

- Auth is the Authentication module's: these routes depend on `deps.get_current_active_user`,
  so a user only ever sees their own meetings.
- Switch to cloud storage by setting `STORAGE_BACKEND=s3` and filling in the storage
  variables. No other code changes are needed — the API talks to a storage interface.
- The `status` field on a meeting is the source of truth the dashboard should poll for
  processing progress.
- `duration_seconds` starts empty and is expected to be filled in by the Speech-to-Text
  module through the internal status endpoint.
- Uploads written by the local backend land in `backend/uploads/` and are gitignored.
