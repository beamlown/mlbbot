"""Persona stat-line derivation for the Dugout OS roster.

The UI never queries `runs` directly for stats; it always goes through
`persona_stats(profile_id)`. Keeps the SQL in one place and lets us
add caching later if the dashboard hits get hot.

Stats:
  G    games — total runs by this persona
  AVG  batting average — succeeded runs / G, formatted ".287" (Baseball-style, no leading 0)
  K    strikeouts — failed runs (status=FAILED or non-zero exit_code)
  BB   walks — cancelled / timed-out runs
  HR   home runs — distinct SHIPPED patches the persona had a succeeded
       run on (joined via runs.task_id → tasks.patch_id → patches.status)
  RBI  runs batted in — distinct tasks this persona had a succeeded run
       on that subsequently reached DONE/APPROVED status
  ERA  earned run average — only meaningful for review-style roles;
       ratio of changes_requested verdicts to total reviews authored
"""
from __future__ import annotations

from typing import TypedDict
from .db import get_conn


class PersonaStats(TypedDict):
    profile_id: str
    G: int
    AVG: str       # ".287" formatted; "—" if G == 0
    K: int
    BB: int
    HR: int
    RBI: int
    ERA: str       # "1.84" formatted; "—" if no reviews
    level: int     # one level per 10 successful runs
    xp_pct: int    # 0..100 progress to next level


def _format_avg(succeeded: int, games: int) -> str:
    if games <= 0:
        return "—"
    avg = succeeded / games
    # Baseball-style: ".287" not "0.287"
    return f"{avg:.3f}".lstrip("0") if avg < 1 else "1.000"


def _format_era(cr: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{cr / total:.2f}"


def persona_stats(profile_id: str) -> PersonaStats:
    """Return the canonical stat line for a persona. Pure read."""
    conn = get_conn()

    prof = conn.execute(
        "SELECT role FROM agent_profiles WHERE profile_id=?", (profile_id,)
    ).fetchone()
    role = prof["role"] if prof else None

    # G, K, BB, succeeded — counted from runs by role.
    # (We track by role rather than by profile_id directly because
    # historical runs predate the profile_id column being recorded on
    # every run — but role is always present.)
    g_row = conn.execute(
        "SELECT COUNT(*) AS n FROM runs WHERE role=?", (role,)
    ).fetchone()
    games = (g_row["n"] if g_row else 0) or 0

    succeeded = conn.execute(
        "SELECT COUNT(*) AS n FROM runs "
        "WHERE role=? AND (status='succeeded' OR exit_code=0)", (role,)
    ).fetchone()["n"] or 0

    failed = conn.execute(
        "SELECT COUNT(*) AS n FROM runs "
        "WHERE role=? AND (status='failed' OR (exit_code IS NOT NULL AND exit_code != 0))",
        (role,),
    ).fetchone()["n"] or 0

    walks = conn.execute(
        "SELECT COUNT(*) AS n FROM runs "
        "WHERE role=? AND status IN ('cancelled','timeout')", (role,)
    ).fetchone()["n"] or 0

    # RBI = distinct tasks where this role had a succeeded run AND the task is now DONE.
    # We derive from runs+tasks rather than task_events because task_events.actor is a
    # lowercase semantic category ("worker", "reviewer") populated by future writes,
    # while runs.role carries the uppercase role string from day one.
    rbi = conn.execute(
        "SELECT COUNT(DISTINCT r.task_id) AS n "
        "FROM runs r JOIN tasks t ON t.task_id = r.task_id "
        "WHERE r.role=? AND (r.status='succeeded' OR r.exit_code=0) "
        "  AND UPPER(t.status) IN ('DONE','APPROVED')",
        (role,),
    ).fetchone()["n"] or 0

    # HR = distinct SHIPPED patches that include any task this role had a succeeded run on.
    hr = conn.execute(
        "SELECT COUNT(DISTINCT p.patch_id) AS n "
        "FROM runs r "
        "JOIN tasks t   ON t.task_id   = r.task_id "
        "JOIN patches p ON p.patch_id  = t.patch_id "
        "WHERE r.role=? AND (r.status='succeeded' OR r.exit_code=0) "
        "  AND p.status='SHIPPED'",
        (role,),
    ).fetchone()["n"] or 0

    # ERA = changes_requested / total reviews authored by this role.
    if role and role.upper() in ("SONNET_MANAGER", "OPUS_AUDITOR",
                                 "OPUS_PATCH_REVIEWER", "SONNET_TRIAGE"):
        rev_total = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE reviewer=?", (role,)
        ).fetchone()["n"] or 0
        rev_cr = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews "
            "WHERE reviewer=? AND UPPER(decision) LIKE 'CHANGES%'", (role,)
        ).fetchone()["n"] or 0
        era = _format_era(rev_cr, rev_total)
    else:
        era = "—"

    level = succeeded // 10
    xp_pct = int((succeeded % 10) * 10)

    return PersonaStats(
        profile_id=profile_id,
        G=games,
        AVG=_format_avg(succeeded, games),
        K=failed,
        BB=walks,
        HR=hr,
        RBI=rbi,
        ERA=era,
        level=level,
        xp_pct=xp_pct,
    )


if __name__ == "__main__":
    # Inline smoke test against the live DB. Prints stats for every
    # active profile and exits 0 on success.
    from .db import get_conn, init_db
    init_db()
    conn = get_conn()
    rows = conn.execute(
        "SELECT profile_id FROM agent_profiles ORDER BY profile_id"
    ).fetchall()
    if not rows:
        raise SystemExit("no agent_profiles seeded yet — run init_db once")
    print(f"{'profile_id':22s}  {'G':>4}  {'AVG':>5}  {'K':>4}  {'BB':>4}  "
          f"{'HR':>4}  {'RBI':>4}  {'ERA':>5}  {'L':>2}  {'XP%':>4}")
    for r in rows:
        s = persona_stats(r["profile_id"])
        print(f"{s['profile_id']:22s}  {s['G']:>4}  {s['AVG']:>5}  "
              f"{s['K']:>4}  {s['BB']:>4}  {s['HR']:>4}  {s['RBI']:>4}  "
              f"{s['ERA']:>5}  {s['level']:>2}  {s['xp_pct']:>4}")
    print("ok")
