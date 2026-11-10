"""Atomic plan replacement and Home checklist updates with optimistic versions."""

from uuid import UUID

from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.plans import ActionPlan, ItemStatus, PlanUpsert
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.errors import ApiError
from app.core.uow import user_uow
from app.modules.incidents.models import Case
from app.modules.plans.models import ActionPlanRecord, PlanItemRecord


def not_found() -> ApiError:
    return ApiError("not_found", "Không tìm thấy kế hoạch hoặc mục được yêu cầu.", 404)


async def plan_dto(session: AsyncSession, row: ActionPlanRecord) -> ActionPlan:
    items = list(
        (
            await session.scalars(
                select(PlanItemRecord)
                .where(PlanItemRecord.plan_id == row.id, PlanItemRecord.owner_id == row.owner_id)
                .order_by(PlanItemRecord.position)
            )
        ).all()
    )
    data = {
        key: getattr(row, key)
        for key in (
            "id",
            "case_id",
            "owner_id",
            "goal",
            "chosen_option_id",
            "status",
            "next_review_date",
            "outcome_notes",
            "version",
            "created_at",
            "updated_at",
        )
    }
    data["items"] = [
        {
            key: getattr(item, key)
            for key in ("id", "label", "status", "notes", "priority", "reason")
        }
        for item in items
    ]
    return ActionPlan.model_validate(data)


class ActionPlanService:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def _case(self, session: AsyncSession, auth: AuthContext, case_id: UUID, *, lock=False):
        query = select(Case).where(Case.id == case_id, Case.owner_id == auth.user_id)
        case = await session.scalar(query.with_for_update() if lock else query)
        if case is None:
            raise not_found()
        return case

    async def get_for_case(self, auth: AuthContext, case_id: UUID) -> ActionPlan | None:
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id)
            row = await uow.session.scalar(
                select(ActionPlanRecord).where(
                    ActionPlanRecord.case_id == case_id, ActionPlanRecord.owner_id == auth.user_id
                )
            )
            return await plan_dto(uow.session, row) if row else None

    async def active(self, auth: AuthContext) -> ActionPlan | None:
        async with user_uow(self.engine, auth) as uow:
            row = await uow.session.scalar(
                select(ActionPlanRecord)
                .where(
                    ActionPlanRecord.owner_id == auth.user_id,
                    ActionPlanRecord.status != "completed",
                )
                .order_by(ActionPlanRecord.updated_at.desc(), ActionPlanRecord.id)
                .limit(1)
            )
            return await plan_dto(uow.session, row) if row else None

    async def upsert(
        self, auth: AuthContext, case_id: UUID, data: PlanUpsert, *, expected_version: int | None
    ) -> ActionPlan:
        if data.status != "draft" and not data.goal.strip():
            raise ApiError("validation_failed", "Kế hoạch cần có mục tiêu.", 422)
        if data.status == "completed" and (
            not data.items or any(item.status != "done" for item in data.items)
        ):
            raise ApiError(
                "validation_failed", "Hoàn thành tất cả các bước trước khi kết thúc kế hoạch.", 422
            )
        if len({item.id for item in data.items}) != len(data.items):
            raise ApiError("validation_failed", "Mỗi bước cần có định danh riêng.", 422)
        async with user_uow(self.engine, auth) as uow:
            await self._case(uow.session, auth, case_id, lock=True)
            row = await uow.session.scalar(
                select(ActionPlanRecord)
                .where(
                    ActionPlanRecord.case_id == case_id, ActionPlanRecord.owner_id == auth.user_id
                )
                .with_for_update()
            )
            if row:
                if expected_version != row.version:
                    raise ApiError(
                        "version_conflict",
                        "Kế hoạch đã có cập nhật mới. Nội dung nhập vẫn được giữ.",
                        409,
                        details={
                            "latest": (await plan_dto(uow.session, row)).model_dump(
                                mode="json", by_alias=True
                            )
                        },
                    )
                if row.id != data.id:
                    raise ApiError("conflict", "Hồ sơ này đã có một kế hoạch.", 409)
            else:
                if expected_version is not None:
                    raise ApiError("version_conflict", "Kế hoạch đã thay đổi.", 409)
                # IDs from a foreign owner must never reveal the existing record.
                from sqlalchemy.dialects.postgresql import insert

                inserted = await uow.session.scalar(
                    insert(ActionPlanRecord)
                    .values(
                        id=data.id,
                        case_id=case_id,
                        owner_id=auth.user_id,
                        **data.model_dump(exclude={"id", "items"}),
                    )
                    .on_conflict_do_nothing(index_elements=[ActionPlanRecord.id])
                    .returning(ActionPlanRecord.id)
                )
                if inserted is None:
                    raise not_found()
                row = await uow.session.scalar(
                    select(ActionPlanRecord).where(
                        ActionPlanRecord.id == inserted, ActionPlanRecord.owner_id == auth.user_id
                    )
                )
                assert row is not None
            if expected_version is not None:
                # Explicit UPDATE ensures every accepted replacement bumps the
                # version, including a reorder with unchanged scalar fields.
                await uow.session.execute(
                    update(ActionPlanRecord)
                    .where(ActionPlanRecord.id == row.id, ActionPlanRecord.owner_id == auth.user_id)
                    .values(**data.model_dump(exclude={"id", "items"}))
                )
            await uow.session.execute(
                delete(PlanItemRecord).where(
                    PlanItemRecord.plan_id == row.id, PlanItemRecord.owner_id == auth.user_id
                )
            )
            # Conflicting IDs are validated before insertion so no foreign plan's
            # item can be moved into this plan through an upsert.
            if data.items:
                conflicts = await uow.session.scalar(
                    select(PlanItemRecord.id)
                    .where(PlanItemRecord.id.in_([item.id for item in data.items]))
                    .limit(1)
                )
                if conflicts:
                    raise ApiError("conflict", "Bước này đã thuộc kế hoạch khác.", 409)
            for position, item in enumerate(data.items):
                from sqlalchemy.dialects.postgresql import insert

                inserted_item = await uow.session.scalar(
                    insert(PlanItemRecord)
                    .values(
                        plan_id=row.id,
                        owner_id=auth.user_id,
                        position=position,
                        **item.model_dump(),
                    )
                    .on_conflict_do_nothing(index_elements=[PlanItemRecord.id])
                    .returning(PlanItemRecord.id)
                )
                if inserted_item is None:
                    raise not_found()
            await uow.session.flush()
            await uow.session.refresh(row)
            return await plan_dto(uow.session, row)

    async def set_item_status(
        self,
        auth: AuthContext,
        plan_id: UUID,
        item_id: UUID,
        status: ItemStatus,
        *,
        notes: str | None = None,
    ) -> ActionPlan:
        return await self.patch_item(auth, plan_id, item_id, status=status, notes=notes)

    async def patch_item(
        self,
        auth: AuthContext,
        plan_id: UUID,
        item_id: UUID,
        *,
        status: ItemStatus | None = None,
        notes: str | None = None,
    ) -> ActionPlan:
        async with user_uow(self.engine, auth) as uow:
            initial = await uow.session.scalar(
                select(ActionPlanRecord).where(
                    ActionPlanRecord.id == plan_id, ActionPlanRecord.owner_id == auth.user_id
                )
            )
            if initial is None:
                raise not_found()
            await self._case(uow.session, auth, initial.case_id, lock=True)
            row = await uow.session.scalar(
                select(ActionPlanRecord)
                .where(ActionPlanRecord.id == plan_id, ActionPlanRecord.owner_id == auth.user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if row is None:
                raise not_found()
            if row.status == "completed" and status is not None and status != "done":
                raise ApiError(
                    "validation_failed",
                    "Mở lại kế hoạch trước khi thay đổi bước đã hoàn thành.",
                    422,
                )
            item = await uow.session.scalar(
                select(PlanItemRecord).where(
                    PlanItemRecord.id == item_id,
                    PlanItemRecord.plan_id == plan_id,
                    PlanItemRecord.owner_id == auth.user_id,
                )
            )
            if item is None:
                raise not_found()
            if status is not None:
                item.status = status
            if notes is not None:
                item.notes = notes
            await uow.session.execute(
                update(ActionPlanRecord)
                .where(ActionPlanRecord.id == plan_id, ActionPlanRecord.owner_id == auth.user_id)
                .values(status=row.status)
            )
            await uow.session.flush()
            await uow.session.refresh(row)
            return await plan_dto(uow.session, row)
