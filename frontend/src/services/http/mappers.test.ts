import { describe, expect, it } from "vitest";
import {
  mapIncident,
  mapPlan,
  serializeCase,
  serializePlan,
  serializeEvent,
} from "./mappers";
describe("API model mapping", () => {
  it("sends exact local input as timezone-aware instant and leaves day labels alone", () => {
    const event = {
      id: crypto.randomUUID(),
      caseId: crypto.randomUUID(),
      when: "2026-11-07T09:30",
      timePrecision: "exact" as const,
      place: "",
      description: "Synthetic",
      provenance: "user_entered" as const,
      evidenceIds: [],
      needsReview: false,
    };
    expect(serializeEvent(event).when).toBe(
      new Date("2026-11-07T09:30").toISOString(),
    );
    expect(
      serializeEvent({ ...event, timePrecision: "day", when: "2026-11-07" })
        .when,
    ).toBe("2026-11-07");
  });
  it("preserves case versions and removes simulated links from real writes", () => {
    const incident = mapIncident({
      id: "a",
      ownerId: "u",
      title: "Synthetic",
      version: 7,
      linkedPlanId: null,
      events: [],
      evidenceIds: [],
      createdAt: "now",
      updatedAt: "now",
    });
    const body = serializeCase({
      ...incident,
      linkedChatIds: ["sim"],
      demo: true,
    });
    expect(incident.version).toBe(7);
    expect(incident.demo).toBe(false);
    expect(incident.linkedPlanId).toBeUndefined();
    expect(body.version).toBe(7);
    expect(body).not.toHaveProperty("linkedChatIds");
    expect(body).not.toHaveProperty("demo");
  });
  it("preserves ordered plan items and version while normalizing nullable dates", () => {
    const plan = mapPlan({
      id: "p",
      caseId: "c",
      goal: "g",
      status: "active",
      version: 3,
      nextReviewDate: null,
      updatedAt: "today",
      items: [
        { id: "b", label: "B" },
        { id: "a", label: "A" },
      ],
    });
    expect(plan.nextReviewDate).toBe("");
    expect(plan.version).toBe(3);
    const body = serializePlan(plan);
    expect(body.items.map((item) => item.id)).toEqual(["b", "a"]);
    expect(body.version).toBe(3);
    expect(body.nextReviewDate).toBeNull();
  });
});
