import { beforeEach, describe, expect, it } from "vitest";
import { useDemoStore } from "./store";
import { demoService } from "../mocks/services/demo";

describe("canonical demo state", () => {
  it("detaches deleted case links while preserving the original AI analysis sources", () => {
    const store = useDemoStore.getState();
    store.login("USER-AN");
    store.putChat({
      id: "CHAT-LINK",
      ownerId: "USER-AN",
      title: "Mẫu",
      scenarioId: "SC-08",
      cursor: 0,
      messages: [],
      linkedCaseId: "CASE-AN-001",
    });
    store.putAnalysis({
      id: "ANALYSIS-LINK",
      ownerId: "USER-AN",
      fixture: "multi",
      evidenceIds: ["MEDIA-LINK"],
      confirmedIds: ["MEDIA-LINK"],
      description: "Mẫu",
      questionAnswer: "",
      status: "confirmed",
      caseId: "CASE-AN-001",
    });
    store.putEvidence({
      id: "MEDIA-LINK",
      caseId: "CASE-AN-001",
      kind: "screenshot",
      origin: "mock_fixture",
      shownTimestamp: "",
      originalText: "Mẫu",
      extractedText: "Mẫu",
      reviewStatus: "confirmed",
      limitations: [],
    });
    sessionStorage.setItem("safevoice-plan-draft-v1:USER-AN:CASE-AN-001", "{}");
    store.deleteCase("CASE-AN-001");
    expect(useDemoStore.getState().chats[0].linkedCaseId).toBeUndefined();
    expect(useDemoStore.getState().analyses[0].caseId).toBeUndefined();
    expect(
      useDemoStore.getState().evidence.find((e) => e.id === "MEDIA-LINK")
        ?.originalText,
    ).toBe("Mẫu");
    expect(
      sessionStorage.getItem("safevoice-plan-draft-v1:USER-AN:CASE-AN-001"),
    ).toBeNull();
  });
  beforeEach(() => useDemoStore.getState().reset());
  it("scopes student records and changes persona without exposing previous drafts", () => {
    useDemoStore.getState().login("USER-AN");
    const an = useDemoStore.getState();
    expect(an.cases.filter((c) => c.ownerId === an.user?.id)).toHaveLength(1);
    useDemoStore.getState().login("USER-MINH");
    expect(useDemoStore.getState().user?.nickname).toBe("Minh");
    expect(
      useDemoStore.getState().cases.filter((c) => c.ownerId === "USER-MINH"),
    ).toHaveLength(2);
  });
  it("keeps Home and case plan in the same canonical state after edits", () => {
    useDemoStore.getState().login("USER-AN");
    const plan = useDemoStore.getState().plans[0];
    useDemoStore.getState().putPlan({
      ...plan,
      items: plan.items.map((i) => ({ ...i, status: "done" })),
    });
    expect(
      useDemoStore.getState().plans[0].items.every((i) => i.status === "done"),
    ).toBe(true);
    expect(
      useDemoStore.getState().cases.find((c) => c.id === plan.caseId)
        ?.linkedPlanId,
    ).toBe(plan.id);
  });
  it("failed save is recoverable and never writes state", async () => {
    useDemoStore.getState().login("USER-AN");
    const incident = useDemoStore.getState().cases[0];
    useDemoStore.getState().setFailNextSave(true);
    await expect(
      demoService.saveCase({ ...incident, title: "Changed" }),
    ).rejects.toThrow("mô phỏng");
    expect(useDemoStore.getState().cases[0].title).toBe(incident.title);
    await demoService.saveCase({ ...incident, title: "Changed" });
    expect(useDemoStore.getState().cases[0].title).toBe("Changed");
  });
  it("reset restores fixtures and clears the mock session", () => {
    useDemoStore.getState().login("USER-AN");
    useDemoStore.getState().deleteCase("CASE-AN-001");
    useDemoStore.getState().reset();
    expect(useDemoStore.getState().user).toBeNull();
    expect(
      useDemoStore.getState().cases.find((c) => c.id === "CASE-AN-001"),
    ).toBeDefined();
  });
  it("isolates personal contacts and reading preferences across logout/personas", () => {
    useDemoStore.getState().login("USER-AN");
    useDemoStore.getState().addTrustedPerson({
      id: "PRIVATE-AN",
      label: "Người tin cậy riêng của An",
      role: "Khác",
    });
    useDemoStore.getState().markRead("KB-24");
    useDemoStore.getState().logout();
    useDemoStore.getState().login("USER-MINH");
    expect(
      useDemoStore.getState().trustedPeople.some((p) => p.id === "PRIVATE-AN"),
    ).toBe(false);
    expect(useDemoStore.getState().readIds).not.toContain("KB-24");
    useDemoStore.getState().login("USER-AN");
    expect(
      useDemoStore.getState().trustedPeople.some((p) => p.id === "PRIVATE-AN"),
    ).toBe(true);
  });
  it("reset removes recoverable form drafts as well as canonical data", () => {
    sessionStorage.setItem(
      "safevoice-case-draft-v1:USER-AN:new",
      '{"summary":"demo"}',
    );
    sessionStorage.setItem(
      "safevoice-plan-draft-v1:USER-AN:CASE-AN-001",
      '{"goal":"demo"}',
    );
    sessionStorage.setItem("unrelated-app", "keep");
    useDemoStore.getState().reset();
    expect(
      sessionStorage.getItem("safevoice-case-draft-v1:USER-AN:new"),
    ).toBeNull();
    expect(
      sessionStorage.getItem("safevoice-plan-draft-v1:USER-AN:CASE-AN-001"),
    ).toBeNull();
    expect(sessionStorage.getItem("unrelated-app")).toBe("keep");
  });
});
