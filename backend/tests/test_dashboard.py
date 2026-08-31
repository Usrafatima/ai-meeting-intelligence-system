"""
Module 6 - Dashboard & Meeting Details
API tests for the dashboard.

Run with:  python -m pytest tests/test_dashboard.py -v

Covers each panel the brief asks the dashboard to show -- recent meetings,
processing status, duration, action item counts, pending decisions, upcoming
deadlines and search -- plus the isolation guarantee that these aggregates never
include another user's meetings.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import MeetingStatus  # noqa: E402
from app.db.models_insights import ActionItem, ActionItemStatus, Deadline, Decision, DecisionStatus  # noqa: E402

from tests.module6_fixtures import (  # noqa: E402,F401
    add_insights,
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
def workspace(db_session, user):
    """
    A realistic account: two analysed meetings, one transcribed but not analysed,
    and one still processing.
    """
    launch = make_meeting(db_session, user, title="Q3 Product Launch Planning", days_ago=2, duration=110)
    add_transcript(db_session, launch)
    add_insights(db_session, launch)

    sync = make_meeting(db_session, user, title="Weekly Engineering Sync", days_ago=5, duration=200)
    add_transcript(db_session, sync)
    add_insights(db_session, sync)

    awaiting = make_meeting(db_session, user, title="Client Call - Acme Corp", days_ago=1, duration=70,
                            status=MeetingStatus.TRANSCRIBED)
    add_transcript(db_session, awaiting)

    processing = make_meeting(db_session, user, title="Design Review", days_ago=0, duration=None,
                              status=MeetingStatus.PROCESSING, participants=())

    return {"launch": launch, "sync": sync, "awaiting": awaiting, "processing": processing}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_empty_account_returns_zeroes_not_an_error(self, client, headers):
        response = client.get("/api/v1/dashboard/stats", headers=headers)
        assert response.status_code == 200

        body = response.json()
        assert body["meetings"]["total"] == 0
        assert body["action_items"]["total"] == 0
        assert body["decisions"]["total"] == 0
        assert body["deadlines"]["total"] == 0
        assert body["total_duration_label"] == "0s"

    def test_counts_meetings_by_processing_state(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["meetings"]

        assert body["total"] == 4
        assert body["processing"] == 1
        assert body["completed"] == 3
        assert body["failed"] == 0
        assert body["by_status"]["completed"] == 2
        assert body["by_status"]["transcribed"] == 1
        assert body["by_status"]["processing"] == 1

    def test_sums_recorded_duration(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/stats", headers=headers).json()
        assert body["total_duration_seconds"] == 380  # 110 + 200 + 70
        assert body["total_duration_label"] == "6m 20s"

    def test_counts_action_items_by_status(self, client, headers, workspace, db_session):
        item = db_session.query(ActionItem).first()
        item.status = ActionItemStatus.DONE
        db_session.commit()

        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["action_items"]
        assert body["total"] == 6  # three per analysed meeting
        assert body["done"] == 1
        assert body["open"] == 5

    def test_counts_pending_decisions(self, client, headers, workspace, db_session):
        decision = db_session.query(Decision).first()
        decision.status = DecisionStatus.CONFIRMED
        db_session.commit()

        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["decisions"]
        assert body["total"] == 4
        assert body["confirmed"] == 1
        assert body["pending"] == 3

    def test_flags_meetings_transcribed_but_not_analysed(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/stats", headers=headers).json()
        assert body["awaiting_analysis"] == 1, "the Acme call has a transcript but no insights"

    def test_counts_overdue_action_items(self, client, headers, workspace, db_session):
        item = db_session.query(ActionItem).filter(ActionItem.status == ActionItemStatus.OPEN).first()
        item.deadline_date = date.today() - timedelta(days=3)
        db_session.commit()

        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["action_items"]
        assert body["overdue"] >= 1

    def test_a_completed_item_is_never_counted_as_overdue(self, client, headers, workspace, db_session):
        for item in db_session.query(ActionItem).all():
            item.deadline_date = date.today() - timedelta(days=5)
            item.status = ActionItemStatus.DONE
        db_session.commit()

        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["action_items"]
        assert body["overdue"] == 0

    def test_deadline_horizon_is_configurable(self, client, headers, workspace, db_session):
        for offset, deadline in enumerate(db_session.query(Deadline).all()):
            deadline.due_date = date.today() + timedelta(days=offset * 10)
        db_session.commit()

        narrow = client.get("/api/v1/dashboard/stats", params={"horizon_days": 5}, headers=headers).json()
        wide = client.get("/api/v1/dashboard/stats", params={"horizon_days": 365}, headers=headers).json()

        assert narrow["horizon_days"] == 5
        assert wide["deadlines"]["upcoming"] >= narrow["deadlines"]["upcoming"]

    def test_separates_dated_deadlines_from_unresolvable_ones(self, client, headers, workspace, db_session):
        deadline = db_session.query(Deadline).first()
        deadline.due_date = None
        deadline.raw_phrase = "when we get to it"
        db_session.commit()

        body = client.get("/api/v1/dashboard/stats", headers=headers).json()["deadlines"]
        assert body["unscheduled"] == 1

    @pytest.mark.parametrize("horizon", [0, -1, 400])
    def test_rejects_an_out_of_range_horizon(self, client, headers, horizon):
        response = client.get("/api/v1/dashboard/stats", params={"horizon_days": horizon}, headers=headers)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Recent meetings
# ---------------------------------------------------------------------------


class TestRecentMeetings:
    def test_returns_meetings_newest_first(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/recent-meetings", params={"limit": 10}, headers=headers).json()

        assert body["total"] == 4
        titles = [m["title"] for m in body["items"]]
        assert titles[0] == "Design Review"
        assert titles[-1] == "Weekly Engineering Sync"

    def test_each_row_carries_its_own_counts(self, client, headers, workspace):
        items = client.get("/api/v1/dashboard/recent-meetings", params={"limit": 10}, headers=headers).json()["items"]
        launch = next(m for m in items if m["title"].startswith("Q3"))

        assert launch["action_items_total"] == 3
        assert launch["action_items_open"] == 3
        assert launch["decisions_pending"] == 2
        assert launch["participant_count"] == 3
        assert launch["has_transcript"] is True
        assert launch["has_insights"] is True
        assert launch["duration_label"] == "1m 50s"
        assert launch["summary_short"] is not None
        assert launch["sentiment"] == "positive"

    def test_a_processing_meeting_reports_nothing_stored(self, client, headers, workspace):
        items = client.get("/api/v1/dashboard/recent-meetings", params={"limit": 10}, headers=headers).json()["items"]
        design = next(m for m in items if m["title"] == "Design Review")

        assert design["status"] == "processing"
        assert design["has_transcript"] is False
        assert design["has_insights"] is False
        assert design["action_items_total"] == 0
        assert design["duration_label"] is None

    def test_reports_the_next_upcoming_deadline(self, client, headers, workspace, db_session):
        """The soonest still-upcoming deadline, not merely the first row found."""
        soonest = date.today() + timedelta(days=2)

        # Push this meeting's deadlines out, then bring one back in, so the
        # expected minimum is unambiguous.
        launch_deadlines = (
            db_session.query(Deadline).filter(Deadline.meeting_id == workspace["launch"].id).all()
        )
        for offset, deadline in enumerate(launch_deadlines):
            deadline.due_date = date.today() + timedelta(days=30 + offset)
        launch_deadlines[0].due_date = soonest
        db_session.commit()

        items = client.get("/api/v1/dashboard/recent-meetings", params={"limit": 10}, headers=headers).json()["items"]
        launch = next(m for m in items if m["title"].startswith("Q3"))
        assert launch["next_deadline"] == soonest.isoformat()

    def test_limit_caps_the_list_but_total_reports_everything(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/recent-meetings", params={"limit": 2}, headers=headers).json()
        assert len(body["items"]) == 2
        assert body["total"] == 4

    def test_can_filter_to_a_single_status(self, client, headers, workspace):
        body = client.get(
            "/api/v1/dashboard/recent-meetings", params={"status": "processing"}, headers=headers
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "Design Review"

    def test_rejects_an_unknown_status(self, client, headers):
        response = client.get("/api/v1/dashboard/recent-meetings", params={"status": "banana"}, headers=headers)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Deadlines and decisions
# ---------------------------------------------------------------------------


class TestUpcomingDeadlines:
    def test_returns_deadlines_across_every_meeting(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/upcoming-deadlines", params={"days": 365}, headers=headers).json()

        assert body["total"] == 6  # three per analysed meeting
        meetings = {item["meeting_title"] for item in body["items"]}
        assert len(meetings) == 2

    def test_sorted_soonest_first(self, client, headers, workspace):
        items = client.get(
            "/api/v1/dashboard/upcoming-deadlines", params={"days": 365}, headers=headers
        ).json()["items"]
        dates = [item["due_date"] for item in items]
        assert dates == sorted(dates)

    def test_carries_the_owner_and_meeting_context(self, client, headers, workspace):
        items = client.get(
            "/api/v1/dashboard/upcoming-deadlines", params={"days": 365}, headers=headers
        ).json()["items"]

        assert all(item["meeting_title"] for item in items)
        assert all(item["action_item_id"] for item in items)
        assert any(item["owner_name"] for item in items)

    def test_overdue_items_are_included_and_flagged(self, client, headers, workspace, db_session):
        # Deadlines resolve against each meeting's own date, so an older meeting
        # legitimately arrives with some already past. Normalise to future first
        # so that exactly one item is overdue by construction.
        deadlines = db_session.query(Deadline).all()
        for deadline in deadlines:
            deadline.due_date = date.today() + timedelta(days=10)
        deadlines[0].due_date = date.today() - timedelta(days=4)
        db_session.commit()

        items = client.get(
            "/api/v1/dashboard/upcoming-deadlines", params={"days": 30}, headers=headers
        ).json()["items"]

        overdue = [item for item in items if item["is_overdue"]]
        assert len(overdue) == 1
        assert overdue[0]["days_until_due"] == -4

    def test_overdue_items_can_be_excluded(self, client, headers, workspace, db_session):
        deadline = db_session.query(Deadline).first()
        deadline.due_date = date.today() - timedelta(days=4)
        db_session.commit()

        body = client.get(
            "/api/v1/dashboard/upcoming-deadlines",
            params={"days": 30, "include_overdue": "false"},
            headers=headers,
        ).json()
        assert all(not item["is_overdue"] for item in body["items"])

    def test_horizon_excludes_distant_deadlines(self, client, headers, workspace, db_session):
        for deadline in db_session.query(Deadline).all():
            deadline.due_date = date.today() + timedelta(days=90)
        db_session.commit()

        near = client.get("/api/v1/dashboard/upcoming-deadlines", params={"days": 7}, headers=headers).json()
        far = client.get("/api/v1/dashboard/upcoming-deadlines", params={"days": 120}, headers=headers).json()

        assert near["total"] == 0
        assert far["total"] == 6

    def test_deadlines_without_a_date_are_omitted(self, client, headers, workspace, db_session):
        for deadline in db_session.query(Deadline).all():
            deadline.due_date = None
        db_session.commit()

        body = client.get("/api/v1/dashboard/upcoming-deadlines", params={"days": 365}, headers=headers).json()
        assert body["total"] == 0


class TestPendingDecisions:
    def test_returns_only_unconfirmed_decisions(self, client, headers, workspace, db_session):
        decision = db_session.query(Decision).first()
        decision.status = DecisionStatus.CONFIRMED
        db_session.commit()

        body = client.get("/api/v1/dashboard/pending-decisions", headers=headers).json()
        assert body["total"] == 3
        assert all("timestamp_label" in item for item in body["items"])

    def test_each_decision_links_back_to_its_meeting_and_moment(self, client, headers, workspace):
        items = client.get("/api/v1/dashboard/pending-decisions", headers=headers).json()["items"]

        assert all(item["meeting_id"] and item["meeting_title"] for item in items)
        launch = next(i for i in items if "September 1" in i["decision"])
        assert launch["timestamp_label"] == "1:08"
        assert launch["timestamp_seconds"] == 68.0


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_finds_the_moment_a_phrase_was_spoken(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "marketing budget"}, headers=headers).json()

        assert body["total_results"] > 0
        hit = body["transcript"][0]
        assert hit["start_label"] == "1:22"
        assert hit["start_time"] == 82.0
        assert hit["segment_index"] == 6
        assert hit["meeting_title"]
        assert "marketing budget" in hit["snippet"].lower()

    def test_searches_meeting_titles(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "Engineering"}, headers=headers).json()
        assert any(m["title"] == "Weekly Engineering Sync" for m in body["meetings"])

    def test_searches_action_items_including_the_owner(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "Hina"}, headers=headers).json()
        assert len(body["action_items"]) > 0
        assert all("Hina" in (i["owner_name"] or "") or "Hina" in i["task"] for i in body["action_items"])

    def test_searches_decisions(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "September"}, headers=headers).json()
        assert len(body["decisions"]) > 0
        assert body["decisions"][0]["timestamp_label"] == "1:08"

    def test_is_case_insensitive(self, client, headers, workspace):
        lower = client.get("/api/v1/dashboard/search", params={"q": "backend"}, headers=headers).json()
        upper = client.get("/api/v1/dashboard/search", params={"q": "BACKEND"}, headers=headers).json()
        assert lower["total_results"] == upper["total_results"] > 0

    def test_types_restricts_which_groups_are_searched(self, client, headers, workspace):
        body = client.get(
            "/api/v1/dashboard/search", params={"q": "budget", "types": "transcript"}, headers=headers
        ).json()

        assert len(body["transcript"]) > 0
        assert body["meetings"] == []
        assert body["action_items"] == []
        assert body["decisions"] == []

    def test_types_accepts_several_groups(self, client, headers, workspace):
        body = client.get(
            "/api/v1/dashboard/search",
            params={"q": "backend", "types": "action_items,decisions"},
            headers=headers,
        ).json()
        assert body["transcript"] == []
        assert len(body["action_items"]) + len(body["decisions"]) > 0

    def test_no_matches_returns_an_empty_result(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "zeppelin"}, headers=headers).json()
        assert body["total_results"] == 0
        assert body["truncated"] is False

    def test_snippet_is_cut_around_the_match(self, client, headers, workspace):
        body = client.get("/api/v1/dashboard/search", params={"q": "mobile app"}, headers=headers).json()
        snippet = body["transcript"][0]["snippet"]
        assert "mobile app" in snippet.lower()
        assert len(snippet) <= 200

    def test_truncated_is_set_when_a_group_is_capped(self, client, headers, workspace):
        body = client.get(
            "/api/v1/dashboard/search", params={"q": "the", "limit_per_type": 1}, headers=headers
        ).json()
        assert body["truncated"] is True

    @pytest.mark.parametrize("query", ["", "a"])
    def test_rejects_a_query_that_is_too_short(self, client, headers, query):
        response = client.get("/api/v1/dashboard/search", params={"q": query}, headers=headers)
        assert response.status_code == 422

    def test_requires_a_query(self, client, headers):
        assert client.get("/api/v1/dashboard/search", headers=headers).status_code == 422

    def test_empty_account_searches_cleanly(self, client, headers):
        body = client.get("/api/v1/dashboard/search", params={"q": "anything"}, headers=headers).json()
        assert body["total_results"] == 0


# ---------------------------------------------------------------------------
# Authorisation and isolation
# ---------------------------------------------------------------------------


class TestAuthorisation:
    ENDPOINTS = ["stats", "recent-meetings", "upcoming-deadlines", "pending-decisions"]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_requires_authentication(self, client, endpoint):
        assert client.get(f"/api/v1/dashboard/{endpoint}").status_code == 401

    def test_search_requires_authentication(self, client):
        assert client.get("/api/v1/dashboard/search", params={"q": "budget"}).status_code == 401

    def test_another_users_meetings_are_never_counted(self, client, other_headers, workspace):
        body = client.get("/api/v1/dashboard/stats", headers=other_headers).json()

        assert body["meetings"]["total"] == 0
        assert body["action_items"]["total"] == 0
        assert body["decisions"]["total"] == 0
        assert body["deadlines"]["total"] == 0
        assert body["unresolved_issues"] == 0

    def test_another_user_sees_no_recent_meetings(self, client, other_headers, workspace):
        body = client.get("/api/v1/dashboard/recent-meetings", headers=other_headers).json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_another_user_sees_no_deadlines_or_decisions(self, client, other_headers, workspace):
        assert client.get("/api/v1/dashboard/upcoming-deadlines", headers=other_headers).json()["total"] == 0
        assert client.get("/api/v1/dashboard/pending-decisions", headers=other_headers).json()["total"] == 0

    def test_search_never_leaks_another_users_content(self, client, other_headers, workspace):
        """The clearest way this module could leak data, so it is asserted directly."""
        body = client.get(
            "/api/v1/dashboard/search", params={"q": "marketing budget"}, headers=other_headers
        ).json()

        assert body["total_results"] == 0
        assert body["meetings"] == []
        assert body["transcript"] == []
        assert body["action_items"] == []
        assert body["decisions"] == []
