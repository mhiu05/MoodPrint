"""Original evidence lifecycle. Storage capabilities are issued outside user transactions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound, QuotaExceeded
from moodprint_shared.contracts.evidence import (
    DerivativeCreate,
    EvidenceDerivative,
    EvidenceMeta,
    ReadPurpose,
    SignedRead,
)
from moodprint_shared.contracts.paging import Page
from sqlalchemy import text

from app.core.errors import ApiError
from app.core.paging import decode_cursor, encode_cursor
from app.core.uow import user_uow
from app.modules.evidence.keys import original_key
from app.modules.evidence.schemas import (
    EvidencePatch,
    NoteCreate,
    UploadCreate,
    UploadInfo,
    UploadReply,
)


def meta(row):
    return EvidenceMeta.model_validate({k: row[k] for k in EvidenceMeta.model_fields})


def kind_for(mime):
    if mime and mime.split("/", 1)[0] in {"image", "audio", "video"}:
        return mime.split("/", 1)[0]
    return "document" if mime in {"application/pdf", "text/plain"} else "other"


class EvidenceService:
    def __init__(self, engine, storage, cfg: AppConfig | None = None):
        self.engine, self.storage, self.cfg = engine, storage, cfg or AppConfig()

    async def _get(self, session, auth, id, *, lock=False):
        row = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM app.evidence_items WHERE id=:id AND owner_id=:owner"
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

    async def _case(self, session, auth, id):
        if id is not None and not await session.scalar(
            text("SELECT id FROM app.cases WHERE id=:id AND owner_id=:owner FOR KEY SHARE"),
            {"id": id, "owner": auth.user_id},
        ):
            raise NotFound()

    async def get(self, auth: AuthContext, evidence_id: UUID) -> EvidenceMeta:
        async with user_uow(self.engine, auth) as uow:
            return meta(await self._get(uow.session, auth, evidence_id))

    async def list(
        self, auth: AuthContext, *, case_id=None, unlinked=False, limit=50, cursor=None
    ) -> Page[EvidenceMeta]:
        scope = f"evidence:{case_id or ''}:{unlinked}"
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        where = "owner_id=:owner AND upload_status<>'deleting'"
        params = {"owner": auth.user_id, "limit": limit + 1}
        if case_id:
            where += " AND case_id=:case"
            params["case"] = case_id
        if unlinked:
            where += " AND case_id IS NULL"
        if position:
            where += " AND (created_at,id)>(:at,:id)"
            params.update(at=position.at, id=position.id)
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id)
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.evidence_items WHERE {where} ORDER BY created_at,id LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        items = [meta(row) for row in rows[:limit]]
        return Page[EvidenceMeta](
            items=items,
            next_cursor=encode_cursor(
                scope=scope, owner=auth.user_id, at=items[-1].created_at, id=items[-1].id
            )
            if len(rows) > limit
            else None,
        )

    async def list_for_case(self, auth: AuthContext, case_id: UUID) -> list[EvidenceMeta]:
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id)
            rows = (
                await uow.session.execute(
                    text(
                        "SELECT * FROM app.evidence_items WHERE owner_id=:owner AND case_id=:case AND upload_status='uploaded' ORDER BY created_at,id"
                    ),
                    {"owner": auth.user_id, "case": case_id},
                )
            ).mappings()
            return [meta(row) for row in rows]

    async def _upload_reply(self, row) -> UploadReply:
        if row["upload_status"] not in {"pending", "uploaded"} or row["kind"] == "text_note":
            raise ApiError("conflict", "Lần tải lên này không còn hoạt động.", 409)
        signed = await self.storage.create_upload_token(row["storage_key"])
        upload = UploadInfo(**{k: getattr(signed, k) for k in UploadInfo.model_fields})
        return UploadReply(evidence=meta(row), upload=upload)

    async def init_upload(self, auth: AuthContext, data: UploadCreate) -> UploadReply:
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "evidence:" + str(auth.user_id)},
            )
            existing = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.evidence_items WHERE id=:id AND owner_id=:owner"),
                        {"id": data.id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                row = dict(existing)
            else:
                if data.byte_size > self.cfg.evidence.max_object_bytes:
                    raise ApiError("object_too_large", "Tệp vượt dung lượng cho phép.", 413)
                await self._case(uow.session, auth, data.case_id)
                usage = (
                    (
                        await uow.session.execute(
                            text("""SELECT
                  coalesce(sum(CASE WHEN upload_status='uploaded' THEN coalesce(byte_size,0)
                    WHEN purged_at IS NULL THEN greatest(coalesce(byte_size,0),coalesce(expected_byte_size,0)) ELSE 0 END),0) AS used,
                  count(*) FILTER(WHERE upload_status='pending') AS pending,
                  app_private.own_upload_init_count() AS recent
                  FROM app.evidence_items WHERE owner_id=:owner"""),
                            {"owner": auth.user_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                if (
                    usage["used"] + data.byte_size > self.cfg.evidence.user_quota_bytes
                    or usage["pending"] >= self.cfg.evidence.pending_uploads_per_user
                ):
                    raise QuotaExceeded()
                if usage["recent"] >= self.cfg.evidence.upload_rate_per_hour:
                    raise ApiError(
                        "rate_limited",
                        "Bạn đã bắt đầu nhiều lần tải lên. Vui lòng thử lại sau.",
                        429,
                    )
                key = original_key(auth.user_id, data.id, data.mime_type)
                await uow.session.execute(
                    text("""INSERT INTO app.evidence_items
                  (id,owner_id,case_id,kind,origin,storage_bucket,storage_key,original_filename,declared_mime_type,expected_byte_size,client_sha256,shown_timestamp,captured_at_label,upload_status)
                  VALUES(:id,:owner,:case_id,:kind,'user_upload',:bucket,:key,:filename,:mime_type,:byte_size,:sha256,:shown_timestamp,:captured_at_label,'pending') ON CONFLICT(id) DO NOTHING"""),
                    {
                        **data.model_dump(),
                        "owner": auth.user_id,
                        "bucket": self.cfg.evidence.bucket,
                        "key": key,
                        "kind": kind_for(data.mime_type),
                    },
                )
                row = dict(await self._get(uow.session, auth, data.id))
                await uow.session.execute(
                    text(
                        "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id) VALUES(:owner,'evidence.upload_initialized','evidence',:id)"
                    ),
                    {"owner": auth.user_id, "id": data.id},
                )
        return await self._upload_reply(row)

    async def upload_token(self, auth: AuthContext, evidence_id: UUID) -> UploadReply:
        async with user_uow(self.engine, auth) as uow:
            row = dict(await self._get(uow.session, auth, evidence_id))
            if row["upload_status"] != "pending":
                raise ApiError("conflict", "Lần tải lên này không còn chờ hoàn tất.", 409)
        return await self._upload_reply(row)

    async def complete(self, auth: AuthContext, evidence_id: UUID) -> EvidenceMeta:
        async with user_uow(self.engine, auth) as uow:
            row = dict(await self._get(uow.session, auth, evidence_id))
            if row["upload_status"] == "uploaded":
                return meta(row)
            if row["upload_status"] != "pending":
                raise ApiError("conflict", "Lần tải lên này không thể hoàn tất.", 409)
        info = await self.storage.object_info(row["storage_key"])
        if info is None:
            raise ApiError("conflict", "Tệp chưa tải lên hoàn tất. Vui lòng thử lại.", 409)
        mismatch = (
            info.byte_size != row["expected_byte_size"]
            or info.byte_size > self.cfg.evidence.max_object_bytes
        )
        async with user_uow(self.engine, auth) as uow:
            current = await self._get(uow.session, auth, evidence_id, lock=True)
            if current["upload_status"] == "uploaded":
                return meta(current)
            if current["upload_status"] != "pending":
                raise ApiError("conflict", "Lần tải lên này không thể hoàn tất.", 409)
            await uow.session.execute(
                text(
                    """UPDATE app.evidence_items SET byte_size=:size,stored_mime_type=:mime,storage_etag=:etag,upload_status=:status WHERE id=:id AND owner_id=:owner"""
                ),
                {
                    "size": info.byte_size,
                    "mime": info.mime_type or "application/octet-stream",
                    "etag": info.etag,
                    "status": "failed" if mismatch else "uploaded",
                    "id": evidence_id,
                    "owner": auth.user_id,
                },
            )
            completed = meta(await self._get(uow.session, auth, evidence_id))
        if mismatch:
            raise ApiError(
                "validation_failed", "Dung lượng tệp không khớp với lần tải lên đã khai báo.", 422
            )
        return completed

    async def create_note(self, auth: AuthContext, data: NoteCreate) -> EvidenceMeta:
        async with user_uow(self.engine, auth) as uow:
            existing = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.evidence_items WHERE id=:id AND owner_id=:owner"),
                        {"id": data.id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return meta(existing)
            await self._case(uow.session, auth, data.case_id)
            await uow.session.execute(
                text("""INSERT INTO app.evidence_items(id,owner_id,case_id,kind,origin,original_text,shown_timestamp,captured_at_label,upload_status)
              VALUES(:id,:owner,:case_id,'text_note','user_entered',:original_text,:shown_timestamp,:captured_at_label,'uploaded') ON CONFLICT(id) DO NOTHING"""),
                {**data.model_dump(), "owner": auth.user_id},
            )
            return meta(await self._get(uow.session, auth, data.id))

    async def patch(
        self, auth: AuthContext, evidence_id: UUID, data: EvidencePatch
    ) -> EvidenceMeta:
        changes = data.model_dump(exclude_unset=True)
        async with user_uow(self.engine, auth) as uow:
            await self._get(uow.session, auth, evidence_id)
            if changes:
                assignments = ",".join(f"{key}=:{key}" for key in changes)
                await uow.session.execute(
                    text(
                        f"UPDATE app.evidence_items SET {assignments} WHERE id=:id AND owner_id=:owner"
                    ),
                    {**changes, "id": evidence_id, "owner": auth.user_id},
                )
            return meta(await self._get(uow.session, auth, evidence_id))

    async def open_read_url(
        self, auth: AuthContext, evidence_id: UUID, purpose: ReadPurpose
    ) -> SignedRead:
        async with user_uow(self.engine, auth) as uow:
            row = dict(await self._get(uow.session, auth, evidence_id))
            if row["upload_status"] != "uploaded" or not row["storage_key"]:
                raise ApiError("conflict", "Tệp chưa sẵn sàng để tải xuống.", 409)
        mime = row["stored_mime_type"] or ""
        attachment = None if mime.startswith("image/") else row["original_filename"] or "evidence"
        ttl = self.cfg.evidence.download_url_ttl_s
        url = await self.storage.create_download_url(
            row["storage_key"], ttl, attachment_name=attachment
        )
        async with user_uow(self.engine, auth) as uow:
            current = await self._get(uow.session, auth, evidence_id)
            if current["upload_status"] != "uploaded":
                raise NotFound()
            await uow.session.execute(
                text("""INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id,metadata)
              VALUES(:owner,'evidence.download_url_issued','evidence',:id,CAST(:metadata AS jsonb))"""),
                {
                    "owner": auth.user_id,
                    "id": evidence_id,
                    "metadata": json.dumps({"purpose": purpose}),
                },
            )
        return SignedRead(url=url, expires_at=datetime.now(UTC) + timedelta(seconds=ttl))

    async def link(self, auth: AuthContext, case_id: UUID, evidence_id: UUID) -> EvidenceMeta:
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id)
            row = await self._get(uow.session, auth, evidence_id, lock=True)
            if row["upload_status"] == "deleting" or row["case_id"] not in (None, case_id):
                raise ApiError("conflict", "Nguồn đã thuộc hồ sơ khác hoặc đang xóa.", 409)
            await uow.session.execute(
                text(
                    "UPDATE app.evidence_items SET case_id=:case WHERE id=:id AND owner_id=:owner"
                ),
                {"case": case_id, "id": evidence_id, "owner": auth.user_id},
            )
            return meta(await self._get(uow.session, auth, evidence_id))

    async def unlink(self, auth: AuthContext, case_id: UUID, evidence_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id)
            row = await self._get(uow.session, auth, evidence_id, lock=True)
            if row["case_id"] != case_id:
                raise NotFound()
            await uow.session.execute(
                text(
                    "DELETE FROM app.case_event_evidence WHERE evidence_id=:id AND owner_id=:owner"
                ),
                {"id": evidence_id, "owner": auth.user_id},
            )
            await uow.session.execute(
                text("UPDATE app.evidence_items SET case_id=NULL WHERE id=:id AND owner_id=:owner"),
                {"id": evidence_id, "owner": auth.user_id},
            )

    async def delete(self, auth: AuthContext, evidence_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            row = await self._get(uow.session, auth, evidence_id, lock=True)
            keys = list(
                (
                    await uow.session.execute(
                        text(
                            "SELECT storage_key FROM app.evidence_derivatives WHERE evidence_id=:id AND owner_id=:owner AND storage_key IS NOT NULL"
                        ),
                        {"id": evidence_id, "owner": auth.user_id},
                    )
                ).scalars()
            )
            if row["storage_key"]:
                keys.append(row["storage_key"])
            if row["upload_status"] != "deleting":
                await uow.session.execute(
                    text(
                        "UPDATE app.evidence_items SET upload_status='deleting' WHERE id=:id AND owner_id=:owner"
                    ),
                    {"id": evidence_id, "owner": auth.user_id},
                )
        await self.storage.delete(keys)
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text(
                    "DELETE FROM app.evidence_items WHERE id=:id AND owner_id=:owner AND upload_status='deleting'"
                ),
                {"id": evidence_id, "owner": auth.user_id},
            )

    async def add_derivative(
        self, auth: AuthContext, evidence_id: UUID, data: DerivativeCreate
    ) -> EvidenceDerivative:
        if data.storage_key:
            prefix = f"users/{auth.user_id}/derived/{evidence_id}/{data.kind}/{data.id}."
            if (
                not data.storage_key.startswith(prefix)
                or ".." in data.storage_key
                or "\\" in data.storage_key
                or "/" in data.storage_key[len(prefix) :]
            ):
                raise ApiError("validation_failed", "Đường dẫn bản dẫn xuất không hợp lệ.", 422)
        async with user_uow(self.engine, auth) as uow:
            row = await self._get(uow.session, auth, evidence_id, lock=True)
            if row["upload_status"] != "uploaded":
                raise ApiError("conflict", "Nguồn chưa sẵn sàng.", 409)
            await uow.session.execute(
                text("""INSERT INTO app.evidence_derivatives(id,evidence_id,owner_id,kind,storage_key,content,generator,generator_version,source_sha256)
              VALUES(:id,:evidence,:owner,:kind,:storage_key,CAST(:content AS jsonb),:generator,:generator_version,:source_sha256) ON CONFLICT(id) DO NOTHING"""),
                {
                    **data.model_dump(),
                    "content": json.dumps(data.content),
                    "evidence": evidence_id,
                    "owner": auth.user_id,
                },
            )
            result = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.evidence_derivatives WHERE id=:id AND evidence_id=:evidence AND owner_id=:owner"
                        ),
                        {"id": data.id, "evidence": evidence_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if result is None:
                raise NotFound()
            return EvidenceDerivative.model_validate(
                {k: result[k] for k in EvidenceDerivative.model_fields}
            )
