import { expect, test } from "@playwright/test";
import {
  call,
  pairAlias,
  publishProfile,
  session,
  type ProfileInput,
} from "./helpers";

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
  31: {
    ...viewer,
    interests: ["photography", "cooking", "reading"],
    style: "direct",
    activities: [],
    availability: [],
  },
  32: { ...viewer, goal: "friendship", strictGoal: true },
  33: { ...viewer, goal: "friendship" },
  34: { ...viewer, languages: ["en"] },
};

test(`T10 T11 T13 T17 T19: real private draft reload and explicit publication (${scorer})`, async ({
  browser,
}) => {
  const [own, other] = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  try {
    await session(own, 43);
    await session(other, 44);
    const page = await own.newPage();
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() !== "GET" && /\/profiles\//.test(request.url()))
        writes.push(new URL(request.url()).pathname);
    });
    await page.goto("/#/connect?tab=profile");
    await page
      .getByRole("radio", { name: "Có người tâm sự", exact: true })
      .check();
    for (const name of ["Âm nhạc", "Cà phê", "Đọc sách"])
      await page.getByRole("checkbox", { name, exact: true }).check();
    await page
      .getByRole("radio", { name: "Từ từ làm quen", exact: true })
      .check();
    expect(writes).toEqual([]);
    await page
      .getByRole("button", { name: "Lưu bản nháp", exact: true })
      .click();
    await expect(
      page.getByText("Đã lưu bản nháp. Hồ sơ chưa được công khai.", {
        exact: true,
      }),
    ).toBeVisible();
    expect(writes).toEqual(["/api/v1/profiles/matching-draft"]);
    const saved = await call(own, 43, "GET", "/profiles/matching-draft");
    expect(saved.body.profile.values).toEqual([]);
    expect(saved.body.profile.discovery).toEqual({
      version: 1,
      intention: "talk",
      connectionApproach: "gradual",
      featuredInterests: ["music", "coffee", "reading"],
    });
    expect(
      (await call(other, 44, "GET", "/profiles/matching-draft")).body.version,
    ).toBe(0);
    expect(
      (await call(own, 43, "GET", "/session")).body.consents.MATCH.enabled,
    ).toBe(false);
    expect(
      (await call(own, 43, "GET", "/profiles/published/current")).body,
    ).toBeNull();
    await page.reload();
    await page
      .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
      .click();
    await expect(
      page.getByRole("radio", { name: "Từ từ làm quen", exact: true }),
    ).toBeChecked();
    await expect(
      page.getByRole("checkbox", { name: "Âm nhạc", exact: true }),
    ).toBeChecked();
    await page
      .getByRole("button", { name: "Xem lại trước khi hiển thị", exact: true })
      .click();
    const supplement = page.getByRole("region", {
      name: "Bổ sung để ghép bạn chính xác hơn",
      exact: true,
    });
    for (const name of ["Tôn trọng", "Chân thành", "Tiếng Việt"])
      await supplement.getByRole("checkbox", { name, exact: true }).check();
    await page
      .getByRole("button", { name: "Xem bản được chia sẻ", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Hiển thị hồ sơ", exact: true }),
    ).toBeVisible();
    expect(
      (await call(own, 43, "GET", "/profiles/published/current")).body,
    ).toBeNull();
    expect(
      (await call(own, 43, "GET", "/session")).body.consents.MATCH.enabled,
    ).toBe(false);
    const previewProfile = (
      await call(own, 43, "GET", "/profiles/matching-draft")
    ).body.profile;
    await page
      .getByRole("button", { name: "Hiển thị hồ sơ", exact: true })
      .click();
    await expect(
      page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true }),
    ).toBeVisible();
    expect(
      (await call(own, 43, "GET", "/profiles/published/current")).body.profile,
    ).toEqual(previewProfile);
    expect(
      (await call(own, 43, "GET", "/session")).body.consents.MATCH.enabled,
    ).toBe(true);
    expect(writes).toEqual([
      "/api/v1/profiles/matching-draft",
      "/api/v1/profiles/matching-draft",
      "/api/v1/profiles/matching-draft/preview",
      "/api/v1/profiles/published",
    ]);
    // A real second published user makes the new profile discoverable, without exposing their draft.
    await publishProfile(other, 44, {
      interests: ["music", "coffee", "reading"],
      values: ["respect", "sincerity"],
      style: "balanced",
      goal: "friendship",
      languages: ["vi"],
    });
    const cards = await call(own, 43, "GET", "/matching/candidates");
    expect(
      cards.body.candidates.map((card: { alias: string }) => card.alias),
    ).toContain(pairAlias(43, 44));
    const current = await call(own, 43, "GET", "/profiles/published/current");
    expect(
      (
        await call(own, 43, "DELETE", "/profiles/published/current", {
          expectedVersion: current.body.profileVersion,
        })
      ).status,
    ).toBe(200);
    const after = await call(other, 44, "GET", "/matching/candidates");
    expect(
      after.body.candidates.map((card: { alias: string }) => card.alias),
    ).not.toContain(pairAlias(43, 44));
    expect(
      (await call(own, 43, "GET", "/profiles/matching-draft")).body.profile,
    ).toEqual(previewProfile);
    // Revoke the real server session while an editor is dirty, as from another tab.
    await page.goto("/#/connect?tab=profile");
    await page
      .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
      .click();
    await page
      .getByRole("radio", { name: "Bạn cùng học", exact: true })
      .check();
    expect((await call(own, 43, "POST", "/auth/logout")).status).toBe(204);
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.locator(".profile-editor")).toHaveCount(0);
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Đăng nhập", exact: true }),
    ).toBeVisible();
    expect(
      (await call(own, 43, "GET", "/profiles/matching-draft")).status,
    ).toBe(401);
  } finally {
    await Promise.all([own.close(), other.close()]);
  }
});

test(`T07 T17 T20 T22: metadata survives older writers with full public data (${scorer})`, async ({
  browser,
}) => {
  const context = await browser.newContext();
  const number = 42;
  try {
    await session(context, number);
    const profile: ProfileInput = {
      interests: [
        "reading",
        "music",
        "coffee",
        "walking",
        "running",
        "cycling",
        "yoga",
        "football",
        "badminton",
        "drawing",
      ],
      values: ["respect", "sincerity"],
      languages: ["vi", "en"],
      style: "direct",
      goal: "language-practice",
      activities: ["focus"],
      availability: ["weekday_evening"],
      strictGoal: true,
      discovery: {
        version: 1,
        intention: "experiences",
        connectionApproach: "activity-first",
        featuredInterests: ["music", "reading"],
      },
    };
    const saved = await call(
      context,
      number,
      "PUT",
      "/profiles/matching-draft",
      { ...profile, expectedVersion: 0 },
    );
    expect(saved.status, saved.text).toBe(200);
    const { discovery, ...legacy } = profile;
    const older = await call(
      context,
      number,
      "PUT",
      "/profiles/matching-draft",
      { ...legacy, expectedVersion: saved.body.version },
    );
    expect(older.status, older.text).toBe(200);
    expect(older.body.profile.discovery).toEqual(discovery);
    expect(older.body.profile.interests).toEqual(profile.interests);
    const preview = await call(
      context,
      number,
      "POST",
      "/profiles/matching-draft/preview",
    );
    expect(preview.status, preview.text).toBe(200);
    expect(
      (await call(context, number, "GET", "/session")).body.consents.MATCH
        .enabled,
    ).toBe(false);
    expect(
      (await call(context, number, "GET", "/profiles/published/current")).body,
    ).toBeNull();
    const published = await call(
      context,
      number,
      "POST",
      "/profiles/published",
      {
        draftVersion: preview.body.draftVersion,
        previewDigest: preview.body.previewDigest,
        expectedPublishedVersion: 0,
      },
    );
    expect(published.status, published.text).toBe(201);
    expect(published.body.profile).toMatchObject(profile);
    expect(
      (await call(context, number, "GET", "/session")).body.consents.MATCH
        .enabled,
    ).toBe(true);
  } finally {
    await context.close();
  }
});

test(`matching (${scorer}) ranks real profiles with qualitative labels and honest rules`, async ({
  browser,
}) => {
  test.setTimeout(120_000);
  const contexts = await Promise.all(
    [29, 30, 31, 32, 33, 34].map(() => browser.newContext()),
  );
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
    const aliases = list.body.candidates.map(
      (card: { alias: string }) => card.alias,
    );
    for (const card of list.body.candidates)
      expect(card.scoringVersion).toBe(
        scorer === "v2" ? "rules-v2" : "rules-v1.1",
      );
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
    await expect(cards.first()).toHaveAttribute(
      "aria-label",
      `Hồ sơ của ${pairAlias(29, 30)}`,
    );
    await expect(cards.first()).toContainText("Nhiều điểm chung");
    const count = await cards.count();
    expect(count).toBeGreaterThan(1);
    expect(count).toBeLessThanOrEqual(5);
    for (let index = 0; index < count; index++) {
      const card = cards.nth(index);
      expect(await card.innerText()).not.toMatch(/\d\s*%/);
      const reasons = card
        .getByRole("list", { name: "Điểm chung" })
        .getByRole("listitem");
      expect(await reasons.count()).toBeLessThanOrEqual(3);
    }
    await expect(
      page.getByText(/không phải đánh giá mức độ hợp nhau/),
    ).toBeVisible();
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

test(`a profile with a v2-only goal still receives suggestions (${scorer})`, async ({
  browser,
}) => {
  // Regression: rollback and candidate scorers both accept every published tag/goal.
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
    expect(
      list.body.candidates.map((card: { alias: string }) => card.alias),
    ).toContain(pairAlias(40, 41));
  } finally {
    await own.close();
    await peer.close();
  }
});
