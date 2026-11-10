"""Restore diacritics in an unaccented Vietnamese query, using only the published corpus text.

The embedding model handles accent-stripped Vietnamese poorly (cosines drop from ~0.5 to ~0.2), so
a user who types fast without marks gets worse results than one who types them. This module maps
each unaccented token to the accented forms seen in the corpus and picks the likeliest sequence
with a Viterbi pass over unigram and bigram counts. It never invents a word: unknown tokens,
English text and text that already has marks pass through unchanged.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from moodprint_agent.knowledge.textnorm import clean_text, fold_vietnamese

_TOKEN = re.compile(r"\w+", re.UNICODE)
_MIN_KNOWN_SHARE = 0.5  # fewer known tokens than this and the text is probably not Vietnamese
_LAMBDA = 0.8  # weight of the bigram estimate in the interpolation


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(clean_text(text).lower())


@dataclass(frozen=True, slots=True)
class Restorer:
    unigrams: Counter[str] = field(default_factory=Counter[str])
    bigrams: Counter[tuple[str, str]] = field(default_factory=Counter[tuple[str, str]])
    by_folded: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    total: int = 0

    @classmethod
    def from_texts(cls, texts: Iterable[str]) -> Restorer:
        unigrams: Counter[str] = Counter()
        bigrams: Counter[tuple[str, str]] = Counter()
        forms: dict[str, set[str]] = defaultdict(set)
        for text in texts:
            tokens = _tokens(text)
            unigrams.update(tokens)
            bigrams.update(zip(tokens, tokens[1:], strict=False))
            for token in tokens:
                forms[fold_vietnamese(token)].add(token)
        by_folded = {key: sorted(values) for key, values in forms.items()}
        return cls(unigrams, bigrams, by_folded, sum(unigrams.values()))

    def _logp(self, previous: str | None, word: str) -> float:
        unigram = (self.unigrams[word] + 0.1) / (self.total + 0.1 * (len(self.unigrams) + 1))
        if previous is None or self.unigrams[previous] == 0:
            return math.log(unigram)
        bigram = self.bigrams[(previous, word)] / self.unigrams[previous]
        return math.log(_LAMBDA * bigram + (1.0 - _LAMBDA) * unigram)

    def restore(self, text: str) -> str:
        if not text.strip() or not self.by_folded:
            return text
        tokens = _tokens(text)
        if not tokens or any(fold_vietnamese(token) != token for token in tokens):
            return text  # the user typed diacritics: respect them
        known = sum(1 for token in tokens if token in self.by_folded)
        if known / len(tokens) < _MIN_KNOWN_SHARE:
            return text  # probably not Vietnamese
        candidates = [self.by_folded.get(token, [token]) for token in tokens]
        # Viterbi: best[i][form] = (score, previous form)
        best: list[dict[str, tuple[float, str | None]]] = []
        for index, forms in enumerate(candidates):
            layer: dict[str, tuple[float, str | None]] = {}
            for form in forms:
                if index == 0:
                    layer[form] = (self._logp(None, form), None)
                    continue
                layer[form] = max(
                    (
                        (score + self._logp(prev, form), prev)
                        for prev, (score, _) in best[index - 1].items()
                    ),
                    key=lambda item: item[0],
                )
            best.append(layer)
        form = max(best[-1], key=lambda key: best[-1][key][0])
        path = [form]
        for index in range(len(tokens) - 1, 0, -1):
            previous = best[index][path[-1]][1]
            assert previous is not None
            path.append(previous)
        return " ".join(reversed(path))
