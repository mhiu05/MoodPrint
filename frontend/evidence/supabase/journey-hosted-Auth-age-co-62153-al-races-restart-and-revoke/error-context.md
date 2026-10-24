# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey.spec.ts >> hosted Auth, age, consent, private data, SDK memory, social races, restart and revoke
- Location: tests\supabase\journey.spec.ts:53:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Synthetic owner 1fd18481', { exact: true })
Expected: visible
Timeout: 20000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('Synthetic owner 1fd18481', { exact: true }) with timeout 20000ms
  - waiting for getByText('Synthetic owner 1fd18481', { exact: true })

```

```yaml
- link "Đến nội dung chính":
  - /url: "#main"
- complementary:
  - link "Me2We — Trợ lý":
    - /url: "#/assistants"
  - navigation "Điều hướng chính":
    - link "Trợ lý":
      - /url: "#/assistants"
      - img
      - text: Trợ lý
    - link "Tìm bạn":
      - /url: "#/connect"
      - img
      - text: Tìm bạn
    - link "Tin nhắn":
      - /url: "#/messages"
      - img
      - text: Tin nhắn
    - link "Tôi":
      - /url: "#/profile"
      - img
      - text: Tôi
  - link "Quyền riêng tư":
    - /url: "#/settings"
    - img
  - link "Hồ sơ của tôi":
    - /url: "#/profile"
    - text: B
- main:
  - link "Me2We — Trợ lý":
    - /url: "#/assistants"
    - text: Me2We .
  - link "Quyền riêng tư":
    - /url: "#/settings"
    - img
  - link "Về tin nhắn":
    - /url: "#/messages"
    - img
  - heading "Bạn đồng hành b8bfa9" [level=1]
  - log "Tin nhắn trong kết nối":
    - paragraph: Supabase chat 1fd18481
    - paragraph: Supabase duplicate 1fd18481
  - textbox "Tin nhắn cho bạn kết nối":
    - /placeholder: Gửi một lời hỏi thăm…
  - button "Gửi tin nhắn" [disabled]:
    - img
  - button "Kết thúc kết nối"
  - group:
    - text: Chia sẻ và an toàn
    - heading "Chia sẻ theo lựa chọn của bạn" [level=2]
    - paragraph: Mỗi thông tin có quyền riêng. Chia sẻ không mở quyền xem các ghi chép hay hội thoại khác.
    - button "Xin xem tên hiển thị"
    - button "Xin xem giới tính"
    - article:
      - heading "Tên hiển thị · Thông tin của người kia" [level=3]
      - paragraph: Đang được chia sẻ
      - button "Xem thông tin đã được chia sẻ"
      - paragraph: Synthetic owner 48952050
    - heading "Báo cáo nội dung" [level=2]
    - paragraph: Bạn có thể chọn tối đa hai tin nhắn làm bằng chứng. Chặn kết nối là một lựa chọn riêng.
    - text: Lý do báo cáo
    - textbox "Lý do báo cáo"
    - group "Tin nhắn bạn muốn chọn":
      - text: Tin nhắn bạn muốn chọn
      - checkbox "Supabase chat 1fd18481"
      - text: Supabase chat 1fd18481
      - checkbox "Supabase duplicate 1fd18481"
      - text: Supabase duplicate 1fd18481
    - button "Gửi báo cáo" [disabled]
    - button "Chặn kết nối này"
```

# Test source

```ts
  52  | 
  53  | test("hosted Auth, age, consent, private data, SDK memory, social races, restart and revoke", async ({ browser }) => {
  54  |   const a = await browser.newContext(), b = await browser.newContext();
  55  |   try {
  56  |     const one = await a.newPage(), two = await b.newPage();
  57  |     await login(one, "A"); await login(two, "B");
  58  |     record("realLoginUiAndHttpOnlySession");
  59  |     const sessionA = await request(a, "GET", "/session"), sessionB = await request(b, "GET", "/session");
  60  |     const year = Number(new Intl.DateTimeFormat("en", { timeZone: "Asia/Bangkok", year: "numeric" }).format(new Date(sessionA.serverTime)));
  61  |     for (const [page, session, offset] of [[one, sessionA, 18], [two, sessionB, 20]] as const) {
  62  |       if (session.ageBand === "unknown") {
  63  |         expect(Object.values(session.consents).every((c: any) => !c.enabled)).toBe(true);
  64  |         await page.getByLabel("Năm sinh", { exact: true }).fill(String(year - offset));
  65  |         await page.getByRole("checkbox", { name: "Tôi xác nhận mình đã đủ 16 tuổi.", exact: true }).check();
  66  |         await page.getByRole("button", { name: "Xác nhận năm sinh", exact: true }).click();
  67  |         await expect(page.getByRole("heading", { name: /Bạn muốn kể gì/ })).toBeVisible();
  68  |       }
  69  |     }
  70  |     if ((await request(a, "GET", "/session")).ageBand === "teen") {
  71  |       await request(a, "PUT", "/consents/MATCH", { enabled: true, expectedVersion: 1, policyVersion: "v1" }, 403);
  72  |       record("teenSocialDeniedBeforeAdultConfirmation");
  73  |       await one.goto(base + "/#/settings");
  74  |       await one.getByRole("checkbox", { name: /Tôi xác nhận mình đã đủ 18 tuổi/ }).check();
  75  |       await one.getByRole("button", { name: "Xác nhận đủ 18 tuổi", exact: true }).click();
  76  |       await expect(one.getByRole("button", { name: "Xác nhận đủ 18 tuổi", exact: true })).toHaveCount(0);
  77  |     }
  78  |     expect((await request(a, "GET", "/session")).ageBand).toBe("adult");
  79  |     record("onboardingPrivate16PlusAndExplicit18Boundary");
  80  |     const tag = randomUUID().slice(0, 8), privateText = `Supabase private ${tag}`, moodText = `Supabase mood ${tag}`, aliasText = `Synthetic owner ${tag}`;
  81  |     const item = await request(a, "POST", "/profiles/private-items", { text: privateText }, 201);
  82  |     await request(b, "PATCH", `/profiles/private-items/${item.id}`, { text: "must not change owner data", expectedVersion: 1 }, 404);
  83  |     expect((await request(b, "GET", "/profiles/private-items")).some((x: any) => x.id === item.id)).toBe(false);
  84  |     record("crossUserPrivateReadAndWriteDenied");
  85  |     await one.goto(base + "/#/profile"); await expect(one.getByText(privateText, { exact: true })).toBeVisible();
  86  |     await one.reload(); await expect(one.getByText(privateText, { exact: true })).toBeVisible();
  87  |     await one.getByRole("textbox", { name: "Tên hiển thị", exact: true }).fill(aliasText);
  88  |     await one.getByRole("button", { name: "Lưu tên hiển thị", exact: true }).click();
  89  |     await expect(one.getByText("Đã cập nhật thông tin riêng.", { exact: true })).toBeVisible();
  90  |     await one.goto(base + "/#/self");
  91  |     await one.getByRole("textbox", { name: "Ghi chú", exact: true }).fill(moodText);
  92  |     await one.getByRole("button", { name: "Lưu tâm trạng", exact: true }).click();
  93  |     await expect(one.getByText("Đã lưu tâm trạng.", { exact: true })).toBeVisible();
  94  |     await one.reload(); await expect(one.locator("article").getByText(moodText, { exact: true })).toBeVisible();
  95  |     record("privateAndMoodPersistenceAcrossReload");
  96  |     await enable(one, "trò chuyện AI"); await enable(one, "ghi nhớ đã duyệt");
  97  |     await one.goto(base + "/#/assistants/may");
  98  |     await one.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("SYNTHETIC_MEMORY_PROPOSAL");
  99  |     await one.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  100 |     await expect(one.getByText("Mình đã nhận được chia sẻ của bạn.", { exact: true })).toBeVisible();
  101 |     await expect(one.getByText("UNVALIDATED-RAW-CANARY", { exact: true })).toHaveCount(0);
  102 |     const proposals = await request(a, "GET", "/proposals");
  103 |     expect(proposals.length > 0).toBe(true);
  104 |     const otherSession = await request(b, "GET", "/session");
  105 |     if (!otherSession.consents.AI.enabled || !otherSession.consents.MEM.enabled)
  106 |       await request(b, "POST", `/proposals/${proposals[0].id}/confirm`, { expectedVersion: 1, editedText: "must not approve" }, 403);
  107 |     await enable(two, "trò chuyện AI"); await enable(two, "ghi nhớ đã duyệt");
  108 |     await request(b, "POST", `/proposals/${proposals[0].id}/confirm`, { expectedVersion: 1, editedText: "must not approve" }, 404);
  109 |     const memoryText = `Supabase approved memory ${tag}`;
  110 |     await one.goto(base + "/#/memory");
  111 |     await one.getByRole("textbox", { name: "Nội dung bạn muốn duyệt" }).first().fill(memoryText);
  112 |     await one.getByRole("button", { name: "Duyệt và lưu", exact: true }).first().click();
  113 |     await expect(one.getByText(memoryText, { exact: true })).toBeVisible();
  114 |     await one.reload(); await expect(one.getByText(memoryText, { exact: true })).toBeVisible();
  115 |     expect((await request(b, "GET", "/memories")).some((x: any) => x.text === memoryText)).toBe(false);
  116 |     record("sdkFakeModelProposalOwnerApprovalAndMemoryPersistence");
  117 |     await publish(one); await publish(two);
  118 |     const ca = (await request(a, "GET", "/matching/candidates")).candidates;
  119 |     const cb = (await request(b, "GET", "/matching/candidates")).candidates;
  120 |     expect(ca.length).toBe(1); expect(cb.length).toBe(1);
  121 |     const invites = await Promise.all([
  122 |       request(a, "POST", "/connection-requests", { candidateRef: ca[0].candidateRef }, 201),
  123 |       request(b, "POST", "/connection-requests", { candidateRef: cb[0].candidateRef }, 201),
  124 |     ]);
  125 |     expect(invites.length).toBe(2);
  126 |     const roomsA = await request(a, "GET", "/connections"), roomsB = await request(b, "GET", "/connections");
  127 |     expect(roomsA.length).toBe(1); expect(roomsB.length).toBe(1); expect(roomsA[0].id === roomsB[0].id).toBe(true);
  128 |     const room = roomsA[0].id, path = `/connections/${room}/messages`;
  129 |     record("publishMatchingAndConcurrentMutualRequestsSingleRoom");
  130 |     await one.goto(base + `/#/chat/${room}`); await two.goto(base + `/#/chat/${room}`);
  131 |     const chatText = `Supabase chat ${tag}`;
  132 |     await one.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" }).fill(chatText);
  133 |     await one.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
  134 |     await expect(two.getByRole("log").getByText(chatText, { exact: true })).toBeVisible();
  135 |     const payload = { clientMessageId: randomUUID(), text: `Supabase duplicate ${tag}` };
  136 |     const retry = await Promise.all([request(a, "POST", path, payload, 201), request(a, "POST", path, payload, 201)]);
  137 |     expect(retry[0].id === retry[1].id).toBe(true);
  138 |     record("realtimeChatAndConcurrentMessageDeduplication");
  139 |     writeFileSync(artifacts + "supabase-restart-request.json", JSON.stringify({ restart: true }));
  140 |     await expect.poll(() => existsSync(artifacts + "supabase-restart-ack.json"), { timeout: 50000 }).toBe(true);
  141 |     const restart = JSON.parse(readFileSync(artifacts + "supabase-restart-ack.json", "utf8"));
  142 |     expect(restart.oldPid !== restart.newPid).toBe(true);
  143 |     await two.reload(); await expect(two.getByRole("log").getByText(chatText, { exact: true })).toBeVisible();
  144 |     expect((await request(a, "GET", "/profiles/private-items")).some((x: any) => x.id === item.id)).toBe(true);
  145 |     expect((await request(a, "GET", "/memories")).some((x: any) => x.text === memoryText)).toBe(true);
  146 |     record("backendProcessRestartRetainsSessionsPrivateMemoryAndChat");
  147 |     await two.locator("summary").filter({ hasText: "Chia sẻ và an toàn" }).click();
  148 |     await two.getByRole("button", { name: "Xin xem tên hiển thị", exact: true }).click();
  149 |     await one.reload(); await one.locator("summary").filter({ hasText: "Chia sẻ và an toàn" }).click();
  150 |     await one.getByRole("button", { name: "Đồng ý chia sẻ", exact: true }).click();
  151 |     await two.getByRole("button", { name: "Xem thông tin đã được chia sẻ", exact: true }).click();
> 152 |     await expect(two.getByText(aliasText, { exact: true })).toBeVisible();
      |                                                             ^ Error: expect(locator).toBeVisible() failed
  153 |     await one.getByRole("button", { name: "Thu hồi chia sẻ", exact: true }).click();
  154 |     await expect(two.getByText(aliasText, { exact: true })).toHaveCount(0);
  155 |     record("ownerRevealGrantAndRevoke");
  156 |     await two.getByRole("textbox", { name: "Lý do báo cáo", exact: true }).fill("Synthetic hosted E2E report");
  157 |     await two.getByRole("checkbox", { name: chatText, exact: true }).check();
  158 |     await two.getByRole("button", { name: "Gửi báo cáo", exact: true }).click();
  159 |     await expect(two.getByText("Đã nhận báo cáo.", { exact: true })).toBeVisible();
  160 |     await two.getByRole("button", { name: "Chặn kết nối này", exact: true }).click();
  161 |     await two.getByRole("button", { name: "Xác nhận chặn", exact: true }).click();
  162 |     await request(a, "GET", path, undefined, 403);
  163 |     await request(a, "POST", path, { clientMessageId: randomUUID(), text: "must not send" }, 403);
  164 |     record("reportReceiptAndBlockImmediatelyDenyBothDirections");
  165 |     // Sign out all provider sessions belonging only to synthetic account B.
  166 |     const provider = process.env.MOODPRINT_TEST_SUPABASE_URL!;
  167 |     const key = process.env.MOODPRINT_TEST_PUBLISHABLE_KEY!;
  168 |     const auth = await fetch(provider + "/auth/v1/token?grant_type=password", { method: "POST", headers: { apikey: key, "Content-Type": "application/json" },
  169 |       body: JSON.stringify({ email: process.env.MOODPRINT_TEST_B_EMAIL, password: process.env.MOODPRINT_TEST_B_PASSWORD }) });
  170 |     expect(auth.status).toBe(200);
  171 |     const token = (await auth.json()).access_token;
  172 |     const revoked = await fetch(provider + "/auth/v1/logout?scope=global", { method: "POST", headers: { apikey: key, Authorization: `Bearer ${token}` } });
  173 |     expect(revoked.ok).toBe(true);
  174 |     await request(b, "GET", "/session", undefined, 401);
  175 |     record("providerSessionRevokeInvalidatesOpaqueAppSession");
  176 |     const oldCookies = await a.cookies(base);
  177 |     await request(a, "POST", "/auth/logout", {}, 204);
  178 |     await request(a, "GET", "/session", undefined, 401);
  179 |     const replay = await browser.newContext(); await replay.addCookies(oldCookies);
  180 |     await request(replay, "GET", "/session", undefined, 401); await replay.close();
  181 |     record("logoutAndOldCookieReplayDenied");
  182 |     proof.status = "PASS_SCOPED_HOSTED_JOURNEY";
  183 |     writeFileSync(artifacts + "supabase-e2e-checkpoints.json", JSON.stringify(proof, null, 2));
  184 |   } finally { await a.close(); await b.close(); }
  185 | });
  186 | 
  187 | test("hosted Nhịp reads only the explicitly selected mood dates and never private notes", async ({ browser }) => {
  188 |   const context = await browser.newContext();
  189 |   try {
  190 |     const page = await context.newPage();
  191 |     await login(page, "A");
  192 |     await enable(page, "trò chuyện AI");
  193 |     await page.goto(base + "/#/assistants/nhip");
  194 |     const draft = page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" });
  195 |     await draft.fill("SYNTHETIC_MOOD_RANGE");
  196 |     await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  197 |     await expect(page.getByText("Chưa có khoảng thống kê được chia sẻ.", { exact: true })).toBeVisible();
  198 |     await page.getByText("Chia sẻ thống kê tâm trạng cho lượt này", { exact: true }).click();
  199 |     await page.getByRole("checkbox", { name: "Cho Nhịp đọc khoảng ngày mình chọn", exact: true }).check();
  200 |     const session = await request(context, "GET", "/session");
  201 |     const day = new Intl.DateTimeFormat("sv-SE", { timeZone: session.timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(session.serverTime));
  202 |     await page.getByLabel("Thống kê từ ngày", { exact: true }).fill(day);
  203 |     await page.getByLabel("Thống kê đến ngày", { exact: true }).fill(day);
  204 |     for (const width of [390, 1440]) {
  205 |       await page.setViewportSize({ width, height: 900 });
  206 |       const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  207 |       expect(axe.passes.length > 0).toBe(true); expect(axe.violations.length).toBe(0);
  208 |       expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  209 |       await page.screenshot({ path: artifacts + `visual/nhip-source-${width}.png`, fullPage: true });
  210 |     }
  211 |     await draft.fill("SYNTHETIC_MOOD_RANGE xem ngày mình chọn");
  212 |     await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  213 |     await expect(page.getByText("Đã xem thống kê bạn chọn, không có ghi chú.", { exact: true })).toBeVisible();
  214 |     await expect(page.getByRole("checkbox", { name: "Cho Nhịp đọc khoảng ngày mình chọn", exact: true })).not.toBeChecked();
  215 |     const tool = JSON.parse(readFileSync(artifacts + "supabase-scoped-tool-proof.json", "utf8"));
  216 |     expect(tool.unselectedToolNotExposed && tool.selectedRangeToolInvoked && tool.notesExcluded).toBe(true);
  217 |     expect(tool.fromDate === day && tool.toDate === day && tool.recordedDays === 1).toBe(true);
  218 |     await request(context, "POST", "/auth/logout", {}, 204);
  219 |   } finally { await context.close(); }
  220 | });
  221 | 
```