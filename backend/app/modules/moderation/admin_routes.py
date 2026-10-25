"""Staff moderation queue (07 section 3.4). Every decision is written to
moderation_actions; staff see only reporter-selected evidence, never transcripts,
emails or user ids (subjects are referenced through the report)."""

import logging
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import func, select

from app.contracts import DTO, ActionReceipt
from app.core.errors import DomainError
from app.core.security import idempotency_key, previous_receipt, save_receipt
from app.infrastructure.database.models import User, now
from app.modules.moderation import enforcement
from app.modules.moderation.models import ModerationAction, Report
from app.modules.moderation.staff import Staff, require_staff
from app.modules.social.service import receipt

router = APIRouter(prefix="/admin")
log = logging.getLogger("moodprint")
RESOLUTION = {
    "dismiss": "dismissed",
    "warn": "warned",
    "restrict": "restricted",
    "suspend": "suspended",
}


class EvidenceView(DTO):
    kind: str
    text: str


class AdminReportView(DTO):
    id: UUID
    status: str
    version: int
    reason: str
    created_at: str
    reviewed_at: str | None = None
    resolution: str | None = None
    # Opaque, per-report handles; never user ids or emails.
    subject_ref: str
    reporter_ref: str
    evidence: list[EvidenceView]
    prior_actions: int


class ClaimInput(DTO):
    expected_version: int = Field(ge=1)


class ResolveInput(ClaimInput):
    action: Literal["dismiss", "warn", "restrict", "suspend"]
    days: int | None = Field(default=None, ge=1, le=90)
    note: str = Field(default="", max_length=500)


class LiftInput(DTO):
    note: str = Field(default="", max_length=500)


def subject_ref(report_id: UUID) -> str:
    return f"s-{report_id.hex}"


def report_of(ref: str) -> UUID:
    if not ref.startswith("s-"):
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
    try:
        return UUID(hex=ref[2:])
    except ValueError:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.") from None


async def view(db, row: Report) -> AdminReportView:
    prior = await db.scalar(
        select(func.count())
        .select_from(ModerationAction)
        .where(ModerationAction.subject_id == row.subject_id, ModerationAction.action != "dismiss")
    )
    return AdminReportView(
        id=row.id,
        status=row.status,
        version=row.version,
        reason=row.reason,
        created_at=row.created_at.isoformat(),
        reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
        resolution=row.resolution,
        subject_ref=subject_ref(row.id),
        reporter_ref=f"r-{row.id.hex[:12]}",
        evidence=[
            EvidenceView(kind=item.get("kind", "message"), text=item.get("text", ""))
            for item in (row.evidence or [])
        ],
        prior_actions=prior or 0,
    )


@router.get("/reports", response_model=list[AdminReportView])
async def queue(
    request: Request,
    status: Literal["received", "in_review", "resolved"] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    staff: Staff = Depends(require_staff()),
):
    async with request.app.state.database.require()() as db:
        statement = select(Report).order_by(Report.created_at)
        if status:
            statement = statement.where(Report.status == status)
        else:
            statement = statement.where(Report.status != "resolved")
        rows = (await db.scalars(statement.limit(limit))).all()
        return [await view(db, row) for row in rows]


async def locked_report(db, report_id: UUID, expected: int) -> Report:
    row = await db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if row is None:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
    if row.version != expected or row.status == "resolved":
        raise DomainError(409, "REPORT_CHANGED", "Báo cáo vừa được người khác xử lý.")
    return row


@router.post("/reports/{report_id}/claim", response_model=AdminReportView)
async def claim(
    report_id: UUID, body: ClaimInput, request: Request, staff: Staff = Depends(require_staff())
):
    async with request.app.state.database.require()() as db, db.begin():
        row = await locked_report(db, report_id, body.expected_version)
        if row.status != "received":
            raise DomainError(409, "REPORT_CHANGED", "Báo cáo đang được xem xét.")
        row.status, row.version = "in_review", row.version + 1
        await db.flush()
        return await view(db, row)


@router.post("/reports/{report_id}/resolve", response_model=AdminReportView)
async def resolve(
    report_id: UUID, body: ResolveInput, request: Request, staff: Staff = Depends(require_staff())
):
    if body.action in ("restrict", "suspend") and not body.days:
        raise DomainError(422, "VALIDATION_ERROR", "Hãy chọn số ngày (1–90).")
    key = idempotency_key(request)
    async with request.app.state.database.require()() as db, db.begin():
        moderator = await db.get(User, staff.user_id)
        assert moderator is not None
        operation = f"admin:resolve:{report_id}"
        if await previous_receipt(db, moderator, operation, key, body.model_dump(mode="json")):
            return await view(db, await db.get(Report, report_id))
        peek = await db.get(Report, report_id)
        if peek is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
        # Lock order: the subject's user row before the report and any pair or room.
        subject = await db.scalar(
            select(User).where(User.id == peek.subject_id).with_for_update()
        )
        row = await locked_report(db, report_id, body.expected_version)
        until = now() + timedelta(days=body.days) if body.days else None
        if body.action == "restrict" and until:
            await enforcement.restrict(db, subject, until)
        elif body.action == "suspend" and until:
            await enforcement.suspend(db, subject, until)
        db.add(
            ModerationAction(
                report_id=row.id,
                subject_id=row.subject_id,
                staff_id=staff.user_id,
                action=body.action,
                until_at=until,
                note=body.note,
            )
        )
        row.status, row.resolution = "resolved", RESOLUTION[body.action]
        row.reviewed_at, row.version = now(), row.version + 1
        await db.flush()
        save_receipt(
            db, moderator, operation, key, body.model_dump(mode="json"), {"id": str(row.id)}
        )
        log.info("metric=moderation_action action=%s", body.action)
        return await view(db, row)


@router.post("/users/{ref}/lift", response_model=ActionReceipt)
async def lift(
    ref: str, body: LiftInput, request: Request, staff: Staff = Depends(require_staff("admin"))
):
    async with request.app.state.database.require()() as db, db.begin():
        report = await db.get(Report, report_of(ref))
        if report is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
        subject = await db.scalar(
            select(User).where(User.id == report.subject_id).with_for_update()
        )
        enforcement.lift(subject)
        action = ModerationAction(
            report_id=report.id,
            subject_id=subject.id,
            staff_id=staff.user_id,
            action="lift",
            note=body.note,
        )
        db.add(action)
        await db.flush()
        log.info("metric=moderation_action action=lift")
        return receipt(action.id)
