import { beforeEach, describe, expect, it } from "vitest";
import { useWorkspaceStore } from "../../app/store";
import { createCasePort } from "./incidents";
import { createPlanPort } from "./plans";
import { ApiError, type ApiClient } from "./client";
import { seedCases, seedPlans } from "../../mocks/data/seed";

describe("real domain adapters", () => {
  it("links a newly uploaded attachment before saving event references to it", async () => {
    const eventId = crypto.randomUUID(),
      evidenceId = crypto.randomUUID();
    const original = {
      ...seedCases[0],
      id: crypto.randomUUID(),
      ownerId: "owner",
      version: 1,
      evidenceIds: [],
      events: [{ ...seedCases[0].events[0], id: eventId, evidenceIds: [] }],
    };
    useWorkspaceStore.getState().putCase(original);
    const changed = {
      ...original,
      events: original.events.map((event) => ({
        ...event,
        evidenceIds: [evidenceId],
      })),
      evidenceIds: [evidenceId],
    };
    let linked = false;
    const api: ApiClient = async <T>(path: string, init?: RequestInit) => {
      if (
        path.endsWith(`/evidence/${evidenceId}/link`) &&
        init?.method === "POST"
      )
        linked = true;
      if (path.endsWith(`/events/${eventId}`) && !linked)
        throw new ApiError(
          404,
          "not_found",
          "Evidence must already belong to this case",
        );
      return (init?.method ? original : changed) as T;
    };
    const result = await createCasePort(api).save(changed);
    expect(result.events[0].evidenceIds).toEqual([evidenceId]);
  });
  it("removes a cached plan when the server confirms it no longer exists", async () => {
    const plan = seedPlans[0];
    useWorkspaceStore.getState().putPlan(plan);
    const api: ApiClient = async () => {
      throw new ApiError(404, "not_found", "Missing");
    };
    expect(await createPlanPort(api).getForCase(plan.caseId)).toBeNull();
    expect(useWorkspaceStore.getState().plans).toEqual([]);
  });
  it("keeps evidence attachment cache aligned with canonical case detail", async () => {
    useWorkspaceStore.getState().putEvidence({
      id: "evidence",
      kind: "text_note",
      origin: "user_entered",
      shownTimestamp: "",
      originalText: "Synthetic",
      extractedText: "",
      reviewStatus: "confirmed",
      limitations: [],
    });
    let evidenceIds = ["evidence"];
    const api: ApiClient = async <T>() =>
      ({ ...seedCases[0], id: "case", ownerId: "owner", evidenceIds }) as T;
    await createCasePort(api).get("case");
    expect(useWorkspaceStore.getState().evidence[0].caseId).toBe("case");
    evidenceIds = [];
    await createCasePort(api).get("case");
    expect(useWorkspaceStore.getState().evidence[0].caseId).toBeUndefined();
  });
  it("caches the server's latest plan on conflict while returning it for draft merging", async () => {
    const plan = { ...seedPlans[0], version: 2 };
    useWorkspaceStore.getState().putPlan(plan);
    const api: ApiClient = async () => {
      throw new ApiError(409, "version_conflict", "Changed", {
        latest: {
          ...plan,
          version: 3,
          nextReviewDate: null,
          updatedAt: "new-date",
        },
      });
    };
    await expect(
      createPlanPort(api).save({ ...plan, goal: "My unsaved goal" }),
    ).rejects.toMatchObject({
      details: { latest: { version: 3, nextReviewDate: "" } },
    });
    expect(useWorkspaceStore.getState().plans[0].version).toBe(3);
    expect(useWorkspaceStore.getState().plans[0].goal).toBe(plan.goal);
  });
  beforeEach(() => useWorkspaceStore.getState().activateReal("owner"));
  it("keeps cache and submitted version intact when a case save conflicts", async () => {
    const item = {
      ...seedCases[0],
      id: crypto.randomUUID(),
      ownerId: "owner",
      version: 2,
    };
    useWorkspaceStore.getState().putCase(item);
    let submitted: Record<string, unknown> | undefined;
    const api: ApiClient = async (_path, init) => {
      submitted = JSON.parse(String(init?.body));
      throw new ApiError(409, "version_conflict", "Changed", {
        latest: { ...item, version: 3 },
      });
    };
    await expect(
      createCasePort(api).save({ ...item, title: "My draft" }),
    ).rejects.toMatchObject({ details: { latest: { version: 3 } } });
    expect(submitted?.version).toBe(2);
    expect(submitted).not.toHaveProperty("linkedChatIds");
    expect(useWorkspaceStore.getState().cases[0].title).toBe(item.title);
  });
  it("uses the server's updated plan after a Home item mutation", async () => {
    const plan = { ...seedPlans[0], version: 4 };
    const api: ApiClient = async <T>() =>
      ({
        ...plan,
        version: 5,
        items: plan.items.map((item, index) =>
          index === 0 ? { ...item, status: "done" } : item,
        ),
      }) as T;
    const result = await createPlanPort(api).setItemStatus(
      plan.id,
      plan.items[0].id,
      "done",
    );
    expect(result.version).toBe(5);
    expect(useWorkspaceStore.getState().plans[0].items[0].status).toBe("done");
  });
  it("does not hydrate a previous owner's in-flight response into the next account", async () => {
    let finish!: (value: unknown) => void;
    const api: ApiClient = <T>() =>
      new Promise<T>((resolve) => {
        finish = resolve as (value: unknown) => void;
      });
    const pending = createCasePort(api).get("case-a");
    useWorkspaceStore.getState().activateReal("other");
    finish({ ...seedCases[0], id: "case-a", ownerId: "owner" });
    await pending;
    expect(useWorkspaceStore.getState().cases).toEqual([]);
  });
});
