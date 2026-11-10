import type { PlanPort } from "../ports";
import { useWorkspaceStore } from "../../app/store";
import { ApiError, type ApiClient } from "./client";
import { commitForOwner, currentOwner, jsonBody } from "./cache";
import { mapPlan, serializePlan, type PlanDTO } from "./mappers";

export function createPlanPort(api: ApiClient): PlanPort {
  const cache = (owner: string | null, data: PlanDTO) => {
    const plan = mapPlan(data);
    commitForOwner(owner, (state) => state.putPlan(plan));
    return plan;
  };
  return {
    async save(item) {
      const owner = currentOwner();
      try {
        return cache(
          owner,
          await api(
            `/v1/cases/${item.caseId}/plan`,
            jsonBody("PUT", serializePlan(item)),
          ),
        );
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.code === "version_conflict" &&
          error.details.latest
        )
          error.details.latest = cache(owner, error.details.latest as PlanDTO);
        throw error;
      }
    },
    async getForCase(id) {
      const owner = currentOwner();
      try {
        return cache(owner, await api(`/v1/cases/${id}/plan`));
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          commitForOwner(owner, () =>
            useWorkspaceStore.setState((state) => ({
              plans: state.plans.filter((plan) => plan.caseId !== id),
              cases: state.cases.map((item) =>
                item.id === id ? { ...item, linkedPlanId: undefined } : item,
              ),
            })),
          );
          return null;
        }
        throw error;
      }
    },
    async active() {
      const owner = currentOwner();
      try {
        const data = await api<PlanDTO | null>("/v1/plans/active");
        return data ? cache(owner, data) : null;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    async setItemStatus(planId, itemId, status, notes) {
      const owner = currentOwner();
      return cache(
        owner,
        await api(
          `/v1/plans/${planId}/items/${itemId}`,
          jsonBody("PATCH", {
            status,
            ...(notes === undefined ? {} : { notes }),
          }),
        ),
      );
    },
  };
}
