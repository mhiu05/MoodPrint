"""Shared effective capability policy; stored opt-ins remain the rollback snapshot.

Journal consent is deliberately a separate gate: a capability token never authorizes a
journal read on its own. No preference or account data is written by this resolver.
"""

from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy import select

from app.ai.collaboration.eligibility import collaboration_eligible
from app.ai.collaboration.models import LEGACY_EDGES, V3_EDGES, AiSharingPermission
from app.ai.proactive.models import AiProactiveSettings
from app.infrastructure.database.models import Consent
from app.modules.consent.policy import consent_enabled

PermissionPolicy = Literal["sharing-v1", "collaboration-defaults-v1"]
DEFAULTS_POLICY: PermissionPolicy = "collaboration-defaults-v1"
LEGACY_POLICY: PermissionPolicy = "sharing-v1"


@dataclass(frozen=True)
class GrantToken:
    policy: PermissionPolicy
    version: int


@dataclass(frozen=True)
class EffectiveGrants:
    edges: dict[str, GrantToken]
    eligible: bool
    feature_open: bool
    journal_context: bool
    policy_mode: PermissionPolicy
    policy_epoch: int


async def effective_grants(db, settings, user, *, family: Literal["legacy", "v3"]) -> EffectiveGrants:
    if family not in ("legacy", "v3"):
        raise ValueError("Unknown collaboration family")
    names = V3_EDGES if family == "v3" else LEGACY_EDGES
    feature = settings.orchestration_open_for(user.id) if family == "v3" else settings.collaboration_open_for(user.id)
    feature = feature and settings.ai_multi_message_enabled
    eligible = await collaboration_eligible(db, user)
    prefs = await db.get(AiProactiveSettings, user.id)
    defaults = settings.ai_collaboration_defaults_enabled
    mode = DEFAULTS_POLICY if defaults else LEGACY_POLICY
    epoch = settings.ai_collaboration_policy_epoch if defaults else 0
    edges: dict[str, GrantToken] = {}
    if defaults:
        # The overlay grants no temporary/persistent access that existing runtime gates deny.
        consent = await db.get(Consent, (user.id, "AI"))
        eligible = eligible and bool(consent and consent_enabled("AI", consent.enabled))
        feature = feature and settings.ai_available_for(user.id) and settings.chat_history_enabled
        if feature and eligible:
            edges = {edge: GrantToken(mode, epoch) for edge in names}
    elif feature and eligible:
        rows = (await db.scalars(select(AiSharingPermission).where(
            AiSharingPermission.user_id == user.id,
            AiSharingPermission.edge.in_(names), AiSharingPermission.enabled.is_(True),
        ))).all()
        edges = {row.edge: GrantToken(cast(PermissionPolicy, row.policy_version), row.version) for row in rows}
    return EffectiveGrants(edges, eligible, feature, bool(prefs and prefs.journal_context_enabled), mode, epoch)
