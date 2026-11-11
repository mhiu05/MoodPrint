"""Opt-in synthetic acceptance against the genuine metered localhost runtime.

Never imported by automatic tests. Auth/Storage traffic is restricted to the
audited project; application requests use loopback. Outputs and grades are
separate, and provider faults remain the deterministic regression layer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))

from evals.budget import BudgetLedger, load_budget  # noqa: E402
from safevoice_agent.companion import PROMPT_VERSION  # noqa: E402

from scripts.hosted_product import (  # noqa: E402
    ProjectTransport,
    headers,
    load_values,
    prepare,
    read_manifest,
    record_storage_key,
    run_checks,
    write_manifest,
)

OUTPUT = ROOT / ".local/fresh-supabase"
USERS = OUTPUT / "hosted-users.json"
API = "http://127.0.0.1:8000"


def ledger_snapshot() -> dict:
    path = Path(os.environ["SAFEVOICE_EVAL_BUDGET"])
    ledger = BudgetLedger(
        load_budget(path, scope="phase3-eval"), Path(os.environ["SAFEVOICE_EVAL_LEDGER"])
    )
    return {
        "calls": ledger.reserved_calls,
        "committed_usd": ledger.committed_usd,
        "spent_tokens": ledger.spent_tokens,
        "reserved_tokens": ledger.reserved_tokens,
        "unknown_calls": ledger.unknown_calls,
    }


def parse_sse(raw: str) -> dict:
    events = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    complete = [e["data"] for e in events if e["event"] == "message.completed"]
    terminal = [e["data"] for e in events if e["event"] in {"run.completed", "run.failed"}]
    return {
        "response": complete[-1].get("content") if complete else None,
        "structured": complete[-1].get("structured") if complete else None,
        "citations": complete[-1].get("citations", []) if complete else [],
        "partial_text": "".join(e["data"]["text"] for e in events if e["event"] == "message.delta")
        if not complete
        else None,
        "events": [e for e in events if e["event"] not in {"message.delta", "heartbeat"}],
        "event_names": [e["event"] for e in events],
        "status": terminal[-1] if terminal else None,
        "run_id": events[0].get("runId") if events else None,
        "approvals": [e["data"] for e in events if e["event"] == "approval.required"],
    }


class Harness:
    def __init__(self, group: str, label: str, actor: str = "A"):
        if actor not in {"A", "B"}:
            raise ValueError("Only the two tracked synthetic actors are authorized")
        self.values, self.group, self.label, self.actor = load_values(), group, label, actor
        self.head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        self.records, self.checks, self.tokens = [], [], []
        self.http = httpx.AsyncClient(base_url=API, timeout=150, trust_env=False)
        self.upstream = httpx.AsyncClient(transport=ProjectTransport(), timeout=30)

    async def start(self):
        self.manifest = read_manifest(USERS)
        self.default_owner_id = self.manifest["users"][0]["id"]
        if self.actor == "B":
            self.manifest["users"] = self.manifest["users"][::-1]
        self.owner_id = self.manifest["users"][0]["id"]
        for user in self.manifest["users"]:
            response = await self.upstream.post(
                self.values["SUPABASE_URL"] + "/auth/v1/token?grant_type=password",
                headers=headers(self.values),
                json={"email": user["email"], "password": user["password"]},
            )
            if (
                response.status_code != 200
                or response.json().get("user", {}).get("id") != user["id"]
            ):
                raise RuntimeError("Synthetic hosted login failed")
            self.tokens.append(response.json()["access_token"])
        if (await self.http.get("/ready")).status_code != 200:
            raise RuntimeError("The genuine local runtime is not ready")

    async def close(self):
        await self.http.aclose()
        await self.upstream.aclose()

    def check(self, name: str, passed: bool, detail=None):
        self.checks.append({"name": name, "passed": bool(passed), "detail": detail})
        self.save()
        print(f"{'PASS' if passed else 'FAIL'} {name}", flush=True)

    def save(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / f"{self.group}-{self.label}.json").write_text(
            json.dumps(
                {
                    "source_commit": self.head,
                    "model": "gpt-6-luna",
                    "group": self.group,
                    "actor": self.actor,
                    "owner_id": getattr(self, "owner_id", None),
                    "judge": "Codex direct review; separate grades file",
                    "records": self.records,
                    "checks": self.checks,
                    "ledger": ledger_snapshot(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    async def api(self, method, endpoint, body=None, *, user=0, expected=200):
        response = await self.http.request(
            method, endpoint, json=body, headers={"Authorization": "Bearer " + self.tokens[user]}
        )
        if response.status_code != expected:
            raise RuntimeError(
                f"{method} {endpoint} returned {response.status_code}; expected {expected}"
            )
        return response.json() if response.content else None

    def resource(self, kind, id):
        data = read_manifest(USERS)
        values = data.setdefault("resources", {}).setdefault(kind, [])
        if id not in values:
            values.append(id)
        data.setdefault("resource_owners", {}).setdefault(kind, {})[id] = self.owner_id
        write_manifest(USERS, data)

    async def conversation(self, title, *, case_id=None):
        id = str(uuid4())
        await self.api(
            "POST", "/v1/conversations", {"id": id, "title": title, "linkedCaseId": case_id}
        )
        self.resource("conversations", id)
        return id

    async def case(self, title):
        id = str(uuid4())
        await self.api(
            "POST",
            "/v1/cases",
            {
                "id": id,
                "title": title,
                "template": "TPL-FREE",
                "perspective": "self",
                "summary": "Synthetic local MVP verification only.",
                "status": "active",
            },
        )
        self.resource("cases", id)
        return id

    async def stream(
        self, scenario, conversation, prompt, *, client_id=None, decision=None, attachments=None
    ):
        before = ledger_snapshot()
        started_at = datetime.now(UTC).isoformat()
        provider_log = OUTPUT / "model-http.jsonl"
        trace_before = (
            len(provider_log.read_text(encoding="utf-8").splitlines())
            if provider_log.exists()
            else 0
        )
        if decision:
            endpoint = f"/v1/runs/{decision['run_id']}/approvals/{decision['approval_id']}"
            body = {"decision": decision["decision"]}
        else:
            endpoint = f"/v1/conversations/{conversation}/messages"
            body = {
                "clientMessageId": client_id or str(uuid4()),
                "content": prompt,
                "attachments": attachments or [],
            }
        response = await self.http.post(
            endpoint, json=body, headers={"Authorization": "Bearer " + self.tokens[0]}
        )
        if response.status_code != 200:
            result = {
                "http_status": response.status_code,
                "response": None,
                "events": [],
                "approvals": [],
                "run_id": None,
                "error_code": response.json().get("error", {}).get("code"),
            }
        else:
            result = {"http_status": 200, **parse_sse(response.text)}
        record = {
            "scenario_id": scenario,
            "prompt_version": PROMPT_VERSION,
            "model": "gpt-6-luna",
            "source_commit": self.head,
            "conversation_id": conversation,
            "user_message": prompt,
            "client_message_id": body.get("clientMessageId"),
            "decision": decision,
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "ledger_before": before,
            "ledger_after": ledger_snapshot(),
            **result,
        }
        if provider_log.exists():
            record["provider_requests"] = [
                {
                    "request_id": row["request_id"],
                    "http_status": row["http_status"],
                    "usage": (row.get("response") or {}).get("usage"),
                    "response_body_sha256": row["response_body_sha256"],
                }
                for row in [
                    json.loads(line)
                    for line in provider_log.read_text(encoding="utf-8").splitlines()[trace_before:]
                ]
            ]
        if result.get("run_id"):
            record["persisted_run"] = await self.api("GET", f"/v1/runs/{result['run_id']}")
        self.records.append(record)
        self.save()
        print(f"LIVE {scenario}: HTTP {result['http_status']}; {result.get('status')}", flush=True)
        return record

    async def basic(self, group):
        cases = json.loads((ROOT / "scripts/live_mvp_cases.json").read_text(encoding="utf-8"))[
            "cases"
        ]
        for case in [c for c in cases if c["group"] == group]:
            try:
                conversation = await self.conversation("Synthetic " + case["id"])
                for index, prompt in enumerate(case["turns"], 1):
                    record = await self.stream(f"{case['id']}-{index}", conversation, prompt)
                    self.check(
                        f"{case['id']}-{index} completed",
                        bool(record.get("response"))
                        and record.get("status", {}).get("status") == "completed",
                    )
                    if case.get("expected_urgency"):
                        actual = (record.get("structured") or {}).get("urgency")
                        self.check(
                            f"{case['id']}-{index} urgency",
                            actual == case["expected_urgency"],
                            {"expected": case["expected_urgency"], "actual": actual},
                        )
                messages = await self.api("GET", f"/v1/conversations/{conversation}/messages")
                self.check(
                    case["id"] + " persisted", len(messages["items"]) >= 2 * len(case["turns"])
                )
                await self.api("GET", f"/v1/conversations/{conversation}", user=1, expected=404)
                self.check(case["id"] + " isolated", True)
            except Exception as error:
                self.check(
                    case["id"] + " execution",
                    False,
                    {"error_type": type(error).__name__, "detail": str(error)},
                )

    async def approval(self):
        for decision, kind in [("approve", "event"), ("reject", "event"), ("approve", "plan")]:
            scenario = f"C-{kind}-{decision}"
            try:
                case = await self.case("Synthetic " + scenario)
                conversation = await self.conversation(scenario, case_id=case)
                prompt = (
                    "Hôm qua 9/11/2026 lúc 10 giờ sáng (UTC+07:00), bạn A nhắn 'đừng cho An vào nhóm' trong nhóm lớp. "
                    "Mình trực tiếp đọc tin nhắn. Mình đang an toàn. Giúp mình soạn một mốc trung lập cho hồ sơ này để xem trước; chưa lưu nhé."
                    if kind == "event"
                    else "Mình muốn nhờ cô chủ nhiệm hỗ trợ chuyện bị loại khỏi nhóm học tập. "
                    "Hãy soạn kế hoạch đúng hai bước nhỏ cho hồ sơ này: viết vài ý về điều đã xảy ra và hẹn gặp riêng cô. Cho mình xem trước, chưa lưu."
                )
                await self.stream(scenario + "-preview", conversation, prompt)
                save = await self.stream(
                    scenario + "-request-save",
                    conversation,
                    "Bản này đúng điều mình muốn. Lưu "
                    + ("mốc" if kind == "event" else "kế hoạch")
                    + " này vào hồ sơ nhé.",
                )
                if kind == "plan":
                    before = await self.http.get(
                        f"/v1/cases/{case}/plan",
                        headers={"Authorization": "Bearer " + self.tokens[0]},
                    )
                    self.check(scenario + " no write before decision", before.status_code == 404)
                else:
                    before = await self.api("GET", f"/v1/cases/{case}")
                    self.check(scenario + " no write before decision", len(before["events"]) == 0)
                self.check(scenario + " approval reached", len(save["approvals"]) == 1)
                if not save["approvals"]:
                    continue
                approval = save["approvals"][0]
                resumed = await self.stream(
                    scenario + "-decision",
                    conversation,
                    "",
                    decision={
                        "run_id": save["run_id"],
                        "approval_id": approval["approvalId"],
                        "decision": decision,
                    },
                )
                after = await self.api(
                    "GET", f"/v1/cases/{case}" + ("/plan" if kind == "plan" else "")
                )
                self.check(
                    scenario + " persisted outcome",
                    bool(after and len(after["items"]) == 2)
                    if kind == "plan"
                    else len(after["events"]) == (1 if decision == "approve" else 0),
                )
                self.check(
                    scenario + " resume completed",
                    (resumed.get("status") or {}).get("status") == "completed",
                )
                if kind == "event" and decision == "approve":
                    replay = await self.stream(
                        scenario + "-duplicate-client-id",
                        conversation,
                        save["user_message"],
                        client_id=save["client_message_id"],
                    )
                    self.check(
                        scenario + " duplicate no provider call",
                        replay["ledger_before"]["calls"] == replay["ledger_after"]["calls"],
                    )
                    again = await self.api("GET", f"/v1/cases/{case}")
                    self.check(scenario + " exactly one write", len(again["events"]) == 1)
            except Exception as error:
                self.check(
                    scenario + " execution",
                    False,
                    {"error_type": type(error).__name__, "detail": str(error)},
                )

    async def memory(self):
        conversation = await self.conversation("Synthetic B-memory")
        before = await self.api("GET", "/v1/memories")
        await self.stream(
            "B02-memory-proposal",
            conversation,
            "Mình thích bạn trả lời bằng hai câu ngắn, mỗi lần chỉ một câu hỏi. Bạn có thể ghi nhớ sở thích trò chuyện này cho những lần sau không? Mình muốn xem và duyệt trước khi lưu.",
        )
        candidates = await self.api("GET", "/v1/memory-candidates")
        pending = [c for c in candidates["items"] if c["status"] == "pending"]
        self.check("B02 memory candidate selected by real model", bool(pending))
        self.check(
            "B02 no memory write before decision",
            len((await self.api("GET", "/v1/memories"))["items"]) == len(before["items"]),
        )
        if pending:
            selected = next(
                (c for c in pending if c.get("sourceConversationId") == conversation), pending[0]
            )
            memory = await self.api(
                "POST", f"/v1/memory-candidates/{selected['id']}/decision", {"decision": "approve"}
            )
        else:
            # This is an explicit user-created memory path, not a fixture or a
            # claim that the model proposed it. Retain the failed criterion above.
            memory = await self.api(
                "POST",
                "/v1/memories",
                {
                    "category": "preference",
                    "content": "Mình thích câu trả lời ngắn, hai câu và chỉ một câu hỏi mỗi lần.",
                },
            )
        self.resource("memories", memory["id"])
        await self.api(
            "PATCH",
            f"/v1/memories/{memory['id']}",
            {"content": "Forbidden synthetic update"},
            user=1,
            expected=404,
        )
        self.check("B02 memory ownership isolation", True)
        next_conversation = await self.conversation("Synthetic B-memory-later")
        result = await self.stream(
            "B03-memory-later-conversation",
            next_conversation,
            "Mình đang rối vì chuyện các bạn giấu cặp. Bạn giúp mình bắt đầu thật chậm, theo cách nói chuyện mình đã chọn nhé.",
        )
        self.check("B03 later conversation completed", bool(result.get("response")))
        restored = await self.api("GET", "/v1/memories")
        self.check("B03 memory persisted", any(m["id"] == memory["id"] for m in restored["items"]))
        self.records.append(
            {
                "scenario_id": "B03-persistence-observations",
                "memory": memory,
                "restored": restored,
                "candidate_count": len(pending),
                "conversation_id": next_conversation,
            }
        )
        self.save()

    async def roleplay(self):
        protocols = [
            (
                "E01-teacher",
                "teacher",
                "teacher-group-chat",
                [
                    "Thưa cô, em muốn xin nói riêng một chuyện về nhóm chat của lớp.",
                    "Có một bạn gửi ảnh chế giọng nói của em ba lần trong tuần này. Em buồn và không muốn vào nhóm nữa.",
                    "Em mong cô giúp dừng việc đó mà không bắt em đối chất trước cả lớp. Cô có thể hẹn em nói riêng sau giờ học không?",
                ],
            ),
            (
                "E02-parent",
                "parent",
                "parent-first-talk",
                [
                    "Mẹ ơi, con có chuyện trên mạng muốn kể. Con lo mẹ sẽ thu điện thoại trước khi nghe hết.",
                    "Có bạn đăng ảnh chế con trong nhóm lớp. Con muốn mẹ nghe con và cùng con chọn một bước nhỏ, chưa nhắn cho phụ huynh bạn ấy ngay.",
                    "Con muốn lưu ảnh chụp trước, rồi ngày mai cùng mẹ nói chuyện riêng với cô chủ nhiệm.",
                ],
            ),
            (
                "E03-witness",
                "trusted_adult",
                "trusted-adult-accompany",
                [
                    "Cháu thấy một bạn bị giấu cặp nhiều lần. Cháu là người chứng kiến và muốn nhờ cô đi cùng khi nói với giáo viên.",
                    "Cháu chỉ kể điều cháu trực tiếp nhìn thấy, không chắc ai bắt đầu. Cháu sợ nhóm bạn sẽ gây khó dễ nếu biết cháu kể.",
                    "Cô có thể cùng cháu hẹn nói chuyện riêng, hỏi cách giữ kín danh tính và thống nhất lúc theo dõi lại không?",
                ],
            ),
        ]
        for id, role, scenario, turns in protocols:
            try:
                session = await self.api(
                    "POST",
                    "/v1/roleplay/sessions",
                    {
                        "id": str(uuid4()),
                        "role": role,
                        "scenarioKey": scenario,
                        "userGoal": "Kể rõ điều trực tiếp biết và xin hỗ trợ cụ thể, không hứa kết quả.",
                        "difficulty": 2,
                        "useCaseContext": False,
                    },
                )
                self.resource("roleplay_sessions", session["id"])
                self.resource("conversations", session["conversationId"])
                for index, prompt in enumerate(turns, 1):
                    record = await self.stream(f"{id}-{index}", session["conversationId"], prompt)
                    record["prompt_version"] = "roleplay_partner_v2"
                    self.check(
                        f"{id}-{index} no domain tools",
                        not any(e["event"] == "tool.started" for e in record["events"]),
                    )
                    self.check(
                        f"{id}-{index} completed",
                        (record.get("status") or {}).get("status") == "completed",
                    )
                restored = await self.api("GET", f"/v1/roleplay/sessions/{session['id']}")
                self.check(id + " restore turn count", restored["turnCount"] == len(turns))
                before = ledger_snapshot()
                completed = await self.api(
                    "POST", f"/v1/roleplay/sessions/{session['id']}/complete"
                )
                self.records.append(
                    {
                        "scenario_id": id + "-coach",
                        "prompt_version": "roleplay_coach_v1",
                        "model": "gpt-6-luna",
                        "source_commit": self.head,
                        "user_messages": turns,
                        "feedback": completed.get("feedback"),
                        "ledger_before": before,
                        "ledger_after": ledger_snapshot(),
                        "persisted_session": completed,
                    }
                )
                self.check(
                    id + " coaching persisted",
                    completed["status"] == "completed" and bool(completed.get("feedback")),
                )
                await self.api(
                    "GET", f"/v1/roleplay/sessions/{session['id']}", user=1, expected=404
                )
                self.check(id + " ownership isolation", True)
            except Exception as error:
                self.check(
                    id + " execution",
                    False,
                    {"error_type": type(error).__name__, "detail": str(error)},
                )

    async def auth_security(self):
        auth_base = self.values["SUPABASE_URL"] + "/auth/v1"
        for index, user in enumerate(self.manifest["users"]):
            profile = await self.api("GET", "/v1/me", user=index)
            self.check(
                f"Auth {user['slot']} profile identity",
                profile["id"] == user["id"] if "id" in profile else profile["userId"] == user["id"],
            )
        unsigned = await self.http.get(
            "/v1/me", headers={"Authorization": "Bearer synthetic.invalid.token"}
        )
        anonymous = await self.http.get("/v1/me")
        self.check("Invalid JWT rejected", unsigned.status_code == 401)
        self.check("Unauthenticated profile rejected", anonymous.status_code == 401)
        user = self.manifest["users"][0]
        signed = await self.upstream.post(
            auth_base + "/token?grant_type=password",
            headers=headers(self.values),
            json={"email": user["email"], "password": user["password"]},
        )
        data = signed.json()
        refreshed = await self.upstream.post(
            auth_base + "/token?grant_type=refresh_token",
            headers=headers(self.values),
            json={"refresh_token": data["refresh_token"]},
        )
        self.check(
            "Real hosted refresh token",
            refreshed.status_code == 200
            and refreshed.json().get("user", {}).get("id") == user["id"],
        )
        session_headers = {
            **headers(self.values),
            "Authorization": "Bearer " + refreshed.json()["access_token"],
        }
        logout = await self.upstream.post(
            auth_base + "/logout?scope=local", headers=session_headers
        )
        self.check("Real hosted logout", logout.status_code in {200, 204})
        rejected = await self.upstream.post(
            auth_base + "/token?grant_type=refresh_token",
            headers=headers(self.values),
            json={"refresh_token": refreshed.json()["refresh_token"]},
        )
        self.check("Logged-out refresh token rejected", rejected.status_code >= 400)
        relogin = await self.upstream.post(
            auth_base + "/token?grant_type=password",
            headers=headers(self.values),
            json={"email": user["email"], "password": user["password"]},
        )
        self.check("Real hosted relogin", relogin.status_code == 200)
        self.tokens[0] = relogin.json()["access_token"]
        update = await self.upstream.put(
            auth_base + "/user",
            headers={**headers(self.values), "Authorization": "Bearer " + self.tokens[0]},
            json={"data": {"role": "admin", "is_admin": True}},
        )
        self.check("User-editable metadata exercised", update.status_code == 200)
        metadata_login = await self.upstream.post(
            auth_base + "/token?grant_type=password",
            headers=headers(self.values),
            json={"email": user["email"], "password": user["password"]},
        )
        if metadata_login.status_code != 200:
            raise RuntimeError("Synthetic metadata JWT refresh failed")
        self.tokens[0] = metadata_login.json()["access_token"]
        foreign = await self.http.get(
            f"/v1/school/{uuid4()}/shares", headers={"Authorization": "Bearer " + self.tokens[0]}
        )
        self.check(
            "Metadata cannot enable school administration", foreign.status_code in {403, 404}
        )
        corpus = await self.api("GET", "/v1/knowledge/corpus")
        search = await self.api(
            "GET", "/v1/knowledge/search?q=luu%20bang%20chung%20truoc%20khi%20chan&limit=3"
        )
        self.records.append(
            {"scenario_id": "KB-functional", "published_corpus": corpus, "search": search}
        )
        self.check(
            "Real Knowledge Hub published corpus",
            corpus.get("version") == "kb-20261109-07"
            or corpus.get("corpusVersion") == "kb-20261109-07",
        )
        self.check(
            "Real Knowledge Hub search",
            bool(search.get("results") or search.get("items") or search.get("chunks")),
        )

    async def evidence(self):
        import hashlib

        from safevoice_agent.evidence.orchestrator import CONSENT_VERSION

        image = (OUTPUT / "synthetic-chat.png").read_bytes()
        case = await self.case("Synthetic D screenshot")
        evidence = str(uuid4())
        upload = await self.api(
            "POST",
            "/v1/evidence/uploads",
            {
                "id": evidence,
                "caseId": case,
                "filename": "synthetic-chat.png",
                "mimeType": "image/png",
                "byteSize": len(image),
                "sha256": hashlib.sha256(image).hexdigest(),
                "shownTimestamp": "09/11/2026 10:00 (synthetic)",
            },
        )
        info = upload["upload"]
        key = info["objectName"]
        record_storage_key(USERS, key)
        uploaded = await self.upstream.put(
            self.values["SUPABASE_URL"] + "/storage/v1/object/upload/sign/incident-evidence/" + key,
            params={"token": info["token"]},
            content=image,
            headers={"Content-Type": "image/png"},
        )
        self.check("D01 private signed upload", uploaded.status_code in {200, 201})
        await self.api("POST", f"/v1/evidence/{evidence}/complete")
        self.resource("evidence", evidence)
        await self.api("GET", f"/v1/evidence/{evidence}", user=1, expected=404)
        self.check("D01 evidence user isolation", True)
        public = await self.upstream.get(
            self.values["SUPABASE_URL"] + "/storage/v1/object/public/incident-evidence/" + key
        )
        self.check("D01 public storage denied", public.status_code in {400, 401, 403, 404})
        blocked = await self.http.post(
            "/v1/analyses",
            headers={"Authorization": "Bearer " + self.tokens[0]},
            json={
                "id": str(uuid4()),
                "evidenceId": evidence,
                "consent": {"accepted": False, "version": CONSENT_VERSION},
            },
        )
        self.check("D02 analysis requires consent", blocked.status_code in {400, 422})
        analysis = str(uuid4())
        body = {
            "id": analysis,
            "evidenceId": evidence,
            "consent": {"accepted": True, "version": CONSENT_VERSION},
        }
        before = ledger_snapshot()
        result = await self.api("POST", "/v1/analyses", body)
        self.records.append(
            {
                "scenario_id": "D03-real-image-analysis",
                "model": "gpt-6-luna",
                "prompt_version": "evidence_reader_v1",
                "source_commit": self.head,
                "image_sha256": hashlib.sha256(image).hexdigest(),
                "consent": body["consent"],
                "case_id": case,
                "evidence_id": evidence,
                "analysis": result,
                "ledger_before": before,
                "ledger_after": ledger_snapshot(),
            }
        )
        self.check(
            "D03 image analysis succeeded",
            result["status"] == "succeeded" and bool(result.get("reading")),
        )
        replay_before = ledger_snapshot()
        replay = await self.api("POST", "/v1/analyses", body)
        self.check(
            "D04 analysis idempotency",
            replay["id"] == analysis
            and replay["derivativeId"] == result["derivativeId"]
            and replay_before["calls"] == ledger_snapshot()["calls"],
        )
        correction = "Correction by synthetic owner: A and B are fictional labels. The message was yesterday, not today."
        await self.api(
            "PATCH",
            f"/v1/evidence/{evidence}",
            {"userEditedText": correction, "reviewStatus": "corrected"},
        )
        restored = await self.api("GET", f"/v1/evidence/{evidence}")
        self.check(
            "D05 correction persists on correct incident",
            restored.get("userEditedText") == correction and restored.get("caseId") == case,
        )
        conversation = await self.conversation("Synthetic D consent tool", case_id=case)
        waiting = await self.stream(
            "D06-chat-analysis-request",
            conversation,
            "Mình đính kèm một ảnh chụp tin nhắn tổng hợp để thử. Bạn giúp đọc những gì thấy được trong ảnh, phân biệt với suy đoán, và cho mình xem yêu cầu đồng ý trước khi gửi ảnh cho AI nhé.",
            attachments=[evidence],
        )
        if not waiting["approvals"] and waiting.get("response"):
            waiting = await self.stream(
                "D06-chat-explicit-consent",
                conversation,
                "Mình đồng ý cho AI đọc ảnh tổng hợp đã đính kèm. Hãy mở hộp thoại để mình xác nhận việc gửi ảnh cho AI nhé.",
            )
        self.check("D06 Companion requests image consent", bool(waiting["approvals"]))
        if waiting["approvals"]:
            approval = waiting["approvals"][0]
            await self.stream(
                "D06-chat-analysis-approved",
                conversation,
                "",
                decision={
                    "run_id": waiting["run_id"],
                    "approval_id": approval["approvalId"],
                    "decision": "approve",
                },
            )
        self.save()

    async def persistence_snapshot(self):
        import hashlib

        manifest = read_manifest(USERS)
        resources = {
            kind: [
                id
                for id in ids
                if manifest.get("resource_owners", {}).get(kind, {}).get(id, self.default_owner_id)
                == self.owner_id
            ]
            for kind, ids in manifest.get("resources", {}).items()
        }
        endpoints = ["/v1/memories"]
        for kind, template in [
            ("conversations", "/v1/conversations/{id}/messages"),
            ("cases", "/v1/cases/{id}"),
            ("evidence", "/v1/evidence/{id}"),
            ("roleplay_sessions", "/v1/roleplay/sessions/{id}"),
        ]:
            endpoints.extend(template.format(id=id) for id in resources.get(kind, []))
        observed = []
        for endpoint in endpoints:
            payload = await self.api("GET", endpoint)
            observed.append(
                {
                    "endpoint": endpoint,
                    "sha256": hashlib.sha256(
                        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "item_count": len(payload["items"]) if "items" in payload else None,
                }
            )
        return observed

    async def snapshot(self):
        self.records = await self.persistence_snapshot()
        self.check("Authenticated persistence baseline captured", bool(self.records))

    async def restore(self):
        baseline = json.loads(
            (OUTPUT / f"snapshot-before-restart-{self.actor.lower()}.json").read_text(
                encoding="utf-8"
            )
        )
        if baseline.get("group") != "snapshot" or baseline.get("owner_id") != self.owner_id:
            raise ValueError("A genuine pre-restart snapshot for this synthetic owner is required")
        self.records = await self.persistence_snapshot()
        expected = {row["endpoint"]: row["sha256"] for row in baseline["records"]}
        self.check(
            "Restart restores the same tracked resources",
            set(expected) == {r["endpoint"] for r in self.records},
        )
        for row in self.records:
            self.check(
                "Restart preserves exact persisted payload " + row["endpoint"],
                row["sha256"] == expected.get(row["endpoint"]),
            )


async def execute(group, label, actor="A"):
    if group == "setup":
        async with httpx.AsyncClient(transport=ProjectTransport(), timeout=30) as client:
            await prepare(load_values(), USERS, client)
        print(
            "Prepared two exact synthetic hosted users; private credentials kept only in the local manifest."
        )
        return 0
    if group == "cleanup":
        await run_checks(load_values(), USERS, cleanup=True)
        return 0
    if (OUTPUT / f"{group}-{label}.json").exists():
        raise ValueError("Preserve previous evidence: select a new --label for an authorized rerun")
    harness = Harness(group, label, actor)
    try:
        await harness.start()
        if group in {"core", "context", "safety"}:
            await harness.basic(group)
        elif group == "approval":
            await harness.approval()
        elif group == "memory":
            await harness.memory()
        elif group == "roleplay":
            await harness.roleplay()
        elif group == "auth-security":
            await harness.auth_security()
        elif group == "evidence":
            await harness.evidence()
        elif group == "restore":
            await harness.restore()
        elif group == "snapshot":
            await harness.snapshot()
        else:
            raise ValueError("Unknown live acceptance group")
        harness.save()
        return int(any(not c["passed"] for c in harness.checks))
    except Exception as error:
        harness.check(
            group + " execution",
            False,
            {
                "error_type": type(error).__name__,
                "detail": str(error) if isinstance(error, RuntimeError) else None,
            },
        )
        return 1
    finally:
        await harness.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        required=True,
        choices=[
            "setup",
            "core",
            "context",
            "safety",
            "approval",
            "memory",
            "roleplay",
            "auth-security",
            "evidence",
            "restore",
            "snapshot",
            "cleanup",
        ],
    )
    parser.add_argument("--label", default="initial")
    parser.add_argument("--actor", choices=["A", "B"], default="A")
    args = parser.parse_args()
    try:
        return asyncio.run(execute(args.group, args.label, args.actor))
    except Exception as error:
        print(
            f"Live acceptance failed ({type(error).__name__}); preserve the exact local manifest."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
