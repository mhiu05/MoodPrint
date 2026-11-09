"""IDF-weighted lexical coverage for the keyword branch.

Why not ``ts_rank``: it is an absolute score, so one shared common word (a Vietnamese function word
or a word every card repeats) cleared the gate and let off-topic queries through. Coverage asks
instead: of the information-bearing query terms, weighted by how rare each is in the published
corpus, how much does this chunk contain? A shared common word then weighs almost nothing.

Diacritics are respected when the user typed them: an accented query token must match the same
accented word ("bắt" does not match "bật"), while an unaccented token matches by folded form, so a
query typed without diacritics still finds accented cards. Folding everything made "bắt cá ở ao"
look 82 percent covered by an unrelated card.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from moodprint_agent.knowledge.textnorm import clean_text, fold_vietnamese

# Letters and digits only: an underscore is a separator, never part of a term.
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

# Folded Vietnamese function and question words. Deliberately short: IDF handles the rest, and a
# long list would delete real words that fold onto the same letters (co = cô / có / cớ).
STOP_TERMS: frozenset[str] = frozenset(
    (
        "la va cua khong thi toi minh ban gi nhu the nao bi cho duoc khi mot cac nhung de o "
        "trong voi cach lam sao nen can phai ve den tu em rat qua cung roi dang se da vua van "
        "hay hoac neu nay do kia day ay ma vi tai lai ra vao len"
    ).split()
)


def _exact_tokens(text: str) -> list[str]:
    return _TOKEN.findall(clean_text(text).lower())


def _has_marks(token: str) -> bool:
    return fold_vietnamese(token) != token


@dataclass(frozen=True, slots=True)
class QueryTerm:
    folded: str
    exact: str
    accented: bool


def query_terms(text: str, *, limit: int = 16) -> list[QueryTerm]:
    """Distinct information-bearing terms, in query order."""
    seen: dict[str, QueryTerm] = {}
    for exact in _exact_tokens(text):
        folded = fold_vietnamese(exact)
        if len(folded) < 2 or folded in STOP_TERMS or folded in seen:
            continue
        seen[folded] = QueryTerm(folded=folded, exact=exact, accented=_has_marks(exact))
        if len(seen) == limit:
            break
    return list(seen.values())


def content_bigrams(text: str) -> list[str]:
    """Adjacent pairs of information-bearing folded terms: Vietnamese words are often two syllables."""
    tokens = [fold_vietnamese(token) for token in _exact_tokens(text)]
    pairs: list[str] = []
    for left, right in zip(tokens, tokens[1:], strict=False):
        if len(left) < 2 or len(right) < 2 or left in STOP_TERMS or right in STOP_TERMS:
            continue
        pairs.append(f"{left} {right}")
    return pairs


@dataclass(frozen=True, slots=True)
class ChunkTerms:
    folded: frozenset[str]
    exact: frozenset[str]
    phrases: frozenset[str]


def chunk_terms(text: str) -> ChunkTerms:
    exact = _exact_tokens(text)
    folded = [fold_vietnamese(token) for token in exact]
    return ChunkTerms(
        folded=frozenset(folded),
        exact=frozenset(exact),
        phrases=frozenset(f"{a} {b}" for a, b in zip(folded, folded[1:], strict=False)),
    )


@dataclass(frozen=True, slots=True)
class TermStats:
    """Chunk-level document frequencies for one corpus version, folded and accented."""

    n: int
    df_folded: dict[str, int] = field(default_factory=dict[str, int])
    df_exact: dict[str, int] = field(default_factory=dict[str, int])

    @classmethod
    def from_texts(cls, texts: Iterable[str]) -> TermStats:
        folded: dict[str, int] = {}
        exact: dict[str, int] = {}
        total = 0
        for value in texts:
            total += 1
            chunk = chunk_terms(value)
            for token in chunk.folded:
                folded[token] = folded.get(token, 0) + 1
            for token in chunk.exact:
                exact[token] = exact.get(token, 0) + 1
        return cls(n=total, df_folded=folded, df_exact=exact)

    def idf(self, term: QueryTerm | str) -> float:
        if isinstance(term, str):
            df = self.df_folded.get(term, 0)
        elif term.accented:
            df = self.df_exact.get(term.exact, 0)
        else:
            df = self.df_folded.get(term.folded, 0)
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))


def _present(term: QueryTerm, chunk: ChunkTerms) -> bool:
    return term.exact in chunk.exact if term.accented else term.folded in chunk.folded


def coverage_score(
    query: Sequence[QueryTerm],
    chunk: ChunkTerms,
    stats: TermStats,
    *,
    bigrams: Sequence[str],
    phrase_bonus: float = 0.0,
) -> float:
    """0..1: share of the query's IDF mass present in the chunk, plus a small phrase bonus."""
    if not query:
        return 0.0
    total = sum(stats.idf(term) for term in query)
    if total <= 0:
        return 0.0
    covered = sum(stats.idf(term) for term in query if _present(term, chunk))
    score = covered / total
    if phrase_bonus > 0 and bigrams:
        matched = sum(1 for pair in bigrams if pair in chunk.phrases)
        score += phrase_bonus * matched / len(bigrams)
    return min(1.0, score)


def folded_terms(text: str, *, limit: int = 16) -> list[str]:
    """Folded form of ``query_terms`` for the tsquery.

    Only ASCII terms are kept: every indexed lexeme is accent-folded ASCII, so a token that is
    still non-ASCII after folding cannot match and has no business inside a tsquery.
    """
    return [term.folded for term in query_terms(text, limit=limit) if term.folded.isascii()]


__all__ = [
    "STOP_TERMS",
    "ChunkTerms",
    "QueryTerm",
    "TermStats",
    "chunk_terms",
    "content_bigrams",
    "coverage_score",
    "folded_terms",
    "query_terms",
]
