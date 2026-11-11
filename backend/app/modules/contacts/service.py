from uuid import UUID

from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.errors import NotFound
from safevoice_shared.contracts.paging import Page
from sqlalchemy import text

from app.core.paging import decode_cursor, encode_cursor
from app.core.uow import user_uow
from app.modules.contacts.schemas import ContactCreate, ContactPatch, ContactRead


def dto(row):
    return ContactRead.model_validate({k: row[k] for k in ContactRead.model_fields})


class ContactService:
    def __init__(self, engine):
        self.engine = engine

    async def _get(self, session, auth, id):
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.trusted_contacts WHERE id=:id AND owner_id=:owner"),
                    {"id": id, "owner": auth.user_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound()
        return row

    async def get(self, auth: AuthContext, id: UUID) -> ContactRead:
        async with user_uow(self.engine, auth) as uow:
            return dto(await self._get(uow.session, auth, id))

    async def list(self, auth: AuthContext, *, limit=50, cursor=None) -> Page[ContactRead]:
        position = decode_cursor(cursor, scope="contacts", owner=auth.user_id)
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
                            "SELECT * FROM app.trusted_contacts WHERE owner_id=:owner"
                            + after
                            + " ORDER BY created_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        items = [dto(row) for row in rows[:limit]]
        next_cursor = (
            encode_cursor(
                scope="contacts", owner=auth.user_id, at=items[-1].created_at, id=items[-1].id
            )
            if len(rows) > limit
            else None
        )
        return Page[ContactRead](items=items, next_cursor=next_cursor)

    async def create(self, auth: AuthContext, data: ContactCreate) -> ContactRead:
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO app.trusted_contacts(id,owner_id,label,role) VALUES(:id,:owner,:label,:role) ON CONFLICT(id) DO NOTHING"
                ),
                {**data.model_dump(), "owner": auth.user_id},
            )
            return dto(await self._get(uow.session, auth, data.id))

    async def patch(self, auth: AuthContext, id: UUID, data: ContactPatch) -> ContactRead:
        changes = data.model_dump(exclude_unset=True)
        async with user_uow(self.engine, auth) as uow:
            await self._get(uow.session, auth, id)
            if changes:
                assignments = ",".join(f"{key}=:{key}" for key in changes)
                await uow.session.execute(
                    text(
                        f"UPDATE app.trusted_contacts SET {assignments} WHERE id=:id AND owner_id=:owner"
                    ),
                    {**changes, "id": id, "owner": auth.user_id},
                )
            return dto(await self._get(uow.session, auth, id))

    async def delete(self, auth: AuthContext, id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await self._get(uow.session, auth, id)
            await uow.session.execute(
                text("DELETE FROM app.trusted_contacts WHERE id=:id AND owner_id=:owner"),
                {"id": id, "owner": auth.user_id},
            )
