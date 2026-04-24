# REVIEW_MLB_002

Decision: **APPROVED**

---

## 1. Confirmed fix: HOU@OAK

PASS. Worker added alias normalization (`OAK→ATH`) inside `recommendation_api.py` before ESPN registry matching. Verification run confirmed:
- `event=mlb-hou-oak-2026-04-04` now surfaces as a healthy candidate mapped to `HOU vs ATH`
- Previously dropped as `no_registry_match` — no longer the case
- Acceptance criterion met

## 2. Not yet fully verified live: TOR@CWS

NOT FAILED — observation gap only. Worker added alias normalization (`CWS→CHW`) in the same patch. The alias code is present and symmetric with the OAK fix. However, no same-day live `tor-cws-2026-04-04` event was present in the Polymarket/Kalshi discovery set during the verification window. The available tor-cws slug was dated `2026-04-05` and matched a FINAL/non-live registry game, so no healthy candidate line could be observed. This is a timing issue, not a code failure.

**Status:** Alias in place, live confirmation deferred to next session where TOR@CWS is same-day live.

## 3. Duplicate event market regression: none

PASS. Worker confirmed `duplicate_event_market` count remained `0` in the discovery summary. No regression.

---

## Scope check

- Files changed: `recommendation_api.py` only — inside allowed_files. PASS.
- Do-not-touch list respected: models, training pipeline, execution logic, sports_bot_v2 — none touched. PASS.
- Verification command run: `python -m integration.recommendation_api` — confirmed. PASS.
- Rollback still possible: revert `recommendation_api.py` only — confirmed. PASS.
- Model logic unchanged: worker explicitly confirmed. PASS.

---

## Notes

- Alias normalization is local to `recommendation_api.py` by task restriction. If registry matching is ever added elsewhere, the same alias map will need to be applied there too. Worker flagged this as a residual risk — noted, not blocking.
- TOR@CWS live confirmation should be observed passively on the next session day that TOR plays CWS. No additional code change needed for that.

---

## Next action

- Move MLB_002 to DONE on task board
- Unlock `recommendation_api.py`
- Create MLB_003 only if a narrow logging/verification task is warranted (see below)
- Do NOT create another alias code change task — the code fix is complete
