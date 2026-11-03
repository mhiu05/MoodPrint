"""Isolated Responses request: no history, tools, memories or model-written query."""

import asyncio

from pydantic import ValidationError

from app.ai.search.schemas import SearchSource, WebSearchResult


class WebSearchAdapter:
    def __init__(self, create, model: str):
        self.create, self.model = create, model

    async def search(self, query: str, *, timeout_seconds: float) -> WebSearchResult:
        async with asyncio.timeout(min(12, timeout_seconds)):
            raw = await self.create(model=self.model, input=query, store=False,
                tools=[{"type": "web_search", "search_context_size": "low", "external_web_access": True}],
                tool_choice={"type": "web_search"}, max_tool_calls=1, max_output_tokens=1200,
                reasoning={"effort": "low"},
                include=["web_search_call.action.sources"], timeout=min(12, timeout_seconds))
        data = raw if isinstance(raw, dict) else raw.model_dump(mode="json")
        output = data.get("output", [])
        calls = len({item["id"] for item in output if item.get("type") == "web_search_call"})
        if calls > 1 or data.get("status") != "completed":
            raise ValueError("search contract drift")
        texts: list[str] = []
        sources: list[SearchSource] = []
        urls: set[str] = set()
        for item in output:
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") != "output_text":
                    continue
                text = content.get("text", "")
                texts.append(text)
                for annotation in content.get("annotations", []):
                    if annotation.get("type") != "url_citation" or len(sources) >= 8:
                        continue
                    try:
                        source = SearchSource(source_id=f"s{len(sources)+1}",
                            title=annotation.get("title", "Nguồn")[:200], url=annotation["url"],
                            excerpt=text[max(0, annotation.get("start_index", 0)-150):annotation.get("end_index", 0)+150][:600])
                    except (ValidationError, ValueError, KeyError, TypeError):
                        continue
                    if source.url not in urls:
                        sources.append(source)
                        urls.add(source.url)
        usage = data.get("usage") or {}
        return WebSearchResult(status="completed" if sources and calls else "empty",
            text="\n".join(texts)[:6000], sources=sources, calls=calls,
            input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=(usage.get("input_tokens_details") or {}).get("cached_tokens", 0))
