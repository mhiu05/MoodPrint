"""Generate the synthetic matching evaluation dataset (deterministic, no real data).

python -m evals.matching.generate   (from backend/)

personas_v2.json: 60 synthetic personas built from seven interest archetypes.
  20 % are v1-shaped (v1 vocabulary, no v2 facets), 30 % have no availability and
  10 % are sparse (minimum selections).
pair_labels.json: 300 persona pairs, each with three labels (0 = no, 1 = maybe,
  2 = yes: "would plausibly enjoy a first conversation") from three *rule-based proxy
  raters* r1..r3 with deliberately different rubrics and 10 % seeded disagreement.
  They are NOT human judgments: the labels are marked provisional and must not be
  used alone to switch the production scorer (docs/productization/05 section 12).
"""

import json
import random
from itertools import combinations
from pathlib import Path

from app.modules.matching import scoring
from app.modules.profiles import taxonomy

HERE = Path(__file__).parent
SEED = 20261025

ARCHETYPES = {
    "language-learner": {
        "interests": ["english", "languages", "reading", "podcasts", "coffee", "travel", "movies"],
        "values": ["curiosity", "growth", "respect", "kindness"],
        "goals": ["language-practice", "study-buddy", "friendship"],
        "activities": ["focus", "coop_quiz", "icebreaker"],
    },
    "active": {
        "interests": ["running", "walking", "cycling", "badminton", "football", "yoga", "travel"],
        "values": ["reliability", "kindness", "growth", "humor"],
        "goals": ["shared-interests", "friendship"],
        "activities": ["chat_only", "icebreaker"],
    },
    "creative": {
        "interests": ["drawing", "photography", "crafts", "writing", "music", "singing", "anime"],
        "values": ["sincerity", "humor", "curiosity", "kindness"],
        "goals": ["shared-interests", "friendship"],
        "activities": ["icebreaker", "chat_only", "focus"],
    },
    "player": {
        "interests": ["games", "anime", "movies", "boardgames", "chess", "puzzles", "music"],
        "values": ["humor", "respect", "reliability"],
        "goals": ["friendship", "shared-interests"],
        "activities": ["coop_quiz", "icebreaker"],
    },
    "mindful": {
        "interests": ["meditation", "yoga", "reading", "plants", "coffee", "writing", "walking"],
        "values": ["calm", "kindness", "sincerity", "respect"],
        "goals": ["friendship", "shared-interests"],
        "activities": ["focus", "chat_only"],
    },
    "foodie": {
        "interests": ["cooking", "coffee", "travel", "photography", "movies", "plants"],
        "values": ["humor", "curiosity", "kindness", "sincerity"],
        "goals": ["friendship", "shared-interests"],
        "activities": ["chat_only", "icebreaker", "coop_quiz"],
    },
    "builder": {
        "interests": ["tech", "science", "games", "chess", "podcasts", "reading", "history"],
        "values": ["curiosity", "growth", "reliability"],
        "goals": ["study-buddy", "shared-interests"],
        "activities": ["focus", "coop_quiz"],
    },
}
V1_GOALS = ["friendship", "shared-interests"]


def persona(index: int, rng: random.Random) -> dict:
    kind = sorted(ARCHETYPES)[index % len(ARCHETYPES)]
    arch = ARCHETYPES[kind]
    shape = "v1" if index % 5 == 0 else "sparse" if index % 10 == 3 else "v2"
    if shape == "v1":
        pool = [tag for tag in arch["interests"] if tag in scoring._INTERESTS]
        pool += rng.sample(sorted(set(scoring._INTERESTS) - set(pool)), 4 - min(len(pool), 3))
        interests = rng.sample(pool, min(len(pool), rng.randint(3, 5)))
        values = rng.sample(sorted(scoring._VALUES), rng.randint(2, 3))
        goal = rng.choice([g for g in arch["goals"] if g in V1_GOALS] or V1_GOALS)
        profile = {
            "interests": interests,
            "values": values,
            "style": rng.choice(sorted(taxonomy.STYLES)),
            "goal": goal,
            "languages": ["vi"] if rng.random() < 0.7 else ["vi", "en"],
        }
    else:
        sparse = shape == "sparse"
        count = 3 if sparse else rng.randint(4, 7)
        noise = rng.sample(sorted(set(taxonomy.INTERESTS) - set(arch["interests"])), 2)
        interests = rng.sample(arch["interests"], min(count, len(arch["interests"]) - 1))
        if not sparse and rng.random() < 0.6:
            interests.append(noise[0])
        values = rng.sample(
            arch["values"], 2 if sparse else rng.randint(2, min(3, len(arch["values"])))
        )
        if not sparse and rng.random() < 0.3:
            extra = rng.choice(sorted(set(taxonomy.VALUES) - set(values)))
            values.append(extra)
        languages = (
            ["vi", "en"]
            if "english" in interests or rng.random() < 0.3
            else (["en"] if rng.random() < 0.05 else ["vi"])
        )
        profile = {
            "interests": interests,
            "values": values,
            "style": rng.choice(sorted(taxonomy.STYLES)),
            "goal": rng.choice(arch["goals"]),
            "languages": languages,
            "activities": []
            if sparse
            else rng.sample(arch["activities"], rng.randint(1, len(arch["activities"]))),
            "availability": []
            if sparse or index % 10 in (1, 4, 7)
            else rng.sample(sorted(taxonomy.AVAILABILITY), rng.randint(1, 3)),
            "strict_goal": not sparse and rng.random() < 0.08,
        }
    return {"id": f"P{index + 1:02d}", "archetype": kind, "shape": shape, "profile": profile}


def _shared(a, b, facet):
    return set(a.get(facet) or []) & set(b.get(facet) or [])


def rater_intent(pa, pb):
    a, b = pa["profile"], pb["profile"]
    same_kind = pa["archetype"] == pb["archetype"]
    goal_ok = taxonomy.goal_compat(a["goal"], b["goal"]) >= 0.7
    if same_kind and goal_ok:
        return 2
    return 1 if same_kind or len(_shared(a, b, "interests")) >= 2 else 0


def rater_interests(pa, pb):
    count = len(_shared(pa["profile"], pb["profile"], "interests"))
    return 2 if count >= 3 else 1 if count >= 1 else 0


def rater_conversation(pa, pb):
    a, b = pa["profile"], pb["profile"]
    if not _shared(a, b, "languages"):
        return 0
    common = _shared(a, b, "interests") | _shared(a, b, "values")
    if _shared(a, b, "activities") and common:
        return 2
    return 1 if common or pa["archetype"] == pb["archetype"] else 0


def main():
    rng = random.Random(SEED)
    personas = [persona(index, rng) for index in range(60)]
    pairs = rng.sample(list(combinations(range(60), 2)), 300)
    labels = []
    for i, j in sorted(pairs):
        pa, pb = personas[i], personas[j]
        ratings = []
        for rater in (rater_intent, rater_interests, rater_conversation):
            value = rater(pa, pb)
            if rng.random() < 0.10:  # seeded disagreement
                value = max(0, min(2, value + rng.choice((-1, 1))))
            ratings.append(value)
        labels.append(
            {"a": pa["id"], "b": pb["id"], "r1": ratings[0], "r2": ratings[1], "r3": ratings[2]}
        )
    meta = {
        "seed": SEED,
        "provisional": True,
        "raters": "r1..r3 are rule-based proxy raters (intent, interests, conversation), not humans",
    }
    (HERE / "personas_v2.json").write_text(
        json.dumps({**meta, "personas": personas}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    (HERE / "pair_labels.json").write_text(
        json.dumps({**meta, "pairs": labels}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"personas={len(personas)} pairs={len(labels)}")


if __name__ == "__main__":
    main()
