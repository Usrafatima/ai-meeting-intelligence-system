from fastapi import APIRouter

from app.api.routes import auth, users, meetings, internal, stt

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
api_router.include_router(stt.router, prefix="/stt", tags=["stt"])
