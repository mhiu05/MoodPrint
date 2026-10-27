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
        self.tokens: dict[str, str] = {}

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/token":
            body = json.loads(request.content)
            actors = {f"local-mvp-{number}@example.invalid": number for number in (45, 46)}
            number = actors.get(body.get("email"))
            if not number or body.get("password") != "local-mvp-synthetic":
                return httpx.Response(400, json={"error_code": "invalid_credentials"})
            uid = UUID(f"00000000-0000-4000-8000-{number:012d}")
            sid = uuid4()
            async with self.database.engine.begin() as db:
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
                            "is_anonymous": False,
                        }
                    ),
                    "synthetic-only",
                )
            )
            self.tokens[token] = str(uid)
            return httpx.Response(200, json={"access_token": token})
        if request.url.path == "/auth/v1/user":
            uid = self.tokens.get(request.headers.get("Authorization", "").removeprefix("Bearer "))
            if not uid:
                return httpx.Response(401)
            return httpx.Response(200, json={"id": uid, "is_anonymous": False})
        return httpx.Response(404)
