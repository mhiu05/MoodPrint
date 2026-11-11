from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.base import FrozenDTO
from safevoice_shared.contracts.plans import ActionPlan, ItemStatus, PlanUpsert

from app.core.auth import get_auth
from app.core.errors import ApiError
from app.modules.plans.service import ActionPlanService

router = APIRouter(prefix="/v1", tags=["plans"])


def service(request: Request) -> ActionPlanService:
    return ActionPlanService(request.app.state.engine)


class PlanWrite(PlanUpsert):
    version: int | None = Field(default=None, ge=1)


class ItemPatch(FrozenDTO):
    status: ItemStatus | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Supply a status or notes")
        return self


@router.get("/cases/{id}/plan", response_model=ActionPlan)
async def get_plan(
    id: UUID, auth: AuthContext = Depends(get_auth), plans: ActionPlanService = Depends(service)
):
    plan = await plans.get_for_case(auth, id)
    if plan is None:
        raise ApiError("not_found", "Hồ sơ chưa có kế hoạch.", 404)
    return plan


@router.put("/cases/{id}/plan", response_model=ActionPlan)
async def put_plan(
    id: UUID,
    data: PlanWrite,
    auth: AuthContext = Depends(get_auth),
    plans: ActionPlanService = Depends(service),
):
    return await plans.upsert(
        auth,
        id,
        PlanUpsert.model_validate(data.model_dump(exclude={"version"})),
        expected_version=data.version,
    )


@router.get("/plans/active", response_model=ActionPlan | None)
async def active_plan(
    auth: AuthContext = Depends(get_auth), plans: ActionPlanService = Depends(service)
):
    return await plans.active(auth)


@router.patch("/plans/{plan_id}/items/{item_id}", response_model=ActionPlan)
async def update_item(
    plan_id: UUID,
    item_id: UUID,
    data: ItemPatch,
    auth: AuthContext = Depends(get_auth),
    plans: ActionPlanService = Depends(service),
):
    return await plans.patch_item(auth, plan_id, item_id, status=data.status, notes=data.notes)
