import json
import time
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.ai.schemas import MemoryDTO
from app.contracts import MoodDTO, PrivateItemDTO
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import (
    AgeDeclaration,
    AuthSession,
    Memory,
    Mood,
    PrivateItem,
    now,
)
from app.modules.users.models import DataJob
from app.modules.users.schemas import DataJobView, DeletionInput, ExportInput

router = APIRouter()


@router.post("/data-deletions", response_model=DataJobView, status_code=202)
async def deletion(body: DeletionInput, request: Request, actor: Actor = Depends(require_actor)):
    if body.scope == "account":
        raise DomainError(
            503,
            "ACCOUNT_DELETION_UNAVAILABLE",
            "Xóa toàn bộ tài khoản chưa sẵn sàng. Bạn vẫn có thể xóa dữ liệu riêng trong ứng dụng.",
        )
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor, eligible=False) as (db, user):
        old = await previous_receipt(db, user, "data:delete", key, payload)
        if old:
            return DataJobView.model_validate(await db.get(DataJob, UUID(old["resourceId"])))
        if user.deletion_pending or user.data_version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Dữ liệu đã thay đổi hoặc đang được xóa.")
        if body.scope == "account":
            session = await db.get(AuthSession, actor.session_id)
            if session.reauthenticated_at < now() - timedelta(minutes=5):
                raise DomainError(
                    401, "REAUTH_REQUIRED", "Hãy đăng nhập lại trước khi yêu cầu xóa tài khoản."
                )
            user.status = "deleting"
            user.auth_version += 1
        user.deletion_pending = True
        user.data_version += 1
        row = DataJob(user_id=user.id, kind="deletion", scope=body.scope)
        db.add(row)
        await db.flush()
        save_receipt(db, user, "data:delete", key, payload, {"resourceId": str(row.id)})
        result = DataJobView.model_validate(row)
    request.app.state.ai.invalidate(str(actor.user_id))
    request.app.state.exports = {
        key: value
        for key, value in request.app.state.exports.items()
        if value["owner"] != actor.user_id
    }
    return result


@router.get("/data-deletions/{job_id}", response_model=DataJobView)
async def deletion_status(job_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor, eligible=False) as (db, user):
        row = await db.get(DataJob, job_id)
        if not row or row.user_id != user.id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy yêu cầu dữ liệu.")
        return DataJobView.model_validate(row)


@router.post("/exports", response_model=DataJobView, status_code=201)
async def export(body: ExportInput, request: Request, actor: Actor = Depends(require_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        session = await db.get(AuthSession, actor.session_id)
        if session.reauthenticated_at < now() - timedelta(minutes=5):
            raise DomainError(401, "REAUTH_REQUIRED", "Hãy đăng nhập lại trước khi xuất dữ liệu.")
        old = await previous_receipt(db, user, "data:export", key, payload)
        if old:
            row = await db.get(DataJob, UUID(old["resourceId"]))
            if row.id not in request.app.state.exports:
                raise DomainError(
                    410, "EXPORT_EXPIRED", "Bản xuất đã hết hạn. Hãy tạo yêu cầu mới."
                )
            return DataJobView.model_validate(row)
        result: dict[str, object] = {}
        if "account" in body.scopes:
            declaration = await db.get(AgeDeclaration, user.id)
            result["account"] = {
                "birthYear": declaration.birth_year if declaration else None,
                "ageBand": user.age_band,
                "policyVersion": declaration.policy_version if declaration else None,
                "declaredAt": declaration.declared_at.isoformat() if declaration else None,
            }
        for scope, model, schema, target in (
            ("private_items", PrivateItem, PrivateItemDTO, "privateItems"),
            ("memories", Memory, MemoryDTO, "memories"),
            ("moods", Mood, MoodDTO, "moods"),
        ):
            if scope not in body.scopes:
                continue
            statement = select(model).where(model.user_id == user.id)
            if model is PrivateItem:
                statement = statement.where(PrivateItem.status != "deleted")
            if model is Memory:
                statement = statement.where(Memory.status == "active")
            if model is Mood:
                today = datetime.now(ZoneInfo(user.timezone)).date()
                statement = statement.where(
                    Mood.local_date >= today - timedelta(days=89), Mood.local_date <= today
                )
            rows = (await db.scalars(statement.limit(1001))).all()
            if len(rows) > 1000:
                raise DomainError(
                    503,
                    "EXPORT_TOO_LARGE",
                    "Phạm vi xuất quá lớn. Hãy yêu cầu hỗ trợ xuất dữ liệu.",
                )
            result[target] = [
                schema.model_validate(item).model_dump(mode="json", by_alias=True) for item in rows
            ]
        if len(json.dumps(result).encode()) > 2 * 1024 * 1024:
            raise DomainError(503, "EXPORT_TOO_LARGE", "Phạm vi xuất quá lớn.")
        active_exports = [
            item
            for item in request.app.state.exports.values()
            if item["expires"] > time.monotonic()
        ]
        if (
            len(active_exports) >= 32
            or sum(item["owner"] == actor.user_id for item in active_exports) >= 2
        ):
            raise DomainError(
                429, "EXPORT_LIMIT", "Hãy tải bản xuất hiện có hoặc chờ bản xuất hết hạn."
            )
        row = DataJob(user_id=user.id, kind="export", scope=",".join(body.scopes), status="ready")
        db.add(row)
        await db.flush()
        save_receipt(db, user, "data:export", key, payload, {"resourceId": str(row.id)})
        identity, version = row.id, user.data_version
        view = DataJobView.model_validate(row)
    request.app.state.exports[identity] = {
        "owner": actor.user_id,
        "session": actor.session_id,
        "version": version,
        "expires": time.monotonic() + 900,
        "data": result,
    }
    return view


@router.get("/exports/{job_id}", response_model=DataJobView)
async def export_status(job_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        row = await db.get(DataJob, job_id)
        if not row or row.user_id != user.id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy bản xuất.")
        return DataJobView.model_validate(row)


@router.get("/exports/{job_id}/download")
async def download(job_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        row = await db.get(DataJob, job_id)
        if not row or row.user_id != user.id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy bản xuất.")
        item = request.app.state.exports.get(job_id)
        if (
            not item
            or item["expires"] <= time.monotonic()
            or item["session"] != actor.session_id
            or item["version"] != user.data_version
        ):
            raise DomainError(
                410, "EXPORT_EXPIRED", "Bản xuất đã hết hạn hoặc dữ liệu đã thay đổi."
            )
        request.app.state.exports.pop(job_id)
        row.status = "downloaded"
        row.version += 1
        payload = item["data"]
    return JSONResponse(
        payload,
        headers={
            "Content-Disposition": "attachment; filename=moodprint-data.json",
            "Cache-Control": "no-store",
        },
    )
