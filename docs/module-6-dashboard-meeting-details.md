# Module 6 — Dashboard & Meeting Details

Backend for the two screens the brief specifies: the **Dashboard** and the
**Meeting Details** page.

This module owns the data and the API. The screens themselves are built by
Module 2 (Frontend UI / Design System) and wired up by Module 8 (Integration).
This document is the contract between them: every endpoint below is implemented,
tested and ready to consume.

---

## Why this module has a database layer

Module 5 analyses a transcript and returns structured results, but stores
nothing — its route takes a transcript in the request body and hands the analysis
straight back.

That is workable for a one-off analysis. It cannot support a dashboard. The brief
asks the dashboard to show *number of action items*, *pending decisions* and
*upcoming deadlines*, which are aggregates across **every meeting a user owns**.
Recomputing those on each page load would mean one model call per meeting, per
refresh — slow, billable, and returning different numbers each time.

So Module 6 stores the analysis. Module 5's code is imported and called, never
edited.

Two columns exist here that Module 5 does not produce:

| Column | Values | Why |
|---|---|---|
| `action_items.status` | `open` / `done` | "Outstanding action items" needs a notion of done |
| `decisions.status` | `pending` / `confirmed` | The brief asks for *pending* decisions specifically |

Both default to the not-yet-actioned value.

---

## Database

Five tables, all cascading from `meetings`.

```
meetings (module 3)
   |
   +-- meeting_insights      1:1   summaries, key points, sentiment, provenance
   +-- action_items          1:N   task, owner, deadline, status, source timestamp
   +-- decisions             1:N   decision, timestamp, status
   +-- deadlines             1:N   flattened dates, pointing back at their origin
   +-- unresolved_issues     1:N   open questions
```

**Indexes.** `meeting_id` on every table; `deadlines.due_date` and
`action_items.deadline_date` for date-range scans; composite
`(meeting_id, status)` on `action_items` and `decisions`, which is the exact
shape of the dashboard's count queries.

**Why `deadlines` is separate from `action_items`.** An action item already has a
deadline, but the dashboard needs *"what is due across all my meetings, soonest
first"*. Reading that from `action_items` alone would miss dates attached to
decisions and dates mentioned with no owner. Every deadline is therefore also
recorded in `deadlines` with `source` and `action_item_id` pointing back at where
it came from.

---

## Deadline resolution

Module 5 is instructed to resolve a spoken phrase to a date only when confident,
and to leave it `null` otherwise. Correct for the model — but an unresolved
deadline can never appear under "Upcoming deadlines".

`app/services/insight_parsing.py` resolves the phrase deterministically, offline,
against **the meeting's own date** (not today, so reprocessing an old recording
still yields the dates its participants meant).

| Phrase | Resolves to |
|---|---|
| `tomorrow` | anchor + 1 day |
| `Friday`, `by Wednesday` | next occurrence of that weekday |
| `next Monday` | the following week's Monday |
| `September 10`, `Sept 10`, `the 15th of October` | that calendar date, rolling to next year if already past |
| `end of this month` / `end of next month` | last day of that month |
| `end of this week` | that week's Friday |
| `in 3 days`, `in 2 weeks` | counted from the anchor |
| `2026-12-01` | parsed as-is |
| `soon`, `when we get to it` | `null` — no date is expressible |

All five examples named in the brief are covered and asserted in
`tests/test_insight_parsing.py`.

---

## Timestamps and seeking

The brief requires that clicking a timestamp jumps to that point in the
recording. That is not a front-end trick — a browser will only seek an
`<audio>`/`<video>` element whose source honours **HTTP range requests**.

`GET /meetings/{id}/media` answers `206 Partial Content` with a `Content-Range`
header for range requests, `200` with `Accept-Ranges: bytes` otherwise, and `416`
for an unsatisfiable range. An unparseable `Range` header is ignored and the
whole file served, per RFC 9110.

S3-backed recordings redirect (307) to a presigned URL instead, so the object
store serves the bytes rather than proxying them through the API.

Every timestamp in the API is returned twice — `*_seconds` as a number for
seeking, `*_label` as `"32:45"` for display — so consumers never format it
themselves and never disagree.

---

## Endpoints

Base path: `/api/v1`. All endpoints require `Authorization: Bearer <token>` and
verify the meeting belongs to the caller (`404` unknown, `403` someone else's).

### Meeting Details

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/meetings/{id}/overview` | Overview tab: summary, participants, speakers, duration, date, sentiment, counts, media URL |
| `GET` | `/meetings/{id}/transcript` | Transcript tab: speaker-labelled, paginated, searchable |
| `GET` | `/meetings/{id}/insights` | AI Insights tab: key points, decisions, action items, deadlines, unresolved issues |
| `POST` | `/meetings/{id}/insights/generate` | Run the analysis and store it |
| `PATCH` | `/meetings/{id}/action-items/{item_id}` | Set `open` / `done` |
| `PATCH` | `/meetings/{id}/decisions/{decision_id}` | Set `pending` / `confirmed` |
| `GET` | `/meetings/{id}/media` | Range-aware recording stream |

### Dashboard

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/dashboard/stats` | All headline numbers in one call |
| `GET` | `/dashboard/recent-meetings` | Recent meetings, counts already resolved |
| `GET` | `/dashboard/upcoming-deadlines` | Deadlines across all meetings, soonest first |
| `GET` | `/dashboard/pending-decisions` | Decisions awaiting confirmation |
| `GET` | `/dashboard/search` | Search meetings, transcripts, action items and decisions |

Interactive documentation with full schemas is at **`/docs`** once the API is
running.

---

## Notes for whoever builds the UI

**One request per panel.** `/dashboard/stats` returns every headline number
together, and `/dashboard/recent-meetings` already includes each meeting's action
item count, pending decision count, next deadline and short summary. There is no
need to fetch a list and then call per-meeting endpoints — that N+1 pattern is
what these shapes exist to avoid.

**Search returns moments, not just meetings.** A transcript hit carries
`meeting_id`, `start_time`, `start_label` and `segment_index`. A result can link
straight into the recording at the point the words were spoken:

```
GET /dashboard/search?q=marketing budget

  transcript[0] = {
    meeting_id:    "bb192fee-…",
    start_time:    126.0,
    start_label:   "2:06",
    segment_index: 10,
    snippet:       "…the marketing budget is finalised at thirty thousand…"
  }
```

Use `types=transcript,decisions` to restrict which groups are searched.

**Empty states are 200, not 404.** `/meetings/{id}/insights` on an unanalysed
meeting returns `200` with `available: false` and empty collections. Render an
empty state; do not treat it as an error. Same for a transcript that does not
exist yet — `total_segments: 0`.

**Playing the recording.** Use `overview.media.stream_url` as the `src`. Because
the endpoint advertises `Accept-Ranges: bytes`, setting `audio.currentTime` will
seek correctly. Note the URL requires the `Authorization` header, so a bare
`<audio src>` will not authenticate — fetch it as a blob, or have Module 8 add a
short-lived signed URL if direct element loading is needed.

**Statuses worth surfacing.** `stats.awaiting_analysis` counts meetings that have
a transcript but no insights — a natural prompt to offer a "Generate insights"
button. `action_items.overdue` counts open items whose date has passed.

---

## Running it

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env            # then set DATABASE_URL and SECRET_KEY
uvicorn app.main:app --reload
```

### Demo data

To review this module without recording a meeting or configuring an API key:

```bash
python scripts/seed_demo.py
```

Creates `demo@example.com` / `demo1234` with four meetings covering every state
the UI has to render:

| Meeting | State it exercises |
|---|---|
| Q3 Product Launch Planning | Fully populated, with a playable recording |
| Weekly Engineering Sync | Populated, no recording |
| Client Call — Acme Corp | Transcript stored, never analysed (`available: false`) |
| Design Review: Onboarding Flow | Still processing, nothing stored |

The script writes through the real persistence path rather than inserting rows,
so deadline resolution, owner matching and timestamp location all run for real —
it doubles as an end-to-end check that needs no model access.

### Tests

```bash
python -m pytest tests/test_insight_parsing.py tests/test_meeting_details.py tests/test_dashboard.py -v
```

170 tests covering parsing, all endpoints, range streaming, validation,
authorisation and cross-user isolation.

---

## Environment notes

Two issues in the shared setup, neither introduced by this module, both worth
knowing before QA:

**1. `passlib` + `bcrypt 5.x` are incompatible.** `requirements.txt` pins neither,
so a fresh install pulls bcrypt 5 and *every login raises*
`ValueError: password cannot be longer than 72 bytes`. Fix:

```bash
pip install "bcrypt<5"
```

Worth pinning in `requirements.txt` — it affects Module 1's auth and therefore
every authenticated endpoint in the project.

**2. Four tests in `tests/test_stt.py` fail, and did so before this module
existed.** Two need `google-generativeai` installed, one needs `pytest-asyncio`,
and `test_service_key_verification` fails only in a full-suite run because
`test_meeting_intelligence.py` imports settings before `test_stt.py` sets its
environment variable. Reproduce without any Module 6 file collected:

```bash
python -m pytest tests/test_meeting_intelligence.py tests/test_stt.py
```

Module 6's test fixtures deliberately assign no environment variable this module
does not need, so they cannot make this ordering problem worse.
