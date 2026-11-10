import json
from uuid import UUID

from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound, VersionConflict
from moodprint_shared.contracts.paging import Page
from sqlalchemy import text

from app.core.paging import decode_cursor, encode_cursor
from app.core.uow import user_uow
from app.modules.support.schemas import DraftCreate, DraftPatch, DraftRead


def dto(row):
    return DraftRead.model_validate({k: row[k] for k in DraftRead.model_fields})


class SupportService:
    def __init__(self, engine):
        self.engine = engine

    async def _get(self, session, auth, id, *, lock=False):
        row = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM app.support_drafts WHERE id=:id AND owner_id=:owner"
                        + (" FOR UPDATE" if lock else "")
                    ),
                    {"id": id, "owner": auth.user_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound()
        return row

    async def _case(self, session, auth, case_id):
        if case_id and not await session.scalar(
            text("SELECT id FROM app.cases WHERE id=:id AND owner_id=:owner"),
            {"id": case_id, "owner": auth.user_id},
        ):
            raise NotFound()

    async def get(self, auth: AuthContext, id: UUID) -> DraftRead:
        async with user_uow(self.engine, auth) as uow:
            return dto(await self._get(uow.session, auth, id))

    async def list(self, auth: AuthContext, *, limit=50, cursor=None) -> Page[DraftRead]:
        position = decode_cursor(cursor, scope="support-drafts", owner=auth.user_id)
        params = {"owner": auth.user_id, "limit": limit + 1}
        after = ""
        if position:
            after = " AND (created_at,id)>(:at,:id)"
            params.update(at=position.at, id=position.id)
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.support_drafts WHERE owner_id=:owner"
                            + after
                            + " ORDER BY created_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        items = [dto(row) for row in rows[:limit]]
        return Page[DraftRead](
            items=items,
            next_cursor=encode_cursor(
                scope="support-drafts", owner=auth.user_id, at=items[-1].created_at, id=items[-1].id
            )
            if len(rows) > limit
            else None,
        )

    async def create(self, auth: AuthContext, data: DraftCreate) -> DraftRead:
        async with user_uow(self.engine, auth) as uow:
            existing = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.support_drafts WHERE id=:id AND owner_id=:owner"),
                        {"id": data.id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return dto(existing)
            await self._case(uow.session, auth, data.case_id)
            params = {
                **data.model_dump(),
                "owner": auth.user_id,
                "compose": json.dumps(data.compose),
            }
            await uow.session.execute(
                text("""INSERT INTO app.support_drafts(id,owner_id,case_id,recipient_type,identity_mode,content,compose,status)
              VALUES(:id,:owner,:case_id,:recipient_type,:identity_mode,:content,CAST(:compose AS jsonb),:status) ON CONFLICT(id) DO NOTHING"""),
                params,
            )
            return dto(await self._get(uow.session, auth, data.id))

    async def patch(self, auth: AuthContext, id: UUID, data: DraftPatch) -> DraftRead:
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        async with user_uow(self.engine, auth) as uow:
            current = dto(await self._get(uow.session, auth, id, lock=True))
            if current.version != data.version:
                raise VersionConflict(
                    details={"latest": current.model_dump(mode="json", by_alias=True)}
                )
            if "case_id" in changes:
                await self._case(uow.session, auth, changes["case_id"])
            if changes:
                assignments = ",".join(
                    f"{key}=CAST(:{key} AS jsonb)" if key == "compose" else f"{key}=:{key}"
                    for key in changes
                )
                if "compose" in changes:
                    changes["compose"] = json.dumps(changes["compose"])
                await uow.session.execute(
                    text(
                        f"UPDATE app.support_drafts SET {assignments} WHERE id=:id AND owner_id=:owner"
                    ),
                    {**changes, "id": id, "owner": auth.user_id},
                )
            return dto(await self._get(uow.session, auth, id))

    async def delete(self, auth: AuthContext, id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await self._get(uow.session, auth, id)
            await uow.session.execute(
                text("DELETE FROM app.support_drafts WHERE id=:id AND owner_id=:owner"),
                {"id": id, "owner": auth.user_id},
            )
