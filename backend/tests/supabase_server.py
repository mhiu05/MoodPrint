"""Hosted Auth/DB test entrypoint: no schema resets, no Auth fixtures, no live AI."""

import asyncio
import json
from pathlib import Path

import uvicorn
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.main import create_app
from tests.fakes import ScriptedModel, message_output, tool_output

settings = Settings(_env_file=Path(__file__).resolve().parents[1] / ".env")
target = make_url(settings.database_url.get_secret_value())
if settings.supabase_url != "https://roznanxbiyqybjpvtilq.supabase.co" or target.username != "moodprint_backend.roznanxbiyqybjpvtilq":
    raise RuntimeError("Hosted E2E requires the reviewed project and dedicated runtime identity")
settings.frontend_origin = "http://127.0.0.1:5176"
settings.ai_enabled = settings.stt_enabled = False
settings.openai_api_key = SecretStr("")
settings.openai_model = ""
app = create_app(settings)
SCOPED_REPORT = Path(__file__).resolve().parents[2] / "docs/plans/validation-artifacts/supabase-scoped-tool-proof.json"


class HostedFixtureModel(ScriptedModel):
    async def stream_response(self, *args, **kwargs):
        context = args[1]
        has_tool_result = isinstance(context, list) and any(
            isinstance(item, dict) and item.get("type") == "function_call_output" for item in context
        )
        serialized = json.dumps(context)
        names = [tool.name for tool in args[3]]
        if "SYNTHETIC_MOOD_RANGE" in serialized:
            report = json.loads(await asyncio.to_thread(SCOPED_REPORT.read_text)) if await asyncio.to_thread(SCOPED_REPORT.exists) else {}
            assert "Supabase mood" not in serialized
            if not has_tool_result and "read_mood_summary" not in names:
                report["unselectedToolNotExposed"] = True
                outputs = [message_output(json.dumps({"text": "Chưa có khoảng thống kê được chia sẻ.", "cards": []}, ensure_ascii=False))]
            elif not has_tool_result:
                call = tool_output("read_mood_summary", "hosted_mood_range")
                outputs = [call]
            else:
                result = next(item["output"] for item in reversed(context) if isinstance(item, dict) and item.get("type") == "function_call_output")
                summary = json.loads(result)
                assert set(summary) == {"from", "to", "count", "mean", "insightAvailable", "sourceVersions", "buckets"}
                assert all(set(bucket) == {"localDate", "value"} for bucket in summary["buckets"])
                report.update(selectedRangeToolInvoked=True, notesExcluded=True, recordedDays=summary["count"], fromDate=summary["from"], toDate=summary["to"])
                outputs = [message_output(json.dumps({"text": "Đã xem thống kê bạn chọn, không có ghi chú.", "cards": []}, ensure_ascii=False))]
            report.update(projectId="roznanxbiyqybjpvtilq", model="SDK fake", liveModelCalls=0)
            await asyncio.to_thread(SCOPED_REPORT.write_text, json.dumps(report, indent=2) + "\n", encoding="utf-8")
        elif "SYNTHETIC_MEMORY_PROPOSAL" in serialized and not has_tool_result:
            call = tool_output("propose_memory", "hosted_memory")
            call.arguments = json.dumps({"text": "Một ghi nhớ tổng hợp để chủ nhân duyệt"})
            outputs = [call]
        else:
            outputs = [message_output(json.dumps({"text": "Mình đã nhận được chia sẻ của bạn.", "cards": []}, ensure_ascii=False))]
        self.responses = [outputs]
        async for event in super().stream_response(*args, **kwargs):
            yield event


app.state.ai.model_override = HostedFixtureModel([])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8003, loop="app.core.loop:selector_factory", log_config=None)
