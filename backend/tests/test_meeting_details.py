"""
Module 6 - Dashboard & Meeting Details
API tests for the meeting details page.

Run with:  python -m pytest tests/test_meeting_details.py -v

Covers the three tabs this module serves (Overview, Transcript, AI Insights),
the status updates behind them, and the range-aware media endpoint that makes
timestamp seeking possible. Authorisation is asserted on every surface, because
each one exposes meeting content.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.models import MeetingStatus  # noqa: E402
from app.db.models_insights import ActionItem, ActionItemStatus, Decision  # noqa: E402

from tests.module6_fixtures import (  # noqa: E402,F401
    SAMPLE_ANALYSIS,
    add_insights,
    add_recording,
    add_transcript,
    client,
    db_session,
    headers,
    make_meeting,
    other_headers,
    other_user,
    user,
)


@pytest.fixture
def meeting(db_session, user):
    """A completed meeting with transcript and insights stored."""
    record = make_meeting(db_session, user)
    add_transcript(db_session, record)
    add_insights(db_session, record)
    return record


@pytest.fixture
def bare_meeting(db_session, user):
    """A meeting still processing: no transcript, no insights, no recording."""
    return make_meeting(
        db_session,
        user,
        title="Design Review",
        status=MeetingStatus.PROCESSING,
        duration=None,
        participants=(),
    )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class TestOverview:
    def test_returns_the_meeting_header(self, client, headers, meeting):
        response = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers)
        assert response.status_code == 200

        body = response.json()
        assert body["id"] == meeting.id
        assert body["title"] == "Q3 Product Launch Planning"
        assert body["status"] == "completed"
        assert body["duration_seconds"] == 110
        assert body["duration_label"] == "1m 50s"
        assert body["has_transcript"] is True
        assert body["has_insights"] is True

    def test_includes_the_summary_and_sentiment(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()
        assert body["summary_short"] == SAMPLE_ANALYSIS["summary_short"]
        assert body["summary_detailed"] == SAMPLE_ANALYSIS["summary_detailed"]
        assert body["sentiment"] == "positive"

    def test_lists_participants(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()
        names = {p["name"] for p in body["participants"]}
        assert names == {"Sara Khan", "Ali Raza", "Hina Malik"}

    def test_derives_speakers_and_maps_them_to_participants(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()
        speakers = {s["label"]: s for s in body["speakers"]}

        assert set(speakers) == {"Speaker 1", "Speaker 2", "Speaker 3"}
        assert speakers["Speaker 1"]["participant_name"] == "Sara Khan"
        assert speakers["Speaker 2"]["participant_name"] == "Ali Raza"

        # Speaker 1 has four lines in the sample transcript.
        assert speakers["Speaker 1"]["segment_count"] == 4
        assert speakers["Speaker 1"]["first_appearance"] == 0.0
        assert speakers["Speaker 1"]["speaking_seconds"] > 0

    def test_speakers_are_ordered_by_first_appearance(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()
        firsts = [s["first_appearance"] for s in body["speakers"]]
        assert firsts == sorted(firsts)

    def test_reports_counts_for_the_tab_badges(self, client, headers, meeting):
        counts = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()["counts"]
        assert counts["action_items_total"] == 3
        assert counts["action_items_open"] == 3
        assert counts["decisions_total"] == 2
        assert counts["decisions_pending"] == 2
        assert counts["unresolved_issues"] == 1
        assert counts["participants"] == 3
        assert counts["transcript_segments"] == 8
        assert counts["key_points"] == 3

    def test_media_is_null_when_no_recording_is_attached(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()
        assert body["media"] is None

    def test_media_carries_a_stream_url_when_a_recording_exists(
        self, client, headers, db_session, meeting, tmp_path
    ):
        add_recording(db_session, meeting, tmp_path)
        body = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()

        assert body["media"]["filename"] == "recording.wav"
        assert body["media"]["file_type"] == "audio"
        assert body["media"]["stream_url"].endswith(f"/meetings/{meeting.id}/media")

    def test_renders_for_a_meeting_with_nothing_stored_yet(self, client, headers, bare_meeting):
        body = client.get(f"/api/v1/meetings/{bare_meeting.id}/overview", headers=headers).json()
        assert body["has_transcript"] is False
        assert body["has_insights"] is False
        assert body["summary_short"] is None
        assert body["duration_label"] is None
        assert body["speakers"] == []
        assert body["counts"]["action_items_total"] == 0


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


class TestTranscript:
    def test_returns_segments_in_time_order(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/transcript", headers=headers).json()

        assert body["total_segments"] == 8
        assert len(body["segments"]) == 8
        starts = [s["start_time"] for s in body["segments"]]
        assert starts == sorted(starts)

    def test_each_segment_carries_speaker_and_display_timestamp(self, client, headers, meeting):
        segments = client.get(f"/api/v1/meetings/{meeting.id}/transcript", headers=headers).json()["segments"]

        first = segments[0]
        assert first["index"] == 0
        assert first["start_label"] == "0:00"
        assert first["speaker"] == "Speaker 1"
        assert first["speaker_name"] == "Sara Khan"
        assert "launch date" in first["text"]

        assert segments[5]["start_label"] == "1:08"

    def test_reports_transcript_metadata(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/transcript", headers=headers).json()
        assert body["language"] == "en"
        assert body["transcriber_model"] == "whisper-base"
        assert body["overall_confidence"] == pytest.approx(0.92)

    def test_search_returns_only_matching_segments(self, client, headers, meeting):
        body = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"q": "marketing budget"}, headers=headers
        ).json()

        assert body["query"] == "marketing budget"
        assert body["match_count"] == 1
        assert len(body["segments"]) == 1
        assert "marketing budget" in body["segments"][0]["text"].lower()

    def test_search_keeps_the_true_position_in_the_transcript(self, client, headers, meeting):
        """A hit must know where it sits in the full recording, not in the result list."""
        body = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"q": "marketing budget"}, headers=headers
        ).json()

        assert body["segments"][0]["index"] == 6
        assert body["segments"][0]["start_time"] == 82.0

    def test_search_is_case_insensitive(self, client, headers, meeting):
        lower = client.get(f"/api/v1/meetings/{meeting.id}/transcript", params={"q": "friday"}, headers=headers)
        upper = client.get(f"/api/v1/meetings/{meeting.id}/transcript", params={"q": "FRIDAY"}, headers=headers)
        assert lower.json()["match_count"] == upper.json()["match_count"] >= 1

    def test_search_with_no_hits_returns_an_empty_result_not_an_error(self, client, headers, meeting):
        body = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"q": "zeppelin"}, headers=headers
        ).json()
        assert body["match_count"] == 0
        assert body["segments"] == []

    def test_match_count_is_absent_when_not_searching(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/transcript", headers=headers).json()
        assert body["match_count"] is None

    def test_pagination_windows_the_segments(self, client, headers, meeting):
        first = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"page": 1, "page_size": 3}, headers=headers
        ).json()
        second = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"page": 2, "page_size": 3}, headers=headers
        ).json()

        assert len(first["segments"]) == 3
        assert len(second["segments"]) == 3
        assert first["total_segments"] == second["total_segments"] == 8
        assert [s["index"] for s in first["segments"]] == [0, 1, 2]
        assert [s["index"] for s in second["segments"]] == [3, 4, 5]

    def test_page_beyond_the_end_is_empty_rather_than_an_error(self, client, headers, meeting):
        body = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"page": 99, "page_size": 50}, headers=headers
        ).json()
        assert body["segments"] == []
        assert body["total_segments"] == 8

    def test_meeting_without_a_transcript_returns_an_empty_payload(self, client, headers, bare_meeting):
        response = client.get(f"/api/v1/meetings/{bare_meeting.id}/transcript", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_segments"] == 0
        assert response.json()["segments"] == []

    @pytest.mark.parametrize("page_size", [0, 501])
    def test_rejects_an_out_of_range_page_size(self, client, headers, meeting, page_size):
        response = client.get(
            f"/api/v1/meetings/{meeting.id}/transcript", params={"page_size": page_size}, headers=headers
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# AI Insights
# ---------------------------------------------------------------------------


class TestInsights:
    def test_returns_the_stored_analysis(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()

        assert body["available"] is True
        assert body["model_name"] == "test-model"
        assert body["sentiment"] == "positive"
        assert len(body["key_points"]) == 3
        assert len(body["follow_up_items"]) == 1

    def test_decisions_carry_a_seekable_timestamp(self, client, headers, meeting):
        decisions = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["decisions"]

        launch = next(d for d in decisions if "September 1" in d["decision"])
        assert launch["timestamp_label"] == "1:08"
        assert launch["timestamp_seconds"] == 68.0
        assert launch["status"] == "pending"

    def test_action_items_resolve_owners_to_participants(self, client, headers, meeting):
        items = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["action_items"]

        backend = next(i for i in items if "backend" in i["task"].lower())
        assert backend["owner_name"] == "Ali"
        assert backend["participant_name"] == "Ali Raza"
        assert backend["participant_id"] is not None

    def test_spoken_deadlines_are_resolved_to_calendar_dates(self, client, headers, meeting):
        items = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["action_items"]

        backend = next(i for i in items if "backend" in i["task"].lower())
        assert backend["deadline_raw"] == "Friday"
        assert backend["deadline_date"] is not None, "an unresolved deadline cannot appear on the dashboard"
        assert date.fromisoformat(backend["deadline_date"]).weekday() == 4

    def test_action_items_are_located_in_the_recording(self, client, headers, meeting):
        items = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["action_items"]
        backend = next(i for i in items if "backend" in i["task"].lower())

        assert backend["source_timestamp"] is not None
        assert backend["source_timestamp_label"] is not None

    def test_deadlines_are_flattened_for_the_dashboard(self, client, headers, meeting):
        body = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()

        assert len(body["deadlines"]) == 3
        assert all(d["source"] == "action_item" for d in body["deadlines"])
        assert all(d["action_item_id"] for d in body["deadlines"])

    def test_deadlines_are_sorted_soonest_first(self, client, headers, meeting):
        deadlines = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["deadlines"]
        dates = [d["due_date"] for d in deadlines if d["due_date"]]
        assert dates == sorted(dates)

    def test_unresolved_issues_are_returned(self, client, headers, meeting):
        issues = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()["unresolved_issues"]
        assert len(issues) == 1
        assert "mobile app" in issues[0]["issue"]
        assert issues[0]["raised_by"] == "Hina"

    def test_unanalysed_meeting_returns_an_empty_payload_not_a_404(self, client, headers, db_session, user):
        """The tab exists whether or not an analysis has run; empty is not an error."""
        record = make_meeting(db_session, user, title="Not analysed yet")
        add_transcript(db_session, record)

        response = client.get(f"/api/v1/meetings/{record.id}/insights", headers=headers)
        assert response.status_code == 200

        body = response.json()
        assert body["available"] is False
        assert body["action_items"] == []
        assert body["decisions"] == []
        assert body["summary_short"] is None


# ---------------------------------------------------------------------------
# Status updates
# ---------------------------------------------------------------------------


class TestStatusUpdates:
    def test_an_action_item_can_be_ticked_off(self, client, headers, meeting, db_session):
        item = db_session.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).first()

        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/{item.id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "done"

        counts = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()["counts"]
        assert counts["action_items_open"] == 2
        assert counts["action_items_total"] == 3

    def test_a_decision_can_be_confirmed(self, client, headers, meeting, db_session):
        decision = db_session.query(Decision).filter(Decision.meeting_id == meeting.id).first()

        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/decisions/{decision.id}", json={"status": "confirmed"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

        counts = client.get(f"/api/v1/meetings/{meeting.id}/overview", headers=headers).json()["counts"]
        assert counts["decisions_pending"] == 1

    @pytest.mark.parametrize("bad_status", ["completed", "", "DONE ", "cancelled"])
    def test_rejects_an_unknown_action_item_status(self, client, headers, meeting, db_session, bad_status):
        item = db_session.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).first()
        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/{item.id}", json={"status": bad_status}, headers=headers
        )
        assert response.status_code == 422

    def test_unknown_action_item_id_is_a_404(self, client, headers, meeting):
        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/does-not-exist", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 404

    def test_an_item_from_another_meeting_cannot_be_updated_through_this_one(
        self, client, headers, meeting, db_session, user
    ):
        """The item id must belong to the meeting in the path, not just exist."""
        other = make_meeting(db_session, user, title="A different meeting")
        add_transcript(db_session, other)
        add_insights(db_session, other)
        foreign_item = db_session.query(ActionItem).filter(ActionItem.meeting_id == other.id).first()

        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/{foreign_item.id}",
            json={"status": "done"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_reanalysis_preserves_a_status_the_user_already_set(self, client, headers, meeting, db_session):
        """
        Re-running the analysis rebuilds these rows. A task the user ticked off
        must not quietly return to open, which would read as data loss.
        """
        item = db_session.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).first()
        client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/{item.id}", json={"status": "done"}, headers=headers
        )

        db_session.expire_all()
        add_insights(db_session, meeting)  # same analysis, run again

        done = (
            db_session.query(ActionItem)
            .filter(ActionItem.meeting_id == meeting.id, ActionItem.status == ActionItemStatus.DONE)
            .count()
        )
        assert done == 1

    def test_regenerating_does_not_duplicate_rows(self, client, headers, meeting, db_session):
        add_insights(db_session, meeting)
        add_insights(db_session, meeting)

        body = client.get(f"/api/v1/meetings/{meeting.id}/insights", headers=headers).json()
        assert len(body["action_items"]) == 3
        assert len(body["decisions"]) == 2
        assert len(body["deadlines"]) == 3


class TestGenerateInsights:
    def test_generating_without_a_transcript_is_a_409(self, client, headers, bare_meeting):
        response = client.post(
            f"/api/v1/meetings/{bare_meeting.id}/insights/generate",
            json={"summary_mode": "short"},
            headers=headers,
        )
        assert response.status_code == 409
        assert "transcript" in response.json()["detail"].lower()

    def test_rejects_an_invalid_summary_mode(self, client, headers, meeting):
        response = client.post(
            f"/api/v1/meetings/{meeting.id}/insights/generate", json={"summary_mode": "medium"}, headers=headers
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Media streaming
# ---------------------------------------------------------------------------


class TestMediaStreaming:
    @pytest.fixture(autouse=True)
    def local_storage(self, tmp_path, monkeypatch):
        """Point the storage layer at a temp directory for these tests."""
        monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
        self.upload_dir = tmp_path
        return tmp_path

    def test_serves_the_whole_file_without_a_range_header(self, client, headers, db_session, meeting):
        record = add_recording(db_session, meeting, self.upload_dir)

        response = client.get(f"/api/v1/meetings/{meeting.id}/media", headers=headers)
        assert response.status_code == 200
        assert response.headers["accept-ranges"] == "bytes"
        assert int(response.headers["content-length"]) == record.size_bytes
        assert len(response.content) == record.size_bytes

    def test_advertises_the_content_type_from_the_upload(self, client, headers, db_session, meeting):
        add_recording(db_session, meeting, self.upload_dir)
        response = client.get(f"/api/v1/meetings/{meeting.id}/media", headers=headers)
        assert response.headers["content-type"].startswith("audio/")

    def test_a_range_request_gets_partial_content(self, client, headers, db_session, meeting):
        record = add_recording(db_session, meeting, self.upload_dir)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media", headers={**headers, "Range": "bytes=100-199"}
        )
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes 100-199/{record.size_bytes}"
        assert response.headers["content-length"] == "100"
        assert len(response.content) == 100

    def test_the_returned_bytes_are_the_ones_asked_for(self, client, headers, db_session, meeting):
        """A seek that returns the wrong offset would play the wrong audio."""
        payload = bytes(range(256)) * 40
        add_recording(db_session, meeting, self.upload_dir, payload=payload)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media", headers={**headers, "Range": "bytes=500-599"}
        )
        assert response.content == payload[500:600]

    def test_an_open_ended_range_runs_to_the_end_of_the_file(self, client, headers, db_session, meeting):
        record = add_recording(db_session, meeting, self.upload_dir)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media", headers={**headers, "Range": "bytes=10000-"}
        )
        assert response.status_code == 206
        assert len(response.content) == record.size_bytes - 10000

    def test_a_suffix_range_returns_the_trailing_bytes(self, client, headers, db_session, meeting):
        payload = bytes(range(256)) * 40
        add_recording(db_session, meeting, self.upload_dir, payload=payload)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media", headers={**headers, "Range": "bytes=-50"}
        )
        assert response.status_code == 206
        assert response.content == payload[-50:]

    def test_a_range_past_the_end_is_416(self, client, headers, db_session, meeting):
        record = add_recording(db_session, meeting, self.upload_dir)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media",
            headers={**headers, "Range": f"bytes={record.size_bytes + 100}-"},
        )
        assert response.status_code == 416
        assert response.headers["content-range"] == f"bytes */{record.size_bytes}"

    def test_an_unparseable_range_falls_back_to_the_whole_file(self, client, headers, db_session, meeting):
        """RFC 9110: a Range header that cannot be understood must be ignored."""
        record = add_recording(db_session, meeting, self.upload_dir)

        response = client.get(
            f"/api/v1/meetings/{meeting.id}/media", headers={**headers, "Range": "rows=1-2"}
        )
        assert response.status_code == 200
        assert len(response.content) == record.size_bytes

    def test_a_meeting_with_no_recording_is_a_404(self, client, headers, meeting):
        response = client.get(f"/api/v1/meetings/{meeting.id}/media", headers=headers)
        assert response.status_code == 404

    def test_a_missing_file_on_disk_is_a_404_not_a_crash(self, client, headers, db_session, meeting):
        record = add_recording(db_session, meeting, self.upload_dir)
        (self.upload_dir / record.storage_path).unlink()

        response = client.get(f"/api/v1/meetings/{meeting.id}/media", headers=headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------


class TestAuthorisation:
    ENDPOINTS = ["overview", "transcript", "insights", "media"]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_requires_authentication(self, client, meeting, endpoint):
        assert client.get(f"/api/v1/meetings/{meeting.id}/{endpoint}").status_code == 401

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_another_user_is_refused(self, client, other_headers, meeting, endpoint):
        response = client.get(f"/api/v1/meetings/{meeting.id}/{endpoint}", headers=other_headers)
        assert response.status_code == 403, "one user must not read another user's meeting"

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_unknown_meeting_is_a_404(self, client, headers, endpoint):
        assert client.get(f"/api/v1/meetings/no-such-meeting/{endpoint}", headers=headers).status_code == 404

    def test_another_user_cannot_change_an_action_item(self, client, other_headers, meeting, db_session):
        item = db_session.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).first()
        response = client.patch(
            f"/api/v1/meetings/{meeting.id}/action-items/{item.id}",
            json={"status": "done"},
            headers=other_headers,
        )
        assert response.status_code == 403

    def test_another_user_cannot_trigger_analysis(self, client, other_headers, meeting):
        response = client.post(
            f"/api/v1/meetings/{meeting.id}/insights/generate", json={"summary_mode": "short"}, headers=other_headers
        )
        assert response.status_code == 403
