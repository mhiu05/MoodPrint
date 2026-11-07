from moodprint_shared.contracts.auth import AuthContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.uow import user_uow
from app.modules.profiles.schemas import Profile, ProfilePatch


class ProfileService:
    def __init__(self, engine: AsyncEngine, auth_provider=None):
        self.engine = engine
        self.auth_provider = auth_provider

    async def get_or_seed(self, auth: AuthContext, token: str) -> Profile:
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.profiles WHERE user_id=:id"), {"id": auth.user_id}
                    )
                )
                .mappings()
                .first()
            )
            if row:
                return Profile.model_validate({name: row[name] for name in Profile.model_fields})
        # Metadata is used only for validated initial display fields, never ownership/roles.
        metadata = await self.auth_provider.user_metadata(auth, token) if self.auth_provider else {}
        return await self.get(auth, metadata)

    async def get(self, auth: AuthContext, metadata: dict | None = None) -> Profile:
        metadata = metadata or {}
        nickname = metadata.get("nickname")
        if not isinstance(nickname, str) or not 2 <= len(nickname.strip()) <= 32:
            nickname = "Bạn"
        age_band = metadata.get("age_band")
        if age_band not in ("11-13", "14-17"):
            age_band = None
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO app.profiles(user_id,nickname,age_band) VALUES (:id,:nickname,:age_band) ON CONFLICT(user_id) DO NOTHING"
                ),
                {"id": auth.user_id, "nickname": nickname.strip(), "age_band": age_band},
            )
            row = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.profiles WHERE user_id=:id"), {"id": auth.user_id}
                    )
                )
                .mappings()
                .one()
            )
            return Profile.model_validate({name: row[name] for name in Profile.model_fields})

    async def patch(self, auth: AuthContext, data: ProfilePatch) -> Profile:
        await self.get(auth)
        changes = data.model_dump(exclude_unset=True)
        if changes:
            if (
                changes.get("nickname", "valid") is None
                or changes.get("reduced_motion", False) is None
            ):
                from app.core.errors import ApiError

                raise ApiError("validation_failed", "Vui lòng kiểm tra dữ liệu nhập.", 422)
            assignment = ",".join(f"{name}=:{name}" for name in changes)
            async with user_uow(self.engine, auth) as uow:
                await uow.session.execute(
                    text(f"UPDATE app.profiles SET {assignment} WHERE user_id=:id"),
                    {**changes, "id": auth.user_id},
                )
        return await self.get(auth)
