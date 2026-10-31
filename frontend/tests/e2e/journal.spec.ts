import { expect, test, type Page } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";
import { mkdir, readFile } from "node:fs/promises";
import { artifactPath } from "../artifacts";

for (const width of [390, 1280]) {
  test(`journal writing box starts compact and follows its content at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await journal(page);
    await page.goto("/#/self");
    const input = page.getByRole("textbox", {
      name: "Ghi lại khoảnh khắc",
      exact: true,
    });
    const initialHeight = (await input.boundingBox())!.height;
    expect(initialHeight).toBeLessThanOrEqual(150);
    await input.fill(
      Array.from(
        { length: 16 },
        (_, index) => `Dòng ${index + 1}: Một khoảnh khắc đáng nhớ.`,
      ).join("\n"),
    );
    await expect
      .poll(async () => (await input.boundingBox())!.height)
      .toBeGreaterThan(initialHeight + 200);
    expect(
      await input.evaluate((node) => node.scrollHeight - node.clientHeight),
    ).toBeLessThanOrEqual(1);
    await input.fill("Một khoảnh khắc dài. ".repeat(400));
    await expect
      .poll(() =>
        input.evaluate((node) => node.scrollHeight > node.clientHeight),
      )
      .toBe(true);
    expect((await input.boundingBox())!.height).toBeLessThanOrEqual(800);
    await input.fill("");
    await expect
      .poll(async () => (await input.boundingBox())!.height)
      .toBe(initialHeight);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - innerWidth,
      ),
    ).toBeLessThanOrEqual(1);
    await input.scrollIntoViewIfNeeded();
    const output = artifactPath("writing-box");
    await mkdir(output, { recursive: true });
    await page.screenshot({ path: path.join(output, `compact-${width}.png`) });
  });
}

test("saved writing adapts its height when the viewport becomes narrower", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  const text =
    "Một buổi chiều bình yên, mình viết lại những điều đáng nhớ. ".repeat(25);
  await journal(page, [entry({ text })]);
  await page.goto(`/#/self/entry/${entry().id}?edit=1`);
  const input = page.getByRole("textbox", {
    name: "Ghi lại khoảnh khắc",
    exact: true,
  });
  await expect(input).toHaveValue(text);
  const wideHeight = (await input.boundingBox())!.height;
  expect(wideHeight).toBeGreaterThan(150);
  await page.setViewportSize({ width: 390, height: 1000 });
  await expect
    .poll(async () => (await input.boundingBox())!.height)
    .toBeGreaterThan(wideHeight);
  await expect(input).toHaveValue(text);
});

test("account-local midnight keeps unsaved text and local media", async ({
  page,
}) => {
  await page.clock.install({ time: new Date("2026-10-23T16:59:50Z") });
  await journal(page, [], {
    ...baseSession,
    serverTime: "2026-10-23T16:59:50Z",
  });
  await page.goto("/#/self");
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Đang viết qua nửa đêm");
  await page.getByLabel("Thêm hình ảnh", { exact: true }).setInputFiles({
    name: "chua-luu.png",
    mimeType: "image/png",
    buffer: Buffer.from([1, 2, 3]),
  });
  await page.clock.fastForward(70000);
  await expect(page.locator("#journal-date")).toHaveAttribute(
    "max",
    "2026-10-24",
  );
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Đang viết qua nửa đêm");
  await expect(page.getByText("chua-luu.png", { exact: true })).toBeVisible();
});

test("a concurrent text edit during attachment upload cannot advance the editor version", async ({
  page,
}) => {
  await journal(page, [entry()]);
  let concurrent = false,
    version = 1;
  await page.route(`**/api/v1/journal/entries/${entry().id}`, (route) => {
    if (route.request().method() === "PUT") {
      version++;
      return route.fulfill({
        json: entry({ ...route.request().postDataJSON(), version }),
      });
    }
    return route.fulfill({
      json: entry({
        version: concurrent ? version + 1 : version,
        text: concurrent ? "Nội dung từ tab khác" : "Một buổi chiều bình yên",
      }),
    });
  });
  const media = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "image",
    mimeType: "image/png",
    sizeBytes: 3,
    status: "pending",
    createdAt: stamp,
  };
  await page.route("**/api/v1/journal/entries/*/media", (route) =>
    route.fulfill({
      json: {
        media,
        uploadUrl: "http://127.0.0.1:5173/signed-concurrent-upload",
        token: "synthetic",
        resumableUrl: "",
        objectPath: "synthetic/photo.png",
        bucket: "journal-media",
      },
    }),
  );
  await page.route("**/signed-concurrent-upload", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.route("**/api/v1/journal/entries/*/media/*/complete", (route) => {
    concurrent = true;
    return route.fulfill({ json: { ...media, status: "ready" } });
  });
  await page.goto(`/#/self/entry/${entry().id}`);
  await page
    .getByRole("button", { name: "Thao tác với khoảnh khắc", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Chỉnh sửa khoảnh khắc", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Phần đang viết của mình");
  await page.getByLabel("Thêm hình ảnh", { exact: true }).setInputFiles({
    name: "photo.png",
    mimeType: "image/png",
    buffer: Buffer.from([1, 2, 3]),
  });
  await page
    .getByRole("button", { name: "Tải tệp đính kèm", exact: true })
    .click();
  await expect(page.locator(".journal-conflict")).toContainText(
    "Khoảnh khắc vừa thay đổi ở nơi khác.",
  );
  await expect(
    page.getByRole("button", { name: "Lưu khoảnh khắc", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Phần đang viết của mình");
});

const stamp = "2026-10-23T08:00:00Z";
function syntheticAudio() {
  const sampleRate = 8000,
    samples = sampleRate * 2;
  const wav = Buffer.alloc(44 + samples * 2);
  wav.write("RIFF", 0);
  wav.writeUInt32LE(36 + samples * 2, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * 2, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(samples * 2, 40);
  for (let i = 0; i < samples; i++)
    wav.writeInt16LE(
      Math.round(Math.sin((i * 2 * Math.PI * 220) / sampleRate) * 1000),
      44 + i * 2,
    );
  return `data:audio/wav;base64,${wav.toString("base64")}`;
}
function entry(patch: Record<string, unknown> = {}) {
  return {
    id: "33333333-3333-4333-8333-333333333333",
    localDate: "2026-10-23",
    timezone: "Asia/Bangkok",
    mood: 4,
    text: "Một buổi chiều bình yên",
    emotions: ["Biết ơn"],
    factors: ["Gia đình"],
    status: "saved",
    version: 1,
    createdAt: stamp,
    updatedAt: stamp,
    media: [],
    ...patch,
  };
}

function fixtureInstant(timestamp: unknown) {
  const value = String(timestamp);
  return (
    new Date(value).toISOString().slice(0, 19) +
    "." +
    (value.match(/\.(\d+)/)?.[1] || "").padEnd(6, "0")
  );
}

async function journal(
  page: Page,
  initial: ReturnType<typeof entry>[] = [],
  session: unknown = baseSession,
) {
  let entries = initial;
  const requests: { method: string; url: string; body: any }[] = [];
  await app(page, session);
  await page.route("**/api/v1/journal/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const body = request.postData() ? request.postDataJSON() : {};
    requests.push({
      method: request.method(),
      url: url.pathname + url.search,
      body,
    });
    if (url.pathname.endsWith("/entries") && request.method() === "GET") {
      let filtered = entries.filter(
        (item) => item.status === (url.searchParams.get("status") || "saved"),
      );
      for (const key of ["from", "to"] as const) {
        const value = url.searchParams.get(key);
        if (value)
          filtered = filtered.filter((item) =>
            key === "from"
              ? String(item.localDate) >= value
              : String(item.localDate) <= value,
          );
      }
      const q = url.searchParams.get("q");
      if (q)
        filtered = filtered.filter((item) => String(item.text).includes(q));
      const mood = url.searchParams.get("mood"),
        media = url.searchParams.get("media");
      if (mood)
        filtered = filtered.filter(
          (item) => Number(item.mood) === Number(mood),
        );
      if (media)
        filtered = filtered.filter((item) =>
          (item.media as any[]).some(
            (file) => file.type === media && file.status === "ready",
          ),
        );
      const offset = Number(url.searchParams.get("offset") || 0),
        limit = Number(url.searchParams.get("limit") || 12);
      filtered.sort(
        (a, b) =>
          String(b.localDate).localeCompare(String(a.localDate)) ||
          fixtureInstant(b.createdAt).localeCompare(
            fixtureInstant(a.createdAt),
          ) ||
          String(b.id).localeCompare(String(a.id)),
      );
      return route.fulfill({
        json: {
          items: filtered.slice(offset, offset + limit),
          total: filtered.length,
          offset,
          limit,
        },
      });
    }
    if (url.pathname.endsWith("/entries") && request.method() === "POST") {
      const saved = entry({
        ...body,
        id: `33333333-3333-4333-8333-${String(entries.length + 1).padStart(12, "0")}`,
      });
      entries = [saved, ...entries];
      return route.fulfill({ json: saved });
    }
    const found = entries.find(
      (item) => url.pathname === `/api/v1/journal/entries/${item.id}`,
    );
    if (found && request.method() === "GET")
      return route.fulfill({ json: found });
    if (found && request.method() === "PUT") {
      const saved = { ...found, ...body, version: Number(found.version) + 1 };
      entries = entries.map((item) => (item.id === found.id ? saved : item));
      return route.fulfill({ json: saved });
    }
    if (found && request.method() === "DELETE") {
      entries = entries.filter((item) => item.id !== found.id);
      return route.fulfill({
        json: { status: "succeeded", resourceId: found.id },
      });
    }
    return route.fulfill({
      status: 404,
      json: {
        error: { code: "NOT_FOUND", message: "Không tìm thấy khoảnh khắc." },
      },
    });
  });
  return requests;
}

test("journal saves a complete moment and restores a server draft without local storage", async ({
  page,
}) => {
  const requests = await journal(page);
  await page.goto("/#/self");
  await page.getByRole("radio", { name: "Khá vui", exact: true }).check();
  await page.getByRole("checkbox", { name: "Biết ơn", exact: true }).check();
  await page.getByRole("checkbox", { name: "Gia đình", exact: true }).check();
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Cùng gia đình đi dạo.");
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu bản nháp" }),
  ).toBeVisible();
  const created = requests.find(
    (request) => request.method === "POST" && request.url.endsWith("/entries"),
  );
  expect(created?.body).toMatchObject({
    mood: 4,
    text: "Cùng gia đình đi dạo.",
    emotions: ["Biết ơn"],
    factors: ["Gia đình"],
    status: "draft",
  });
  await page.reload();
  await page.getByText("1 bản nháp đã lưu").click();
  await page.getByRole("link", { name: /Mở bản nháp/ }).click();
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Cùng gia đình đi dạo.");
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu khoảnh khắc" }),
  ).toBeVisible();
  expect(
    requests.filter(
      (request) =>
        request.method === "POST" && request.url.endsWith("/entries"),
    ),
  ).toHaveLength(1);
  expect(
    requests.some(
      (request) => request.method === "PUT" && request.body.status === "saved",
    ),
  ).toBe(true);
});

test("failed and stale saves preserve text; dirty navigation waits for a decision", async ({
  page,
}) => {
  await journal(page, [entry()]);
  await page.goto(`/#/self/entry/${entry().id}`);
  await page
    .getByRole("button", { name: "Thao tác với khoảnh khắc", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Chỉnh sửa khoảnh khắc", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Bản nháp cần giữ");
  await page.route(`**/api/v1/journal/entries/${entry().id}`, (route) =>
    route.request().method() === "PUT"
      ? route.fulfill({
          status: 409,
          json: {
            error: {
              code: "STALE_VERSION",
              message: "Khoảnh khắc đã thay đổi ở nơi khác.",
            },
          },
        })
      : route.fallback(),
  );
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("thay đổi");
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Bản nháp cần giữ");
  await page
    .getByRole("link", { name: "Lịch nhật ký", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("dialog", { name: "Rời bản đang viết?" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tiếp tục viết", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Bản nháp cần giữ");
});

test("calendar and timeline use real dates, progressive loading and open details", async ({
  page,
}) => {
  const many = Array.from({ length: 14 }, (_, i) =>
    entry({
      id: `33333333-3333-4333-8333-${String(i + 1).padStart(12, "0")}`,
      text: `Bình yên ${i}`,
      localDate: "2026-10-23",
    }),
  );
  const requests = await journal(page, many);
  await page.goto("/#/self/calendar");
  await expect(
    page.getByRole("heading", { name: "Lịch nhật ký", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /23 tháng 10.*14 khoảnh khắc/ })
    .click();
  await expect(page.getByText("Bình yên 0", { exact: true })).toBeVisible();
  await page
    .getByRole("link", { name: "Khoảnh khắc của bạn", exact: true })
    .first()
    .click();
  await expect(page.locator(".journal-timeline article")).toHaveCount(12);
  await page
    .getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true })
    .click();
  await expect
    .poll(() => requests.some((request) => request.url.includes("limit=24")))
    .toBe(true);
  await expect(page.locator(".journal-timeline article")).toHaveCount(14);
  await expect(page.getByText("Bình yên 0", { exact: true })).toBeVisible();
  await expect(page.getByText("Bình yên 13", { exact: true })).toBeVisible();
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Trang sau", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: /Mở khoảnh khắc.*23\/10\/2026/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Thao tác với khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("menuitem", { name: "Chỉnh sửa khoảnh khắc", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Xóa khoảnh khắc", exact: true }),
  ).toHaveCount(0);
});

test("attachment upload retry keeps one server draft and one reservation", async ({
  page,
}) => {
  const requests = await journal(page);
  const media = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "image",
    mimeType: "image/png",
    sizeBytes: 3,
    status: "pending",
    createdAt: stamp,
  };
  let reservations = 0,
    uploads = 0;
  await page.route("**/api/v1/journal/entries/*/media", (route) => {
    reservations++;
    return route.fulfill({
      json: {
        media,
        uploadUrl: "http://127.0.0.1:5173/signed-journal-upload",
        token: "synthetic-token",
        resumableUrl: "",
        objectPath: "synthetic/photo.png",
        bucket: "journal-media",
      },
    });
  });
  await page.route("**/signed-journal-upload*", (route) => {
    uploads++;
    return route.fulfill({ status: uploads === 1 ? 503 : 200, json: {} });
  });
  await page.route("**/api/v1/journal/entries/*/media/*/complete", (route) =>
    uploads >= 2
      ? route.fulfill({ json: { ...media, status: "ready" } })
      : route.fulfill({
          status: 409,
          json: {
            error: { code: "UPLOAD_INCOMPLETE", message: "Tệp chưa tải xong." },
          },
        }),
  );
  await page.goto("/#/self");
  await page.getByLabel("Thêm hình ảnh", { exact: true }).setInputFiles({
    name: "photo.png",
    mimeType: "image/png",
    buffer: Buffer.from([1, 2, 3]),
  });
  await page
    .getByRole("button", { name: "Tải tệp đính kèm", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("tải");
  await expect(page.getByText("photo.png", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Thử tải lại photo.png", exact: true })
    .click();
  await expect.poll(() => uploads).toBe(2);
  expect(reservations).toBe(1);
  expect(
    requests.filter(
      (request) =>
        request.method === "POST" && request.url.endsWith("/entries"),
    ),
  ).toHaveLength(1);
});

test("a completion retry verifies uploaded bytes before attempting another immutable upload", async ({
  page,
}) => {
  await journal(page);
  const media = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "audio",
    mimeType: "audio/wav",
    sizeBytes: 3,
    status: "pending",
    createdAt: stamp,
  };
  let uploads = 0,
    completions = 0;
  await page.route("**/api/v1/journal/entries/*/media", (route) =>
    route.fulfill({
      json: {
        media,
        uploadUrl: "http://127.0.0.1:5173/signed-journal-upload",
        token: "synthetic-token",
        resumableUrl: "",
        objectPath: "synthetic/audio.wav",
        bucket: "journal-media",
      },
    }),
  );
  await page.route("**/signed-journal-upload*", (route) => {
    uploads++;
    return route.fulfill({ status: uploads === 1 ? 200 : 409, json: {} });
  });
  await page.route("**/api/v1/journal/entries/*/media/*/complete", (route) => {
    completions++;
    return completions === 1
      ? route.fulfill({
          status: 503,
          json: {
            error: { code: "UNAVAILABLE", message: "Chưa xác nhận được tệp." },
          },
        })
      : route.fulfill({ json: { ...media, status: "ready" } });
  });
  await page.goto("/#/self");
  await page.getByLabel("Thêm âm thanh", { exact: true }).setInputFiles({
    name: "audio.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from([1, 2, 3]),
  });
  await page
    .getByRole("button", { name: "Tải tệp đính kèm", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("xác nhận");
  await page
    .getByRole("button", { name: "Thử tải lại audio.wav", exact: true })
    .click();
  await expect.poll(() => completions).toBe(2);
  expect(uploads).toBe(1);
});

test("microphone denial preserves writing; local video can be previewed and removed", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: () =>
          Promise.reject(new DOMException("No microphone", "NotAllowedError")),
      },
    }),
  );
  const requests = await journal(page);
  await page.goto("/#/self");
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Vẫn giữ lời viết của mình.");
  await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("quyền dùng micro");
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toHaveValue("Vẫn giữ lời viết của mình.");
  await page.getByLabel("Thêm video", { exact: true }).setInputFiles({
    name: "moment.webm",
    mimeType: "video/webm",
    buffer: Buffer.from([1, 2, 3]),
  });
  await expect(
    page.getByLabel("Xem trước moment.webm", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gỡ moment.webm", exact: true })
    .click();
  await expect(
    page.getByLabel("Xem trước moment.webm", { exact: true }),
  ).toHaveCount(0);
  expect(requests.filter((request) => request.method !== "GET")).toHaveLength(
    0,
  );
});

test("recording pauses, resumes, stops and replays without calling chat transcription", async ({
  page,
}) => {
  await page.addInitScript(() => {
    class SyntheticRecorder {
      static isTypeSupported() {
        return false;
      }
      state = "inactive";
      mimeType = "audio/wav";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      pause() {
        this.state = "paused";
      }
      resume() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        const buffer = new ArrayBuffer(16044),
          view = new DataView(buffer);
        const chars = (offset: number, text: string) => {
          for (let i = 0; i < text.length; i++)
            view.setUint8(offset + i, text.charCodeAt(i));
        };
        chars(0, "RIFF");
        view.setUint32(4, 16036, true);
        chars(8, "WAVEfmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, 8000, true);
        view.setUint32(28, 16000, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        chars(36, "data");
        view.setUint32(40, 16000, true);
        this.ondataavailable?.({
          data: new Blob([buffer], { type: "audio/wav" }),
        });
        this.onstop?.();
      }
    }
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: SyntheticRecorder,
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: () =>
          Promise.resolve({ getTracks: () => [{ stop() {} }] }),
      },
    });
  });
  const writes = await journal(page);
  await page.goto("/#/self");
  await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đang ghi âm" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tạm dừng ghi âm", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã tạm dừng" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tiếp tục ghi âm", exact: true })
    .click();
  await page.getByRole("button", { name: "Dừng ghi âm", exact: true }).click();
  const audio = page.getByLabel(/^Nghe lại Ghi âm/);
  await expect(audio).toBeVisible();
  await audio.evaluate(async (element) => {
    await (element as HTMLAudioElement).play();
  });
  expect(
    await audio.evaluate((element) => (element as HTMLAudioElement).paused),
  ).toBe(false);
  await audio.evaluate((element) => (element as HTMLAudioElement).pause());
  expect(writes.filter((request) => request.method !== "GET")).toHaveLength(0);
});

test("unavailable entries and signed media have a visible recovery path", async ({
  page,
}) => {
  const media = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "audio",
    mimeType: "audio/wav",
    sizeBytes: 3,
    status: "ready",
    createdAt: stamp,
  };
  await journal(page, [entry({ media: [media] })]);
  let recover = false;
  await page.route("**/api/v1/journal/entries/*/media/*/access", (route) =>
    recover
      ? route.fulfill({
          json: {
            url: "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=",
            expiresIn: 60,
          },
        })
      : route.fulfill({
          status: 503,
          json: {
            error: {
              code: "UNAVAILABLE",
              message: "Tạm thời chưa mở được tệp.",
            },
          },
        }),
  );
  await page.goto(`/#/self/entry/${entry().id}`);
  await expect(
    page.getByRole("button", { name: "Thử mở lại", exact: true }),
  ).toBeVisible();
  recover = true;
  await page.getByRole("button", { name: "Thử mở lại", exact: true }).click();
  await expect(
    page.getByLabel("Bản ghi âm của khoảnh khắc", { exact: true }),
  ).toBeVisible();
  await page.goto("/#/self/entry/99999999-9999-4999-8999-999999999999");
  await expect(
    page.getByRole("heading", {
      name: "Khoảnh khắc chưa mở được",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Một buổi chiều bình yên", { exact: true }),
  ).toHaveCount(0);
});

test("timeline attachment previews open lazily while all moods remain visible", async ({
  page,
}) => {
  const media = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "image",
    mimeType: "image/png",
    sizeBytes: 68,
    status: "ready",
    createdAt: stamp,
  };
  await journal(page, [
    entry({ media: [media] }),
    entry({
      id: "44444444-4444-4444-8444-444444444444",
      mood: 2,
      text: "Một ngày chậm lại",
    }),
  ]);
  let access = 0;
  await page.route("**/api/v1/journal/entries/*/media/*/access", (route) => {
    access++;
    return route.fulfill({
      json: {
        url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF3sAAAAASUVORK5CYII=",
        expiresIn: 60,
      },
    });
  });
  await page.goto("/#/self/memories");
  await expect(
    page.getByText("Một buổi chiều bình yên", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: "Ảnh trong khoảnh khắc của bạn",
      exact: true,
    }),
  ).toBeVisible();
  expect(access).toBe(1);
  await expect(
    page.getByText("Một ngày chậm lại", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Xem ảnh lớn hơn", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Ảnh trong khoảnh khắc", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Đóng", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Xem ảnh lớn hơn", exact: true }),
  ).toBeFocused();
});

test("empty memories explain the next step and open the existing editor", async ({
  page,
}) => {
  await journal(page, [entry({ status: "draft" })]);
  await page.goto("/#/self/memories");
  await expect(
    page.getByRole("heading", { name: "Chưa có khoảnh khắc nào", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  await page
    .getByRole("link", { name: "Viết khoảnh khắc đầu tiên", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("1 bản nháp đã lưu")).toBeVisible();
});

test("load-more failures retain moments and retry reconciles insertions across the API page cap", async ({
  page,
}) => {
  const rows = Array.from({ length: 65 }, (_, i) =>
    entry({
      id: `33333333-3333-4333-8333-${String(100 - i).padStart(12, "0")}`,
      localDate: i < 13 ? "2026-10-23" : "2026-09-30",
      text: `Kỷ niệm ${i}`,
    }),
  );
  await journal(page, rows);
  let fail = false;
  await page.route("**/api/v1/journal/entries?*", (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: {
            error: {
              code: "UNAVAILABLE",
              message: "Chưa tải được khoảnh khắc. Hãy thử lại.",
            },
          },
        })
      : route.fallback(),
  );
  await page.goto("/#/self/memories");
  const cards = page.locator(".journal-timeline article");
  await expect(cards).toHaveCount(12);
  fail = true;
  await page
    .getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true })
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(cards).toHaveCount(12);
  fail = false;
  rows.unshift(
    entry({
      id: "99999999-9999-4999-8999-999999999999",
      text: "Khoảnh khắc vừa thêm",
    }),
  );
  await page.getByRole("button", { name: "Thử lại", exact: true }).click();
  await expect(cards).toHaveCount(24);
  await expect(cards.first()).toContainText("Khoảnh khắc vừa thêm");
  for (const count of [36, 48, 60, 66]) {
    await page
      .getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true })
      .click();
    await expect(cards).toHaveCount(count);
  }
  await expect(
    page.getByRole("heading", { name: "Tháng 10, 2026", exact: true }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "Tháng 9, 2026", exact: true }),
  ).toHaveCount(1);
  const ids = await cards.evaluateAll((nodes) => nodes.map((node) => node.id));
  expect(new Set(ids).size).toBe(66);
  await expect(cards.last()).toContainText("Kỷ niệm 64");
  await expect(
    page.getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true }),
  ).toHaveCount(0);
});

test("timeline long text, keyboard menu and intentional deletion preserve the remaining moments", async ({
  page,
}) => {
  await journal(page, [
    entry({ text: "Dòng đầu tiên.\n\n" + "Một đoạn kể dài. ".repeat(45) }),
    entry({
      id: "22222222-2222-4222-8222-222222222222",
      text: "Giữ khoảnh khắc này",
    }),
  ]);
  await page.goto("/#/self/memories");
  const card = page.locator(".journal-timeline article").first();
  await card.getByRole("button", { name: "Xem thêm", exact: true }).click();
  await expect(
    card.getByRole("button", { name: "Thu gọn", exact: true }),
  ).toHaveAttribute("aria-expanded", "true");
  expect(
    await card
      .locator("p.is-open")
      .evaluate((node) => getComputedStyle(node).whiteSpace),
  ).toBe("pre-wrap");
  await card.getByRole("button", { name: "Thu gọn", exact: true }).click();
  const menu = card.getByRole("button", { name: /Thao tác với khoảnh khắc/ });
  await menu.focus();
  await page.keyboard.press("Enter");
  await expect(
    card.getByRole("menuitem", { name: "Chỉnh sửa khoảnh khắc", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: "Xóa khoảnh khắc này?",
    exact: true,
  });
  await expect(
    dialog.getByRole("button", { name: "Giữ lại", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(".journal-timeline article")).toHaveCount(2);
  await menu.click();
  await card
    .getByRole("menuitem", { name: "Xóa khoảnh khắc", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Xóa vĩnh viễn", exact: true })
    .click();
  await expect(page.locator(".journal-timeline article")).toHaveCount(1);
  await expect(
    page.getByText("Giữ khoảnh khắc này", { exact: true }),
  ).toBeVisible();
});

test("returning from editing an older moment restores depth, scroll and refreshed text", async ({
  page,
}) => {
  await journal(
    page,
    Array.from({ length: 15 }, (_, i) =>
      entry({
        id: `33333333-3333-4333-8333-${String(100 - i).padStart(12, "0")}`,
        text: `Khoảnh khắc ${i}`,
      }),
    ),
  );
  await page.goto("/#/self/memories");
  await page
    .getByRole("button", { name: "Xem thêm khoảnh khắc", exact: true })
    .click();
  const older = page.locator(".journal-timeline article").last();
  await older.scrollIntoViewIfNeeded();
  await older.getByRole("button", { name: /Thao tác với khoảnh khắc/ }).click();
  await older
    .getByRole("menuitem", { name: "Chỉnh sửa khoảnh khắc", exact: true })
    .click();
  const savedY = await page.evaluate(() =>
    Number(sessionStorage.getItem("journal-feed-scroll")),
  );
  expect(savedY).toBeGreaterThan(500);
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill("Khoảnh khắc đã chỉnh sửa");
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu khoảnh khắc" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Khoảnh khắc của bạn", exact: true })
    .click();
  await expect(page.locator(".journal-timeline article")).toHaveCount(15);
  await expect(
    page.getByText("Khoảnh khắc đã chỉnh sửa", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(savedY - 150);
});

test("broken attachment files offer recovery instead of a broken thumbnail", async ({
  page,
}) => {
  const photo = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "image",
    mimeType: "image/png",
    sizeBytes: 68,
    status: "ready",
    createdAt: stamp,
  };
  await journal(page, [entry({ media: [photo] })]);
  let broken = true;
  await page.route("**/api/v1/journal/entries/*/media/*/access", (route) =>
    route.fulfill({
      json: {
        url: broken
          ? "data:image/png;base64,YmFk"
          : "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF3sAAAAASUVORK5CYII=",
        expiresIn: 60,
      },
    }),
  );
  await page.goto("/#/self/memories");
  await expect(
    page.getByText("Chưa mở được tệp đính kèm.", { exact: true }),
  ).toBeVisible();
  broken = false;
  await page.getByRole("button", { name: "Thử mở lại", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Xem ảnh lớn hơn", exact: true }),
  ).toBeVisible();
});

test("image navigation clears the previous photo while the next access request is delayed", async ({
  page,
}) => {
  await journal(page, [
    entry({
      media: [1, 2].map((number) => ({
        id: `55555555-5555-4555-8555-${String(number).padStart(12, "0")}`,
        type: "image",
        mimeType: "image/jpeg",
        sizeBytes: 1000,
        status: "ready",
        createdAt: stamp,
      })),
    }),
  ]);
  const first = `data:image/jpeg;base64,${(await readFile(path.resolve("tests/fixtures/journal/forest.jpg"))).toString("base64")}`;
  const second = `data:image/jpeg;base64,${(await readFile(path.resolve("tests/fixtures/journal/sunrise.jpg"))).toString("base64")}`;
  let secondReads = 0;
  let release = () => {};
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/api/v1/journal/entries/*/media/*/access",
    async (route) => {
      const isSecond = route.request().url().includes("000000000002");
      if (isSecond && ++secondReads > 1) await delayed;
      return route.fulfill({
        json: { url: isSecond ? second : first, expiresIn: 60 },
      });
    },
  );
  await page.goto("/#/self/memories");
  await expect(
    page.getByRole("button", { name: "Xem ảnh lớn hơn", exact: true }),
  ).toHaveCount(2);
  await page
    .getByRole("button", { name: "Xem ảnh lớn hơn", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Ảnh trong khoảnh khắc",
    exact: true,
  });
  await expect
    .poll(
      async () => (await dialog.locator("img").getAttribute("src")) === first,
    )
    .toBe(true);
  await dialog.getByRole("button", { name: "Ảnh sau", exact: true }).click();
  await expect(dialog.locator("img")).toHaveCount(0);
  release();
  await expect
    .poll(
      async () => (await dialog.locator("img").getAttribute("src")) === second,
    )
    .toBe(true);
  await page.keyboard.press("ArrowLeft");
  await expect
    .poll(
      async () => (await dialog.locator("img").getAttribute("src")) === first,
    )
    .toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("timeline audio and video play, advance and pause using existing native controls", async ({
  page,
}) => {
  await journal(page, [
    entry({
      media: [
        {
          id: "55555555-5555-4555-8555-555555555551",
          type: "audio",
          mimeType: "audio/wav",
          sizeBytes: 32044,
          status: "ready",
          createdAt: stamp,
        },
        {
          id: "55555555-5555-4555-8555-555555555552",
          type: "video",
          mimeType: "video/webm",
          sizeBytes: 1000,
          status: "ready",
          createdAt: stamp,
        },
      ],
    }),
  ]);
  await page.goto("/#/self/memories");
  const videoUrl = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 100;
    const stream = canvas.captureStream(10);
    const recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => chunks.push(event.data);
    const done = new Promise<string>((resolve) => {
      recorder.onstop = () => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.readAsDataURL(new Blob(chunks, { type: "video/webm" }));
        stream.getTracks().forEach((track) => track.stop());
      };
    });
    recorder.start();
    for (let i = 0; i < 8; i++) {
      const context = canvas.getContext("2d")!;
      context.fillStyle = i % 2 ? "#285c4b" : "#e0e9de";
      context.fillRect(0, 0, 160, 100);
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    recorder.stop();
    return done;
  });
  await page.route("**/api/v1/journal/entries/*/media/*/access", (route) =>
    route.fulfill({
      json: {
        url: route.request().url().includes("555555555551")
          ? syntheticAudio()
          : videoUrl,
        expiresIn: 60,
      },
    }),
  );
  await page.reload();
  for (const label of ["Bản ghi âm của khoảnh khắc", "Video của khoảnh khắc"]) {
    const player = page.getByLabel(label, { exact: true });
    await expect(player).toHaveAttribute("controls", "");
    await player.scrollIntoViewIfNeeded();
    await player.evaluate((node) => (node as HTMLMediaElement).play());
    await expect
      .poll(() =>
        player.evaluate((node) => (node as HTMLMediaElement).currentTime),
      )
      .toBeGreaterThan(0.1);
    await player.evaluate((node) => (node as HTMLMediaElement).pause());
    expect(
      await player.evaluate((node) => (node as HTMLMediaElement).paused),
    ).toBe(true);
    expect(
      await player.evaluate((node) => (node as HTMLMediaElement).duration),
    ).toBeGreaterThan(0);
  }
});

for (const width of [390, 430, 768, 1280, 1440]) {
  test(`emotion timeline visual and accessibility check at ${width}px`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width, height: 1000 });
    await journal(page, [
      entry({
        text: "Nói chuyện với bạn thân, cảm thấy dễ chịu hơn nhiều.\n\nCó những ngày, chỉ cần được lắng nghe là đủ.",
        media: [1, 2, 3].map((i) => ({
          id: `55555555-5555-4555-8555-${String(i).padStart(12, "0")}`,
          type: "image",
          mimeType: "image/png",
          sizeBytes: 68,
          status: "ready",
          createdAt: stamp,
        })),
      }),
      entry({
        id: "22222222-2222-4222-8222-222222222222",
        mood: 2,
        text: "Sáng nay dậy khá muộn, cảm thấy thiếu năng lượng. Mình cho phép bản thân chậm lại một chút.",
        createdAt: "2026-10-23T01:30:00Z",
      }),
      entry({
        id: "11111111-1111-4111-8111-111111111111",
        mood: 3,
        localDate: "2026-09-30",
        text: "Học bài ở thư viện. Một buổi chiều bình thường, nhưng thật đáng nhớ.",
      }),
    ]);
    const photos = await Promise.all(
      ["forest", "sunrise", "coffee"].map(
        async (name) =>
          `data:image/jpeg;base64,${(await readFile(path.resolve(`tests/fixtures/journal/${name}.jpg`))).toString("base64")}`,
      ),
    );
    await page.route("**/api/v1/journal/entries/*/media/*/access", (route) => {
      const id = route.request().url().split("/").at(-2)!;
      return route.fulfill({
        json: {
          url: id.startsWith("6666")
            ? syntheticAudio()
            : photos[Number(id.slice(-1)) - 1],
          expiresIn: 60,
        },
      });
    });
    await page.goto("/#/self/memories");
    await expect(page.locator(".journal-timeline article")).toHaveCount(3);
    await expect(
      page.getByRole("img", {
        name: "Ảnh trong khoảnh khắc của bạn",
        exact: true,
      }),
    ).toHaveCount(3);
    await expect
      .poll(() =>
        page
          .locator(".journal-gallery img")
          .evaluateAll((nodes) =>
            nodes.every(
              (node) =>
                (node as HTMLImageElement).complete &&
                (node as HTMLImageElement).naturalWidth > 1,
            ),
          ),
      )
      .toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - innerWidth,
      ),
    ).toBeLessThanOrEqual(1);
    if (width < 768)
      await expect(
        page.getByRole("navigation", { name: "Điều hướng chính" }),
      ).toBeVisible();
    const scan = await new AxeBuilder({ page })
      .include(".journal-timeline-page")
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(scan.violations).toEqual([]);
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    const output = artifactPath("emotion-timeline");
    await mkdir(output, { recursive: true });
    await page.screenshot({
      path: path.join(output, `timeline-${width}.png`),
      fullPage: true,
    });
  });
}

test("journal experiences have accessible rendered evidence", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 1000 });
  const photo = {
    id: "55555555-5555-4555-8555-555555555555",
    type: "image",
    mimeType: "image/png",
    sizeBytes: 68,
    status: "ready",
    createdAt: stamp,
  };
  const png =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF3sAAAAASUVORK5CYII=";
  await journal(page, [
    entry({ media: [photo] }),
    entry({
      id: "44444444-4444-4444-8444-444444444444",
      mood: 2,
      text: "Sáng nay mình cần nghỉ một chút.",
      createdAt: "2026-10-23T01:30:00Z",
    }),
  ]);
  await page.route("**/api/v1/journal/entries/*/media/*/access", (route) =>
    route.fulfill({
      json: { url: `data:image/png;base64,${png}`, expiresIn: 60 },
    }),
  );
  const output = artifactPath("journal");
  await mkdir(output, { recursive: true });
  for (const [name, route, heading] of [
    ["01-checkin-mobile", "/self", "Nhật ký cảm xúc"],
    ["04-calendar-mobile", "/self/calendar", "Lịch nhật ký"],
    ["05-timeline-mobile", "/self/memories", "Khoảnh khắc của bạn"],
  ]) {
    await page.goto(`/#${route}`);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    await expect(page.locator(".journal-page")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - innerWidth,
      ),
    ).toBeLessThanOrEqual(1);
    const scan = await new AxeBuilder({ page })
      .include(".journal-page")
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(scan.violations).toEqual([]);
    if (route === "/self/memories")
      await expect(
        page.getByRole("img", {
          name: "Ảnh trong khoảnh khắc của bạn",
          exact: true,
        }),
      ).toBeVisible();
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: path.join(output, `${name}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: path.join(output, "01-checkin-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.goto("/#/self");
  await expect(
    page.getByRole("heading", { name: "Nhật ký cảm xúc", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Ghi lại khoảnh khắc", exact: true })
    .fill(
      "Mình đã dành một khoảng nghỉ nhỏ. Một lời viết, một hình ảnh và âm thanh để nhớ lại.",
    );
  await page.getByLabel("Thêm hình ảnh", { exact: true }).setInputFiles({
    name: "anh-minh-hoa.png",
    mimeType: "image/png",
    buffer: Buffer.from(png, "base64"),
  });
  const wav = Buffer.alloc(16044);
  wav.write("RIFF", 0);
  wav.writeUInt32LE(16036, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(8000, 24);
  wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(16000, 40);
  await page.getByLabel("Thêm âm thanh", { exact: true }).setInputFiles({
    name: "ghi-am-minh-hoa.wav",
    mimeType: "audio/wav",
    buffer: wav,
  });
  const video = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 120;
    const stream = canvas.captureStream(10),
      recorder = new MediaRecorder(stream, { mimeType: "video/webm" }),
      chunks: Blob[] = [];
    const data = new Promise<number[]>((resolve) => {
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () =>
        resolve(
          Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer())),
        );
    });
    recorder.start();
    canvas.getContext("2d")!.fillRect(0, 0, 160, 120);
    await new Promise((r) => setTimeout(r, 200));
    recorder.stop();
    stream.getTracks().forEach((track) => track.stop());
    return await data;
  });
  await page.getByLabel("Thêm video", { exact: true }).setInputFiles({
    name: "video-minh-hoa.webm",
    mimeType: "video/webm",
    buffer: Buffer.from(video),
  });
  await page
    .locator(".journal-editor")
    .screenshot({ path: path.join(output, "02-editor-mobile.png") });
  await page.locator(".journal-save-actions").scrollIntoViewIfNeeded();
  const save = await page.locator(".journal-save-actions").boundingBox(),
    nav = await page
      .getByRole("navigation", { name: "Điều hướng chính" })
      .boundingBox();
  expect(save!.y + save!.height).toBeLessThanOrEqual(nav!.y);
  await page.screenshot({
    path: path.join(output, "mobile-save-clearance.png"),
  });
});

for (const width of [360, 390, 430, 768, 1024, 1280, 1440]) {
  test(`journal rendered layout and safe navigation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await journal(page, [entry()]);
    await page.goto("/#/self");
    await expect(
      page.getByRole("heading", { name: "Nhật ký cảm xúc", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("radio")).toHaveCount(5);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - innerWidth,
      ),
    ).toBeLessThanOrEqual(1);
    if (width < 768) {
      const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
      expect((await nav.boundingBox())!.y).toBeGreaterThan(800);
    }
    const output = artifactPath("journal");
    await mkdir(output, { recursive: true });
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: path.join(output, `viewport-${width}.png`),
      fullPage: true,
    });
    if (width === 360) {
      await page.goto("/#/self/calendar");
      await expect(
        page.getByRole("heading", { name: "Lịch nhật ký", exact: true }),
      ).toBeVisible();
      const box = await page
        .locator(".journal-calendar-day")
        .first()
        .boundingBox();
      expect(box!.width).toBeGreaterThanOrEqual(44);
    }
  });
}
