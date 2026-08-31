"""
Module 6 - Dashboard & Meeting Details
Unit tests for deadline and timestamp parsing.

Run with:  python -m pytest tests/test_insight_parsing.py -v

These cover the pure helpers behind two dashboard features. Deadline resolution
in particular is worth testing directly: the brief lists the phrasings that must
work, and each is asserted below against a known anchor date rather than against
whatever today happens to be, so the suite cannot pass or fail by calendar luck.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.insight_parsing import (  # noqa: E402
    format_seconds_as_timestamp,
    parse_timestamp_to_seconds,
    resolve_deadline,
)

# All relative phrases are resolved against this anchor, a Monday.
MONDAY = date(2026, 8, 31)
SATURDAY = date(2026, 8, 29)


class TestParseTimestampToSeconds:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("32:45", 1965.0),
            ("0:07", 7.0),
            ("1:02:33", 3753.0),
            ("00:00", 0.0),
            ("2:06.5", 126.0),
            ("1965", 1965.0),
        ],
    )
    def test_parses_known_forms(self, value, expected):
        assert parse_timestamp_to_seconds(value) == expected

    @pytest.mark.parametrize("value", [None, "", "   ", "later", "half past two", "abc:def"])
    def test_returns_none_for_unparseable(self, value):
        assert parse_timestamp_to_seconds(value) is None

    def test_ignores_surrounding_whitespace(self):
        assert parse_timestamp_to_seconds("  12:30  ") == 750.0


class TestFormatSecondsAsTimestamp:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (1965.0, "32:45"),
            (7.0, "0:07"),
            (3753.0, "1:02:33"),
            (0.0, "0:00"),
            (59.9, "0:59"),
            (3600.0, "1:00:00"),
        ],
    )
    def test_formats_for_display(self, seconds, expected):
        assert format_seconds_as_timestamp(seconds) == expected

    def test_returns_none_for_missing_or_negative(self):
        assert format_seconds_as_timestamp(None) is None
        assert format_seconds_as_timestamp(-5) is None

    def test_round_trips_with_the_parser(self):
        for seconds in (0.0, 7.0, 126.0, 1965.0, 3753.0):
            assert parse_timestamp_to_seconds(format_seconds_as_timestamp(seconds)) == seconds


class TestResolveDeadline:
    """Every phrasing the brief lists as needing to work."""

    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("tomorrow", date(2026, 9, 1)),
            ("Friday", date(2026, 9, 4)),
            ("next Monday", date(2026, 9, 7)),
            ("September 10", date(2026, 9, 10)),
            ("end of this month", date(2026, 8, 31)),
        ],
    )
    def test_resolves_the_examples_from_the_brief(self, phrase, expected):
        assert resolve_deadline(phrase, MONDAY) == expected

    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("today", MONDAY),
            ("day after tomorrow", date(2026, 9, 2)),
            ("by Wednesday", date(2026, 9, 2)),
            ("this Friday", date(2026, 9, 4)),
            ("next Friday", date(2026, 9, 11)),
            ("end of next month", date(2026, 9, 30)),
            ("in 3 days", date(2026, 9, 3)),
            ("in 2 weeks", date(2026, 9, 14)),
            ("2026-12-01", date(2026, 12, 1)),
            ("the 15th of October", date(2026, 10, 15)),
            ("Sept 10", date(2026, 9, 10)),
        ],
    )
    def test_resolves_common_variations(self, phrase, expected):
        assert resolve_deadline(phrase, MONDAY) == expected

    @pytest.mark.parametrize(
        "phrase", [None, "", "   ", "soon", "as soon as possible", "when we get to it", "later this quarter"]
    )
    def test_returns_none_when_no_date_is_expressible(self, phrase):
        assert resolve_deadline(phrase, MONDAY) is None

    def test_is_case_insensitive(self):
        assert resolve_deadline("NEXT MONDAY", MONDAY) == resolve_deadline("next monday", MONDAY)

    def test_resolves_against_the_anchor_not_today(self):
        """
        The whole point of anchoring: the same phrase said in two different
        meetings resolves to two different dates.
        """
        assert resolve_deadline("tomorrow", MONDAY) == date(2026, 9, 1)
        assert resolve_deadline("tomorrow", SATURDAY) == date(2026, 8, 30)

    def test_a_weekday_never_resolves_to_the_anchor_itself(self):
        """'Friday' said on a Friday means the next one, not the day it was said."""
        friday = date(2026, 9, 4)
        assert resolve_deadline("Friday", friday) == date(2026, 9, 11)

    def test_a_month_already_past_rolls_into_next_year(self):
        # In August, "January 15" cannot mean a date seven months behind us.
        assert resolve_deadline("January 15", MONDAY) == date(2027, 1, 15)

    def test_end_of_month_handles_february_in_a_leap_year(self):
        assert resolve_deadline("end of this month", date(2028, 2, 3)) == date(2028, 2, 29)

    def test_month_boundary_beats_weekday_matching(self):
        """'end of next month' must not be captured by the 'next <weekday>' rule."""
        assert resolve_deadline("end of next month", MONDAY) == date(2026, 9, 30)

    def test_rejects_an_impossible_calendar_date(self):
        assert resolve_deadline("February 30", MONDAY) is None
