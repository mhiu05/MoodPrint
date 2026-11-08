"""Incident operations share a case-row lock with plan and sharing mutations."""

import base64
import binascii
import json
from datetime import date, datetime
from uuid import UUID

from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.incidents import (
    CaseDetail,
    CaseQuery,
    CaseSummary,
    EventCreate,
    TimelineEvent,
)
from moodprint_shared.contracts.paging import Page
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.errors import ApiError
from app.core.uow import user_uow
from app.modules.evidence.models import CaseEventEvidence, EvidenceItem
from app.modules.incidents.models import Case, CaseEvent
from app.modules.incidents.schemas import CaseCreate, CasePatch
from app.modules.plans.models import ActionPlanRecord, PlanItemRecord


def not_found() -> ApiError:
    return ApiError("not_found", "Không tìm thấy hồ sơ hoặc mục được yêu cầu.", 404)


async def owned_case(
    session: AsyncSession, auth: AuthContext, case_id: UUID, *, lock=False
) -> Case:
    query = select(Case).where(Case.id == case_id, Case.owner_id == auth.user_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise not_found()
    return row


async def plan_progress(session: AsyncSession, case_ids: list[UUID]) -> dict:
    rows = (
        await session.execute(
            select(
                ActionPlanRecord.case_id,
                ActionPlanRecord.id,
                func.count(PlanItemRecord.id).label("total"),
                func.count(PlanItemRecord.id).filter(PlanItemRecord.status == "done").label("done"),
            )
            .outerjoin(PlanItemRecord, PlanItemRecord.plan_id == ActionPlanRecord.id)
            .where(ActionPlanRecord.case_id.in_(case_ids))
            .group_by(ActionPlanRecord.case_id, ActionPlanRecord.id)
        )
    ).all()
    return {r.case_id: {"id": r.id, "total": r.total, "done": r.done} for r in rows}


def summary(row: Case, progress: dict | None) -> CaseSummary:
    return CaseSummary.model_validate(
        {
            "id": row.id,
            "owner_id": row.owner_id,
            "title": row.title,
            "status": row.status,
            "category_tags": row.category_tags,
            "version": row.version,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "plan_progress": {"done": progress["done"], "total": progress["total"]}
            if progress
            else None,
        }
    )


async def event_dto(session: AsyncSession, row: CaseEvent) -> TimelineEvent:
    evidence = list(
        (
            await session.scalars(
                select(CaseEventEvidence.evidence_id)
                .where(
                    CaseEventEvidence.event_id == row.id, CaseEventEvidence.owner_id == row.owner_id
                )
                .order_by(CaseEventEvidence.evidence_id)
            )
        ).all()
    )
    when = (
        row.occurred_at.isoformat()
        if row.occurred_at
        else row.occurred_on.isoformat()
        if row.occurred_on
        else ""
    )
    return TimelineEvent.model_validate(
        {
            "id": row.id,
            "case_id": row.case_id,
            "when": when,
            "time_precision": row.time_precision,
            "place": row.place,
            "description": row.description,
            "provenance": row.provenance,
            "evidence_ids": evidence,
            "needs_review": row.needs_review,
        }
    )


async def detail(session: AsyncSession, row: Case) -> CaseDetail:
    progress = (await plan_progress(session, [row.id])).get(row.id)
    events = list(
        (
            await session.scalars(
                select(CaseEvent)
                .where(CaseEvent.case_id == row.id, CaseEvent.owner_id == row.owner_id)
                .order_by(
                    func.coalesce(
                        CaseEvent.occurred_at,
                        func.cast(CaseEvent.occurred_on, CaseEvent.occurred_at.type),
                    )
                    .asc()
                    .nulls_last(),
                    CaseEvent.id,
                )
            )
        ).all()
    )
    evidence = list(
        (
            await session.scalars(
                select(EvidenceItem.id)
                .where(
                    EvidenceItem.case_id == row.id,
                    EvidenceItem.owner_id == row.owner_id,
                    EvidenceItem.upload_status != "deleting",
                )
                .order_by(EvidenceItem.created_at, EvidenceItem.id)
            )
        ).all()
    )
    data = summary(row, progress).model_dump()
    data.update(
        {
            key: getattr(row, key)
            for key in (
                "template",
                "perspective",
                "summary",
                "impact_tags",
                "people",
                "place",
                "tried",
                "trusted_person",
            )
        }
    )
    data.update(
        occurred_at=row.occurred_label,
        events=[await event_dto(session, e) for e in events],
        evidence_ids=evidence,
        linked_plan_id=progress["id"] if progress else None,
    )
    return CaseDetail.model_validate(data)


class IncidentService:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def get_case(self, auth: AuthContext, case_id: UUID) -> CaseDetail:
        async with user_uow(self.engine, auth) as uow:
            return await detail(uow.session, await owned_case(uow.session, auth, case_id))

    async def create(self, auth: AuthContext, data: CaseCreate) -> CaseDetail:
        async with user_uow(self.engine, auth) as uow:
            existing = await uow.session.scalar(
                select(Case).where(Case.id == data.id, Case.owner_id == auth.user_id)
            )
            if existing:
                return await detail(uow.session, existing)
            if data.status != "draft" and (not data.title.strip() or not data.summary.strip()):
                raise ApiError(
                    "validation_failed", "Hồ sơ đang theo dõi cần tiêu đề và tóm tắt.", 422
                )
            values = data.model_dump(exclude={"first_event", "evidence_ids", "occurred_at"})
            values.update(owner_id=auth.user_id, occurred_label=data.occurred_at)
            result = await uow.session.scalar(
                insert(Case)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[Case.id])
                .returning(Case.id)
            )
            row = await owned_case(uow.session, auth, data.id, lock=True)
            if result is None:
                return await detail(uow.session, row)
            if data.evidence_ids:
                records = list(
                    (
                        await uow.session.scalars(
                            select(EvidenceItem)
                            .where(
                                EvidenceItem.id.in_(data.evidence_ids),
                                EvidenceItem.owner_id == auth.user_id,
                            )
                            .with_for_update()
                        )
                    ).all()
                )
                if len(records) != len(set(data.evidence_ids)):
                    raise not_found()
                for evidence in records:
                    if (
                        evidence.case_id not in (None, row.id)
                        or evidence.upload_status != "uploaded"
                    ):
                        raise ApiError(
                            "conflict", "Tệp cần tải xong và chưa thuộc hồ sơ khác.", 409
                        )
                    evidence.case_id = row.id
                await uow.session.flush()
            if data.first_event:
                await self._save_event(uow.session, auth, row.id, data.first_event, editing=False)
            return await detail(uow.session, row)

    async def update(self, auth: AuthContext, case_id: UUID, data: CasePatch) -> CaseDetail:
        async with user_uow(self.engine, auth) as uow:
            row = await owned_case(uow.session, auth, case_id, lock=True)
            if row.version != data.version:
                raise ApiError(
                    "version_conflict",
                    "Hồ sơ đã có cập nhật mới. Nội dung nhập vẫn được giữ.",
                    409,
                    details={
                        "latest": (await detail(uow.session, row)).model_dump(
                            mode="json", by_alias=True
                        )
                    },
                )
            changes = data.model_dump(exclude_unset=True, exclude={"version"})
            target = changes.get("status", row.status)
            transitions = {
                "draft": {"draft", "active"},
                "active": {"active", "monitoring", "closed"},
                "monitoring": {"monitoring", "active", "closed"},
                "closed": {"closed", "active"},
            }
            if target not in transitions[row.status]:
                raise ApiError("validation_failed", "Không thể chuyển sang trạng thái này.", 422)
            if target != "draft" and (
                not changes.get("title", row.title).strip()
                or not changes.get("summary", row.summary).strip()
            ):
                raise ApiError("validation_failed", "Hồ sơ cần tiêu đề và tóm tắt.", 422)
            for key, value in changes.items():
                setattr(row, "occurred_label" if key == "occurred_at" else key, value)
            if changes:
                await uow.session.flush()
                await uow.session.refresh(row)
            return await detail(uow.session, row)

    async def delete(self, auth: AuthContext, case_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            row = await owned_case(uow.session, auth, case_id, lock=True)
            await uow.session.delete(row)

    async def list_cases(self, auth: AuthContext, query: CaseQuery) -> Page[CaseSummary]:
        scope = f"cases:{query.sort}:{query.status}:{query.q}"
        key = (
            func.lower(func.app_private.f_unaccent(Case.title))
            if query.sort == "title"
            else Case.updated_at
        )
        statement = select(Case, key.label("sort_key")).where(Case.owner_id == auth.user_id)
        if query.status:
            statement = statement.where(Case.status == query.status)
        if query.q:
            escaped = query.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(
                Case.search_text.like(
                    func.concat("%", func.lower(func.app_private.f_unaccent(escaped)), "%"),
                    escape="\\",
                )
            )
        if query.cursor:
            try:
                raw = json.loads(
                    base64.b64decode(
                        query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
                    )
                )
                if raw["scope"] != scope or raw["owner"] != str(auth.user_id) or raw["v"] != 1:
                    raise ValueError
                at = raw["key"] if query.sort == "title" else datetime.fromisoformat(raw["key"])
                id = UUID(raw["id"])
            except (ValueError, KeyError, TypeError, binascii.Error):
                raise ApiError(
                    "validation_failed", "Con trỏ phân trang không hợp lệ.", 422
                ) from None
            statement = statement.where(
                or_(key > at, and_(key == at, Case.id > id))
                if query.sort == "title"
                else or_(key < at, and_(key == at, Case.id < id))
            )
        statement = (
            statement.order_by(key.asc(), Case.id.asc())
            if query.sort == "title"
            else statement.order_by(key.desc(), Case.id.desc())
        )
        async with user_uow(self.engine, auth) as uow:
            rows = (await uow.session.execute(statement.limit(query.limit + 1))).all()
            page = rows[: query.limit]
            progress = await plan_progress(uow.session, [r[0].id for r in page])
            cursor = None
            if len(rows) > query.limit:
                last, at = page[-1]
                payload = {
                    "v": 1,
                    "scope": scope,
                    "owner": str(auth.user_id),
                    "key": at if isinstance(at, str) else at.isoformat(),
                    "id": str(last.id),
                }
                cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            return Page[CaseSummary](
                items=[summary(r[0], progress.get(r[0].id)) for r in page], next_cursor=cursor
            )

    async def related(self, auth: AuthContext, case_id: UUID) -> list[CaseSummary]:
        async with user_uow(self.engine, auth) as uow:
            current = await owned_case(uow.session, auth, case_id)
            rows = list(
                (
                    await uow.session.scalars(
                        select(Case)
                        .where(Case.owner_id == auth.user_id, Case.id != case_id)
                        .order_by(
                            Case.category_tags.overlap(current.category_tags).desc(),
                            Case.updated_at.desc(),
                            Case.id,
                        )
                        .limit(3)
                    )
                ).all()
            )
            progress = await plan_progress(uow.session, [r.id for r in rows])
            return [summary(r, progress.get(r.id)) for r in rows]

    async def _save_event(
        self,
        session: AsyncSession,
        auth: AuthContext,
        case_id: UUID,
        data: EventCreate,
        *,
        editing: bool,
    ) -> TimelineEvent:
        if data.provenance != "user_entered":
            raise ApiError(
                "forbidden",
                "Mốc mô phỏng hoặc AI chưa được hỗ trợ trong hồ sơ thật.",
                403,
                details={"reason": "fixture_not_allowed"},
            )
        row = await session.scalar(
            select(CaseEvent).where(
                CaseEvent.id == data.id,
                CaseEvent.case_id == case_id,
                CaseEvent.owner_id == auth.user_id,
            )
        )
        if editing and row is None:
            raise not_found()
        if row is not None and not editing:
            return await event_dto(session, row)
        records = list(
            (
                await session.scalars(
                    select(EvidenceItem.id).where(
                        EvidenceItem.id.in_(data.evidence_ids),
                        EvidenceItem.case_id == case_id,
                        EvidenceItem.owner_id == auth.user_id,
                        EvidenceItem.upload_status == "uploaded",
                    )
                )
            ).all()
        )
        if len(records) != len(set(data.evidence_ids)):
            raise not_found()
        values = data.model_dump(exclude={"when", "evidence_ids"})
        values.update(
            owner_id=auth.user_id,
            case_id=case_id,
            occurred_at=datetime.fromisoformat(data.when.replace("Z", "+00:00"))
            if data.time_precision == "exact"
            else None,
            occurred_on=date.fromisoformat(data.when)
            if data.time_precision in ("day", "week")
            else None,
        )
        if row is None:
            created = await session.scalar(
                insert(CaseEvent)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[CaseEvent.id])
                .returning(CaseEvent.id)
            )
            if created is None:
                raise not_found()
            row = await session.scalar(select(CaseEvent).where(CaseEvent.id == data.id))
        else:
            for key, value in values.items():
                setattr(row, key, value)
            await session.execute(
                delete(CaseEventEvidence).where(
                    CaseEventEvidence.event_id == row.id, CaseEventEvidence.owner_id == auth.user_id
                )
            )
        await session.flush()
        for evidence_id in records:
            session.add(
                CaseEventEvidence(event_id=data.id, evidence_id=evidence_id, owner_id=auth.user_id)
            )
        await session.flush()
        assert row is not None
        return await event_dto(session, row)

    async def add_event(self, auth: AuthContext, case_id: UUID, data: EventCreate) -> TimelineEvent:
        async with user_uow(self.engine, auth) as uow:
            await owned_case(uow.session, auth, case_id, lock=True)
            result = await self._save_event(uow.session, auth, case_id, data, editing=False)
            await uow.session.execute(
                update(Case)
                .where(Case.id == case_id, Case.owner_id == auth.user_id)
                .values(updated_at=func.now())
            )
            return result

    async def update_event(
        self, auth: AuthContext, case_id: UUID, data: EventCreate
    ) -> TimelineEvent:
        async with user_uow(self.engine, auth) as uow:
            await owned_case(uow.session, auth, case_id, lock=True)
            result = await self._save_event(uow.session, auth, case_id, data, editing=True)
            await uow.session.execute(
                update(Case)
                .where(Case.id == case_id, Case.owner_id == auth.user_id)
                .values(updated_at=func.now())
            )
            return result

    async def remove_event(self, auth: AuthContext, case_id: UUID, event_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await owned_case(uow.session, auth, case_id, lock=True)
            result = await uow.session.scalar(
                delete(CaseEvent)
                .where(
                    CaseEvent.id == event_id,
                    CaseEvent.case_id == case_id,
                    CaseEvent.owner_id == auth.user_id,
                )
                .returning(CaseEvent.id)
            )
            if result is None:
                raise not_found()
            await uow.session.execute(
                update(Case)
                .where(Case.id == case_id, Case.owner_id == auth.user_id)
                .values(updated_at=func.now())
            )
