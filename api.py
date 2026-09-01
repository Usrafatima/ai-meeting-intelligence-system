from fastapi import APIRouter

from app.api.routes import (
    auth,
    users,
    meetings,
    transcripts,
    internal,
    stt,
    meeting_intelligence,
    dashboard,
    meeting_details,
)

api_router = APIRouter()


# ============================================================
# AUTH
# ============================================================

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
)


# ============================================================
# USERS
# ============================================================

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
)


# ============================================================
# MEETINGS
# ============================================================

api_router.include_router(
    meetings.router,
    prefix="/meetings",
    tags=["meetings"],
)


# ============================================================
# TRANSCRIPTS / RAG
# ============================================================

api_router.include_router(
    transcripts.router,
    prefix="/meetings",
    tags=["transcripts"],
)


# ============================================================
# INTERNAL
# ============================================================

api_router.include_router(
    internal.router,
    prefix="/internal",
    tags=["internal"],
)


# ============================================================
# STT
# ============================================================

api_router.include_router(
    stt.router,
    prefix="/meetings",
    tags=["stt"],
)


# ============================================================
# MEETING INTELLIGENCE
# ============================================================

api_router.include_router(
    meeting_intelligence.router,
    prefix="/meeting-intelligence",
    tags=["meeting-intelligence"],
)


# ============================================================
# MEETING DETAILS
# ============================================================

api_router.include_router(
    meeting_details.router,
    prefix="/meetings",
    tags=["meeting-details"],
)


# ============================================================
# DASHBOARD
# ============================================================

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"],
)