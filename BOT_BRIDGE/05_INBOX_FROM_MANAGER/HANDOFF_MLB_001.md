# HANDOFF — MLB_001
## Diagnose live market discovery mismatch

---

## Context

Same-day MLB event slugs are being excluded before candidate generation, but the exact reason isn't being logged. This makes it impossible to diagnose whether it's a date filter, abbreviation mismatch, or registry gap.

---

## File to change

`sports_bot_v2/mlb_model/integration/recommendation_api.py` — ONLY this file.

---

## Change

In the market discovery / filtering function (wherever same-day MLB events are evaluated for inclusion as candidates), add explicit logging for each exclusion reason. For each event that is skipped, log: the slug, the rejection reason (e.g. `date_mismatch`, `no_registry_match`, `already_open`, `stale`), and the relevant values being compared.

Example log format:
```
DISCOVERY EXCLUDE slug=mlb-atl-ari-2026-04-04 reason=date_mismatch event_date=2026-04-03 today=2026-04-04
DISCOVERY EXCLUDE slug=mlb-cws-tor-2026-04-04 reason=no_registry_match abbr=CWS
```

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python -m integration.recommendation_api
```

Logs should show explicit DISCOVERY EXCLUDE lines with reasons for each skipped slug.

## Rollback

Revert `mlb_model/integration/recommendation_api.py` only.
