"""Seeded hostile and random queries shared by the unit and database security tests."""

from __future__ import annotations

import random
import string

ATTACKS = [
    "'; DROP TABLE knowledge.chunks; --",
    "a & b | !c <-> d :* e",
    '") OR 1=1 --',
    "$$ select pg_sleep(5) $$",
    "'|'||(select version())||'",
    "\x00\x01\x02 control \x7f chars",
    "‮ rtl override ​ zero width",
    "%s %d {0} {{x}} ${jndi:ldap://x}",
    "<script>alert(1)</script>",
    "' UNION SELECT licence_note FROM knowledge.sources --",
]
ALPHABET = (
    string.ascii_letters
    + string.digits
    + " '\"&|!:*<>()-_;\\/%$@.+,#"
    + "ắằẳẵặâấầẩẫậđêếềểễệôốồổỗộơớờởỡợưứừửữự\t\n"
)


def fuzz_corpus() -> list[str]:
    """500 fixed strings: ten attacks plus 490 random ones up to 420 characters."""
    rng = random.Random(20261109)
    cases = list(ATTACKS)
    cases += ["".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 420))) for _ in range(490)]
    return cases
