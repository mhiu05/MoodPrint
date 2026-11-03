"""Read-only rollout inventory. Never returns identities, prompts, or private content."""

from sqlalchemy import text


async def sharing_preflight_counts(db) -> dict[str, dict[str, int]]:
    """Count stored preferences for registered accounts, independently of runtime eligibility.

    This inventory is not a grant decision. Eligibility continues to be checked live by the
    shared resolver; an account absent from a rollout cohort is still included in inventory.
    """
    rows = (await db.execute(text("""
        with edges(family, edge) as (values
            ('legacy', 'nhip_energy_for_rure'), ('legacy', 'nhip_habit_for_may'),
            ('legacy', 'rure_activity_for_guong'), ('v3', 'dieuphoi_consult_nhatky'),
            ('v3', 'dieuphoi_consult_hoatdong'), ('v3', 'dieuphoi_handoff_nhatky'),
            ('v3', 'dieuphoi_handoff_hoatdong')
        )
        select e.family,
            count(*) filter (where p.enabled is true) as enabled,
            count(*) filter (where p.enabled is false) as disabled,
            count(*) filter (where p.user_id is null) as missing
        from moodprint.users u cross join edges e
        left join moodprint.ai_sharing_permissions p on p.user_id = u.id and p.edge = e.edge
        where u.account_kind = 'registered'
        group by e.family
    """))).mappings().all()
    counts = {family: {"true": 0, "false": 0, "missing": 0} for family in ("legacy", "v3")}
    for row in rows:
        counts[row["family"]] = {"true": row["enabled"], "false": row["disabled"], "missing": row["missing"]}
    return counts
