"""Loopback harness only: synthetic provider, real application login/session logic."""

import base64
import json
import time
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text


class LocalAuth:
    def __init__(self, database):
        self.database = database
        self.tokens: dict[str, tuple[str, bool]] = {}
        self.registrations: dict[str, UUID] = {}

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path in ("/auth/v1/token", "/auth/v1/signup"):
            body = json.loads(request.content)
            if request.url.path.endswith("/signup") and "email" in body:
                if body.get("password") != "local-mvp-synthetic" or not body["email"].endswith("@example.invalid"):
                    return httpx.Response(400, json={"error_code": "invalid_credentials"})
                uid = self.registrations.setdefault(body["email"], uuid4())
                async with self.database.engine.begin() as db:
                    await db.execute(text("insert into auth.users(id,is_anonymous) values (:uid,false) on conflict do nothing"), {"uid": uid})
                return httpx.Response(200, json={"user": {"id": str(uid)}})
            anonymous = request.url.path.endswith("/signup")
            if anonymous:
                if (set(body) != {"data", "gotrue_meta_security"}
                    or set(body["data"]) != {"moodprint_guest_attempt"}
                    or body["gotrue_meta_security"].get("captcha_token") != "synthetic-captcha-token"):
                    return httpx.Response(400, json={"error_code": "captcha_failed"})
                uid = uuid4()
            else:
                actors = {f"local-mvp-{number}@example.invalid": number for number in (45, 46)}
                number = actors.get(body.get("email"))
                registered = self.registrations.get(body.get("email"))
                if (not number and not registered) or body.get("password") != "local-mvp-synthetic":
                    return httpx.Response(400, json={"error_code": "invalid_credentials"})
                uid = registered or UUID(f"00000000-0000-4000-8000-{number:012d}")
            sid = uuid4()
            async with self.database.engine.begin() as db:
                if anonymous:
                    await db.execute(text("insert into auth.users(id,is_anonymous,raw_user_meta_data)"
                        " values (:uid,true,cast(:meta as jsonb))"),
                        {"uid": uid, "meta": json.dumps(body["data"])})
                await db.execute(
                    text("insert into auth.sessions(id,user_id) values (:sid,:uid)"),
                    {"sid": sid, "uid": uid},
                )

            def part(value):
                return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

            token = ".".join(
                (
                    part({"alg": "none"}),
                    part(
                        {
                            "sub": str(uid),
                            "session_id": str(sid),
                            "exp": int(time.time()) + 3600,
                            "iss": "https://local-auth.invalid/auth/v1",
                            "aud": "authenticated",
                            "is_anonymous": anonymous,
                        }
                    ),
                    "synthetic-only",
                )
            )
            self.tokens[token] = (str(uid), anonymous)
            return httpx.Response(200, json={"access_token": token})
        if request.url.path == "/auth/v1/user":
            actor = self.tokens.get(request.headers.get("Authorization", "").removeprefix("Bearer "))
            if not actor:
                return httpx.Response(401)
            return httpx.Response(200, json={"id": actor[0], "is_anonymous": actor[1]})
        return httpx.Response(404)
