"""Only a user's explicit confirmation can freeze a school-scoped snapshot."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.errors import Forbidden, NotFound, VersionConflict
from safevoice_shared.contracts.evidence import SignedRead
from safevoice_shared.contracts.paging import Page
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.core.paging import decode_cursor, encode_cursor
from app.core.uow import user_uow
from app.modules.sharing.schemas import (
    SchoolRead,
    SchoolShareRead,
    ShareCreate,
    SharePatch,
    SharePreview,
    ShareRead,
    ShareSubmit,
)


def dto(model, row):
    return model.model_validate({k: row[k] for k in model.model_fields if k in row})


class SharingService:
    def __init__(self, engine, storage, cfg: AppConfig | None = None):
        self.engine, self.storage, self.cfg = engine, storage, cfg or AppConfig()

    async def _get(self, session, auth, id, *, lock=False):
        if lock:
            # Parent-before-child matches case deletion and timeline mutations.
            # Read identity without locking, lock the parent, then re-read share
            # under its row lock so deletion/withdrawal cannot leave stale state.
            initial = await self._get(session, auth, id)
            if initial["case_id"] is not None:
                await self._case(session, auth, initial["case_id"])
        row = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM app.case_shares WHERE id=:id AND owner_id=:owner"
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
        return dict(row)

    async def _read(self, session, auth, row):
        ids = list(
            (
                await session.execute(
                    text(
                        "SELECT evidence_id FROM app.case_share_evidence WHERE share_id=:id AND owner_id=:owner ORDER BY evidence_id"
                    ),
                    {"id": row["id"], "owner": auth.user_id},
                )
            ).scalars()
        )
        return dto(ShareRead, {**row, "evidence_ids": ids})

    async def _school(self, session, id):
        if not await session.scalar(text("SELECT id FROM app.schools WHERE id=:id"), {"id": id}):
            raise NotFound()

    async def _case(self, session, auth, id):
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.cases WHERE id=:id AND owner_id=:owner FOR UPDATE"),
                    {"id": id, "owner": auth.user_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound()
        return row

    async def _selections(self, session, auth, share_id, case_id, ids):
        await session.execute(
            text("DELETE FROM app.case_share_evidence WHERE share_id=:id AND owner_id=:owner"),
            {"id": share_id, "owner": auth.user_id},
        )
        for id in sorted(set(ids)):
            valid = await session.scalar(
                text(
                    "SELECT id FROM app.evidence_items WHERE id=:id AND owner_id=:owner AND case_id=:case AND upload_status='uploaded' FOR SHARE"
                ),
                {"id": id, "owner": auth.user_id, "case": case_id},
            )
            if valid is None:
                raise NotFound()
            await session.execute(
                text(
                    "INSERT INTO app.case_share_evidence(share_id,evidence_id,owner_id) VALUES(:share,:evidence,:owner)"
                ),
                {"share": share_id, "evidence": id, "owner": auth.user_id},
            )

    async def create(self, auth: AuthContext, data: ShareCreate) -> ShareRead:
        try:
            async with user_uow(self.engine, auth) as uow:
                # Serialize retries and one-active-share checks per owner.
                await uow.session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                    {"key": "sharing:" + str(auth.user_id)},
                )
                existing = (
                    (
                        await uow.session.execute(
                            text("SELECT * FROM app.case_shares WHERE id=:id AND owner_id=:owner"),
                            {"id": data.id, "owner": auth.user_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    return await self._read(uow.session, auth, existing)
                await self._case(uow.session, auth, data.case_id)
                await self._school(uow.session, data.school_id)
                await uow.session.execute(
                    text("""INSERT INTO app.case_shares(id,owner_id,case_id,school_id,identity_mode,shared_fields)
                  VALUES(:id,:owner,:case_id,:school_id,:identity_mode,:shared_fields) ON CONFLICT(id) DO NOTHING"""),
                    {**data.model_dump(exclude={"evidence_ids"}), "owner": auth.user_id},
                )
                row = await self._get(uow.session, auth, data.id)
                await self._selections(uow.session, auth, data.id, data.case_id, data.evidence_ids)
                return await self._read(uow.session, auth, row)
        except IntegrityError as error:
            raise ApiError(
                "conflict", "Hồ sơ đã có một bản chia sẻ đang hoạt động với trường này.", 409
            ) from error

    async def get(self, auth: AuthContext, id: UUID) -> ShareRead:
        async with user_uow(self.engine, auth) as uow:
            return await self._read(uow.session, auth, await self._get(uow.session, auth, id))

    async def list(self, auth: AuthContext, *, limit=50, cursor=None) -> Page[ShareRead]:
        position = decode_cursor(cursor, scope="shares", owner=auth.user_id)
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
                            "SELECT * FROM app.case_shares WHERE owner_id=:owner"
                            + after
                            + " ORDER BY created_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
            items = [await self._read(uow.session, auth, row) for row in rows[:limit]]
        return Page[ShareRead](
            items=items,
            next_cursor=encode_cursor(
                scope="shares", owner=auth.user_id, at=items[-1].created_at, id=items[-1].id
            )
            if len(rows) > limit
            else None,
        )

    async def patch(self, auth: AuthContext, id: UUID, data: SharePatch) -> ShareRead:
        try:
            async with user_uow(self.engine, auth) as uow:
                row = await self._get(uow.session, auth, id, lock=True)
                current = await self._read(uow.session, auth, row)
                if row["version"] != data.version:
                    raise VersionConflict(
                        details={"latest": current.model_dump(mode="json", by_alias=True)}
                    )
                if row["status"] != "draft":
                    raise ApiError("conflict", "Chỉ bản nháp mới có thể chỉnh sửa.", 409)
                changes = data.model_dump(exclude_unset=True, exclude={"version", "evidence_ids"})
                if "school_id" in changes:
                    await self._school(uow.session, changes["school_id"])
                if changes:
                    assignments = ",".join(f"{k}=:{k}" for k in changes)
                    await uow.session.execute(
                        text(
                            f"UPDATE app.case_shares SET {assignments} WHERE id=:id AND owner_id=:owner"
                        ),
                        {**changes, "id": id, "owner": auth.user_id},
                    )
                if "evidence_ids" in data.model_fields_set:
                    await self._selections(
                        uow.session, auth, id, row["case_id"], data.evidence_ids or []
                    )
                    if not changes:
                        await uow.session.execute(
                            text(
                                "UPDATE app.case_shares SET updated_at=now() WHERE id=:id AND owner_id=:owner"
                            ),
                            {"id": id, "owner": auth.user_id},
                        )
                return await self._read(uow.session, auth, await self._get(uow.session, auth, id))
        except IntegrityError as error:
            raise ApiError(
                "conflict", "Bản chia sẻ bị trùng với bản đang hoạt động.", 409
            ) from error

    async def _preview(self, session, auth, share):
        case = await self._case(session, auth, share["case_id"])
        profile = (
            (
                await session.execute(
                    text("SELECT nickname FROM app.profiles WHERE user_id=:owner"),
                    {"owner": auth.user_id},
                )
            )
            .mappings()
            .first()
        )
        identity = {
            "mode": share["identity_mode"],
            "alias": profile["nickname"] if profile else "Bạn",
        }
        if share["identity_mode"] == "disclose":
            identity["userId"] = str(auth.user_id)
        fields = {}
        names = {
            "title": "title",
            "summary": "summary",
            "occurredAt": "occurred_label",
            "place": "place",
            "people": "people",
            "impactTags": "impact_tags",
            "tried": "tried",
        }
        for name in sorted(set(share["shared_fields"])):
            if name == "events":
                events = (
                    await session.execute(
                        text(
                            "SELECT id,occurred_at,occurred_on,time_precision,place,description,provenance,needs_review FROM app.case_events WHERE case_id=:case AND owner_id=:owner ORDER BY occurred_on NULLS LAST,occurred_at NULLS LAST,id FOR SHARE"
                        ),
                        {"case": share["case_id"], "owner": auth.user_id},
                    )
                ).mappings()
                fields["events"] = [
                    {
                        "id": str(event["id"]),
                        "when": event["occurred_at"].isoformat()
                        if event["time_precision"] == "exact"
                        else event["occurred_on"].isoformat()
                        if event["occurred_on"]
                        else "",
                        "timePrecision": event["time_precision"],
                        "place": event["place"],
                        "description": event["description"],
                        "provenance": event["provenance"],
                        "needsReview": event["needs_review"],
                    }
                    for event in events
                ]
            else:
                fields[name] = case[names[name]]
        evidence = list(
            (
                await session.execute(
                    text("""SELECT ei.id,ei.kind,ei.original_filename,ei.stored_mime_type,ei.byte_size,ei.original_text,ei.user_edited_text
          FROM app.case_share_evidence selected JOIN app.evidence_items ei ON ei.id=selected.evidence_id AND ei.owner_id=selected.owner_id
          WHERE selected.share_id=:share AND selected.owner_id=:owner AND ei.upload_status='uploaded' ORDER BY ei.id FOR SHARE OF ei"""),
                    {"share": share["id"], "owner": auth.user_id},
                )
            ).mappings()
        )
        snapshot = {
            "identity": identity,
            "fields": fields,
            "evidence": [
                {
                    "id": str(row["id"]),
                    "kind": row["kind"],
                    "originalFilename": row["original_filename"],
                    "storedMimeType": row["stored_mime_type"],
                    "byteSize": row["byte_size"],
                    **(
                        {
                            "originalText": row["original_text"],
                            "userEditedText": row["user_edited_text"],
                        }
                        if row["kind"] == "text_note"
                        else {}
                    ),
                }
                for row in evidence
            ],
        }
        hashed = json.dumps(
            {
                "shareId": str(share["id"]),
                "schoolId": str(share["school_id"]),
                "version": share["version"],
                "snapshot": snapshot,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return SharePreview(
            snapshot=snapshot, preview_hash=hashlib.sha256(hashed.encode()).hexdigest()
        )

    async def preview(self, auth: AuthContext, id: UUID) -> SharePreview:
        async with user_uow(self.engine, auth) as uow:
            share = await self._get(uow.session, auth, id, lock=True)
            if share["status"] != "draft":
                raise ApiError("conflict", "Bản chia sẻ không còn là bản nháp.", 409)
            return await self._preview(uow.session, auth, share)

    async def submit(self, auth: AuthContext, id: UUID, data: ShareSubmit) -> ShareRead:
        async with user_uow(self.engine, auth) as uow:
            row = await self._get(uow.session, auth, id, lock=True)
            if row["status"] != "draft":
                raise ApiError("conflict", "Bản chia sẻ đã được quyết định.", 409)
            preview = await self._preview(uow.session, auth, row)
            if preview.preview_hash != data.preview_hash:
                raise VersionConflict("Nội dung đã thay đổi. Vui lòng xem lại bản xem trước.")
            await uow.session.execute(
                text(
                    """UPDATE app.case_shares SET status='submitted',snapshot=CAST(:snapshot AS jsonb),confirmation_version=:confirmation,confirmed_at=now(),submitted_at=now() WHERE id=:id AND owner_id=:owner"""
                ),
                {
                    "snapshot": json.dumps(preview.snapshot),
                    "confirmation": data.confirmation_version,
                    "id": id,
                    "owner": auth.user_id,
                },
            )
            await uow.session.execute(
                text(
                    "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id,school_id) VALUES(:owner,'share.submitted','share',:id,:school)"
                ),
                {"owner": auth.user_id, "id": id, "school": row["school_id"]},
            )
            return await self._read(uow.session, auth, await self._get(uow.session, auth, id))

    async def withdraw(self, auth: AuthContext, id: UUID) -> ShareRead:
        async with user_uow(self.engine, auth) as uow:
            row = await self._get(uow.session, auth, id, lock=True)
            if row["status"] != "withdrawn":
                await uow.session.execute(
                    text(
                        "UPDATE app.case_shares SET status='withdrawn',snapshot=NULL,withdrawn_at=now() WHERE id=:id AND owner_id=:owner"
                    ),
                    {"id": id, "owner": auth.user_id},
                )
                await uow.session.execute(
                    text(
                        "DELETE FROM app.case_share_evidence WHERE share_id=:id AND owner_id=:owner"
                    ),
                    {"id": id, "owner": auth.user_id},
                )
                await uow.session.execute(
                    text(
                        "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id,school_id) VALUES(:owner,'share.withdrawn','share',:id,:school)"
                    ),
                    {"owner": auth.user_id, "id": id, "school": row["school_id"]},
                )
            return await self._read(uow.session, auth, await self._get(uow.session, auth, id))

    async def schools(self, auth: AuthContext, *, limit=50, cursor=None) -> Page[SchoolRead]:
        position = decode_cursor(cursor, scope="schools", owner=auth.user_id)
        where = "verification_status='verified'"
        params: dict[str, object] = {"limit": limit + 1}
        if position:
            where += " AND (created_at,id)>(:at,:id)"
            params.update(at=position.at, id=position.id)
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.schools WHERE {where} ORDER BY created_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        items = [dto(SchoolRead, row) for row in rows[:limit]]
        return Page[SchoolRead](
            items=items,
            next_cursor=encode_cursor(
                scope="schools", owner=auth.user_id, at=items[-1].created_at, id=items[-1].id
            )
            if len(rows) > limit
            else None,
        )

    async def _member(self, session, auth, school_id):
        if not await session.scalar(
            text(
                "SELECT school_id FROM app.school_memberships WHERE school_id=:school AND user_id=:user AND status='active'"
            ),
            {"school": school_id, "user": auth.user_id},
        ):
            raise Forbidden()

    async def school_list(
        self, auth: AuthContext, school_id: UUID, *, limit=50, cursor=None
    ) -> Page[SchoolShareRead]:
        scope = "school-shares:" + str(school_id)
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        params = {"school": school_id, "limit": limit + 1}
        where = "school_id=:school AND status IN ('submitted','in_review','closed')"
        if position:
            where += " AND (submitted_at,id)>(:at,:id)"
            params.update(at=position.at, id=position.id)
        async with user_uow(self.engine, auth) as uow:
            await self._member(uow.session, auth, school_id)
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT id,school_id,status,snapshot,submitted_at FROM app.case_shares WHERE {where} ORDER BY submitted_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        items = [dto(SchoolShareRead, row) for row in rows[:limit]]
        return Page[SchoolShareRead](
            items=items,
            next_cursor=encode_cursor(
                scope=scope, owner=auth.user_id, at=items[-1].submitted_at, id=items[-1].id
            )
            if len(rows) > limit
            else None,
        )

    async def _school_get(self, session, auth, school_id, id):
        await self._member(session, auth, school_id)
        row = (
            (
                await session.execute(
                    text(
                        "SELECT id,school_id,status,snapshot,submitted_at FROM app.case_shares WHERE id=:id AND school_id=:school AND status IN ('submitted','in_review','closed')"
                    ),
                    {"id": id, "school": school_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound()
        return dto(SchoolShareRead, row)

    async def school_get(self, auth: AuthContext, school_id: UUID, id: UUID) -> SchoolShareRead:
        async with user_uow(self.engine, auth) as uow:
            return await self._school_get(uow.session, auth, school_id, id)

    async def school_download(
        self, auth: AuthContext, school_id: UUID, id: UUID, evidence_id: UUID
    ) -> SignedRead:
        async with user_uow(self.engine, auth) as uow:
            share = await self._school_get(uow.session, auth, school_id, id)
            key = await uow.session.scalar(
                text("SELECT app_private.shared_evidence_key(:school,:share,:evidence)"),
                {"school": school_id, "share": id, "evidence": evidence_id},
            )
            if not key:
                raise NotFound()
            selected_items = share.snapshot.get("evidence")
            if not isinstance(selected_items, list):
                raise NotFound()
            selected = next(
                (
                    item
                    for item in selected_items
                    if isinstance(item, dict) and item.get("id") == str(evidence_id)
                ),
                None,
            )
            if selected is None:
                raise NotFound()
        mime = selected.get("storedMimeType") or ""
        filename = selected.get("originalFilename") or "evidence"
        ttl = self.cfg.evidence.download_url_ttl_s
        url = await self.storage.create_download_url(
            key, ttl, attachment_name=None if str(mime).startswith("image/") else str(filename)
        )
        async with user_uow(self.engine, auth) as uow:
            # Recheck after external I/O: withdrawal takes effect before this returns.
            await self._school_get(uow.session, auth, school_id, id)
            current_key = await uow.session.scalar(
                text("SELECT app_private.shared_evidence_key(:school,:share,:evidence)"),
                {"school": school_id, "share": id, "evidence": evidence_id},
            )
            if current_key != key:
                raise NotFound()
            await uow.session.execute(
                text(
                    "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id,school_id,metadata) VALUES(:actor,'evidence.download_url_issued','evidence',:evidence,:school,CAST(:metadata AS jsonb))"
                ),
                {
                    "actor": auth.user_id,
                    "evidence": evidence_id,
                    "school": school_id,
                    "metadata": json.dumps({"purpose": "school_share", "shareId": str(id)}),
                },
            )
        return SignedRead(url=url, expires_at=datetime.now(UTC) + timedelta(seconds=ttl))
