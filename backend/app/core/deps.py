from fastapi import Request

from app.modules.profiles.service import ProfileService


def profile_service(request: Request) -> ProfileService:
    return ProfileService(request.app.state.engine, request.app.state.auth_admin)
