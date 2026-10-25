import { expect, test } from "@playwright/test";
import { call, pairAlias, publishProfile, session, type ProfileInput } from "./helpers";

// Synthetic users against the served scorer. Run with E2E_MATCHING_SCORER=v2 for the
// candidate scorer; the default server serves v1 (the production default).
const scorer = process.env.E2E_MATCHING_SCORER === "v2" ? "v2" : "v1";

// Inside the frozen v1 vocabulary, so both scorers can rank it (users 29-34).
const viewer: ProfileInput = {
  interests: ["photography", "cooking", "puzzles"],
  values: ["curiosity", "kindness"],
  style: "listening",
  goal: "shared-interests",
  languages: ["vi"],
  activities: ["focus"],
  availability: ["weekday_evening"],
  strictGoal: false,
};
const peers: Record<number, ProfileInput> = {
  30: { ...viewer },
  31: { ...viewer, interests: ["photography", "cooking", "reading"], style: "direct", activities: [], availability: [] },
  32: { ...viewer, goal: "friendship", strictGoal: true },
  33: { ...viewer, goal: "friendship" },
  34: { ...viewer, languages: ["en"] },
};

test(`matching (${scorer}) ranks real profiles with qualitative labels and honest rules`, async ({
  browser,
}) => {
  test.setTimeout(120_000);
  const contexts = await Promise.all([29, 30, 31, 32, 33, 34].map(() => browser.newContext()));
  try {
    const [own, ...others] = contexts;
    await session(own, 29);
    await publishProfile(own, 29, viewer);
    for (const [index, number] of [30, 31, 32, 33, 34].entries()) {
      await session(others[index], number);
      await publishProfile(others[index], number, peers[number]);
    }
    const list = await call(own, 29, "GET", "/matching/candidates");
    expect(list.status, list.text).toBe(200);
    const aliases = list.body.candidates.map((card: { alias: string }) => card.alias);
    for (const card of list.body.candidates)
      expect(card.scoringVersion).toBe(scorer === "v2" ? "rules-v2" : "rules-v1");
    expect(aliases[0], list.text).toBe(pairAlias(29, 30));
    expect(aliases).toContain(pairAlias(29, 31));
    // A strict goal is honoured by both scorers; no shared language means no match.
    expect(aliases).not.toContain(pairAlias(29, 32));
    expect(aliases).not.toContain(pairAlias(29, 34));
    // v2 relaxes equal goals unless strict; v1 still requires the same goal.
    if (scorer === "v2") expect(aliases).toContain(pairAlias(29, 33));
    else expect(aliases).not.toContain(pairAlias(29, 33));

    const page = await own.newPage();
    await page.goto("/#/connect?tab=suggestions");
    const cards = page.getByRole("article", { name: /^Hồ sơ của / });
    await expect(cards.first()).toHaveAttribute("aria-label", `Hồ sơ của ${pairAlias(29, 30)}`);
    await expect(cards.first()).toContainText("Nhiều điểm chung");
    const count = await cards.count();
    expect(count).toBeGreaterThan(1);
    expect(count).toBeLessThanOrEqual(5);
    for (let index = 0; index < count; index++) {
      const card = cards.nth(index);
      expect(await card.innerText()).not.toMatch(/\d\s*%/);
      const reasons = card.getByRole("list", { name: "Điểm chung" }).getByRole("listitem");
      expect(await reasons.count()).toBeLessThanOrEqual(3);
    }
    await expect(page.getByText(/không phải đánh giá mức độ hợp nhau/)).toBeVisible();
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

test(`a profile with a v2-only goal still receives suggestions (${scorer})`, async ({ browser }) => {
  // Known defect (P1, release report): /taxonomy always offers the v2 vocabulary, but the
  // default v1 scorer treats v2-only goals and tags as invalid and returns nothing.
  test.fail(scorer === "v1", "v1 cannot rank v2-only goals or tags");
  const profile: ProfileInput = {
    interests: ["chess", "anime", "podcasts"],
    values: ["growth", "calm"],
    style: "balanced",
    goal: "study-buddy",
    languages: ["vi"],
  };
  const [own, peer] = [await browser.newContext(), await browser.newContext()];
  try {
    await session(own, 40);
    await session(peer, 41);
    await publishProfile(own, 40, profile);
    await publishProfile(peer, 41, profile);
    const list = await call(own, 40, "GET", "/matching/candidates");
    expect(list.status, list.text).toBe(200);
    expect(list.body.candidates.map((card: { alias: string }) => card.alias)).toContain(
      pairAlias(40, 41),
    );
  } finally {
    await own.close();
    await peer.close();
  }
});
