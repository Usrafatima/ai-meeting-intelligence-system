"""
Module 6 - Dashboard & Meeting Details
Deterministic parsing helpers used when storing AI insights.

Two jobs, both of which the dashboard depends on and neither of which should be
left to the language model:

1. Timestamps.  Module 5 reports where a decision was made as a display string
   ("32:45"). Seeking the recording needs a number of seconds, so the string is
   parsed once on the way into the database rather than on every page render.

2. Deadlines.  Module 5 is instructed to resolve a spoken phrase to a calendar
   date only when it is confident, and leaves `deadline` null otherwise. That is
   the right call for the model, but it means "Friday" and "end of this month"
   frequently arrive unresolved -- and an unresolved deadline cannot appear under
   "Upcoming deadlines" at all. These helpers resolve the common phrasings from
   the brief against the meeting's own date, deterministically and offline.

Everything here is pure: no I/O, no model calls, no database. That keeps it fast
and directly unit-testable.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Optional

__all__ = ["parse_timestamp_to_seconds", "format_seconds_as_timestamp", "resolve_deadline"]


# --------------------------------------------------------------------------
# Timestamps
# --------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.\d+)?\s*$")


def parse_timestamp_to_seconds(value: Optional[str]) -> Optional[float]:
    """
    Turn a display timestamp into seconds.

    Accepts "mm:ss" and "hh:mm:ss", with or without a fractional part. Returns
    None for anything else, including None itself, so callers can pass model
    output straight in without pre-checking.

        >>> parse_timestamp_to_seconds("32:45")
        1965.0
        >>> parse_timestamp_to_seconds("1:02:33")
        3753.0
        >>> parse_timestamp_to_seconds("sometime later") is None
        True
    """
    if not value or not isinstance(value, str):
        return None

    # A bare number of seconds is also accepted -- some models return "1965".
    stripped = value.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", stripped):
        return float(stripped)

    match = _TIMESTAMP_RE.match(stripped)
    if not match:
        return None

    hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    return float(total)


def format_seconds_as_timestamp(seconds: Optional[float]) -> Optional[str]:
    """
    Render seconds as the label shown next to a decision or transcript line.

    Uses mm:ss below an hour and hh:mm:ss at or above it, matching how the brief
    writes timestamps ("finalized at 32:45").
    """
    if seconds is None or seconds < 0:
        return None

    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# --------------------------------------------------------------------------
# Deadlines
# --------------------------------------------------------------------------

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WEEKDAY_NAMES = "|".join(_WEEKDAYS)

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY_RE = re.compile(rf"\b({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b")
_DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_NAMES})\b")
_IN_N_UNITS_RE = re.compile(r"\bin\s+(\d{1,3})\s+(day|days|week|weeks|month|months)\b")
_WEEKDAY_RE = re.compile(rf"\b(next|this|coming)?\s*({_WEEKDAY_NAMES})\b")


def _end_of_month(anchor: date, months_ahead: int = 0) -> date:
    """Last calendar day of the month `months_ahead` months after `anchor`."""
    year = anchor.year + (anchor.month - 1 + months_ahead) // 12
    month = (anchor.month - 1 + months_ahead) % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def _next_weekday(anchor: date, weekday: int, force_next_week: bool) -> date:
    """
    The next occurrence of `weekday` strictly after `anchor`.

    "next Monday" is read as the Monday of the following week, which is how people
    normally mean it; a bare "Monday" means the soonest upcoming Monday.
    """
    delta = (weekday - anchor.weekday()) % 7
    if delta == 0:
        delta = 7  # "Friday" said on a Friday means the next one, not today.
    result = anchor + timedelta(days=delta)
    if force_next_week and (weekday - anchor.weekday()) % 7 != 0:
        # Only push out by a week when the plain reading landed in the current week.
        if result <= anchor + timedelta(days=6 - anchor.weekday()):
            result += timedelta(days=7)
    return result


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def resolve_deadline(phrase: Optional[str], anchor: date) -> Optional[date]:
    """
    Resolve a spoken deadline phrase to a calendar date.

    `anchor` is the date the meeting took place -- every relative phrase is read
    against it, so re-processing an old recording still produces the dates the
    participants meant, not dates relative to today.

    Returns None when the phrase carries no resolvable date, which is a normal
    outcome and not an error.

        >>> from datetime import date
        >>> monday = date(2026, 8, 31)          # a Monday
        >>> resolve_deadline("tomorrow", monday)
        datetime.date(2026, 9, 1)
        >>> resolve_deadline("Friday", monday)
        datetime.date(2026, 9, 4)
        >>> resolve_deadline("end of this month", monday)
        datetime.date(2026, 8, 31)
        >>> resolve_deadline("September 10", monday)
        datetime.date(2026, 9, 10)
    """
    if not phrase or not isinstance(phrase, str):
        return None

    text = phrase.strip().lower()
    if not text:
        return None

    # --- Explicit calendar dates -----------------------------------------
    iso = _ISO_RE.search(text)
    if iso:
        resolved = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if resolved:
            return resolved

    month_day = _MONTH_DAY_RE.search(text)
    if month_day:
        month = _MONTHS[month_day.group(1)]
        resolved = _safe_date(anchor.year, month, int(month_day.group(2)))
        # A month already behind us refers to next year.
        if resolved and resolved < anchor:
            resolved = _safe_date(anchor.year + 1, month, int(month_day.group(2)))
        if resolved:
            return resolved

    day_month = _DAY_MONTH_RE.search(text)
    if day_month:
        month = _MONTHS[day_month.group(2)]
        resolved = _safe_date(anchor.year, month, int(day_month.group(1)))
        if resolved and resolved < anchor:
            resolved = _safe_date(anchor.year + 1, month, int(day_month.group(1)))
        if resolved:
            return resolved

    # --- Month boundaries -------------------------------------------------
    # Checked before weekdays so "end of next month" is not caught by "next".
    if re.search(r"\bend of (the |this )?month\b", text):
        return _end_of_month(anchor)
    if re.search(r"\bend of next month\b", text):
        return _end_of_month(anchor, 1)
    if re.search(r"\bend of (the |this )?week\b", text):
        return anchor + timedelta(days=(4 - anchor.weekday()) % 7)  # that Friday
    if re.search(r"\bnext month\b", text):
        return _end_of_month(anchor, 1)

    # --- Simple relative days --------------------------------------------
    if re.search(r"\bday after tomorrow\b", text):
        return anchor + timedelta(days=2)
    if re.search(r"\btomorrow\b", text):
        return anchor + timedelta(days=1)
    if re.search(r"\btoday\b|\bend of (the )?day\b|\beod\b", text):
        return anchor
    if re.search(r"\bnext week\b", text):
        # Friday of the following week -- the usual practical reading.
        return anchor + timedelta(days=(4 - anchor.weekday()) % 7 + 7)

    counted = _IN_N_UNITS_RE.search(text)
    if counted:
        amount, unit = int(counted.group(1)), counted.group(2)
        if unit.startswith("day"):
            return anchor + timedelta(days=amount)
        if unit.startswith("week"):
            return anchor + timedelta(weeks=amount)
        if unit.startswith("month"):
            return _end_of_month(anchor, amount)

    # --- Weekday names ----------------------------------------------------
    weekday = _WEEKDAY_RE.search(text)
    if weekday:
        qualifier = (weekday.group(1) or "").strip()
        return _next_weekday(anchor, _WEEKDAYS[weekday.group(2)], qualifier == "next")

    return None
