from app.ai.schemas import AiOutput, AiReply, Citation
from app.ai.search.schemas import GroundedReply, SearchSource


def render_grounded_reply(draft: GroundedReply, sources: dict[str, SearchSource]) -> AiReply:
    parts = []
    for bubble in draft.messages:
        if any(card.kind in ("maps_search", "places") for card in bubble.cards):
            raise ValueError("model cannot create search cards")
        text, citations = "", []
        for segment in bubble.segments:
            start = len(text)
            text += segment.text
            for identity in dict.fromkeys(segment.source_ids):
                if identity not in sources:
                    raise ValueError("unknown source ID")
                source = sources[identity]
                citations.append(Citation(source_id=identity, title=source.title, url=source.url,
                                          start=start, end=len(text)))
        if len(text) > 1500:
            raise ValueError("grounded bubble too long")
        parts.append(AiOutput(text=text, cards=[*bubble.cards], citations=citations))
    reply = AiReply(parts=parts)
    if sources and any(not p.citations for p in parts):
        raise ValueError("source-backed answer requires citations")
    return reply
