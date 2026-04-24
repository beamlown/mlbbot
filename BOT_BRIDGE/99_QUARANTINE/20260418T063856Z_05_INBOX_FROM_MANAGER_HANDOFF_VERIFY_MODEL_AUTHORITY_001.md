# HANDOFF - VERIFY_MODEL_AUTHORITY_001
## Verify local MLB origination is disabled in production mode

Restated gate logic:
- `bot_core.py` defines:
  - `ALLOW_LOCAL_MLB_ORIGINATION = os.getenv("ALLOW_LOCAL_MLB_ORIGINATION", "0") == "1"`
- local origination block exits before `generate_signal(...)` unless that flag is enabled

Where the env var could be set from:
- `.env`
- launcher/startup process environment
- parent shell/runtime environment

Production startup path to inspect:
- `launch_all.py`
- current `.env`
- runtime/launcher logs
- current `bot_core.py` gate and remaining bridge branch

Verification goal:
- prove local MLB origination is off by default in normal production startup
- prove bridge/model path is still the only production open-entry path
- identify whether any unintended non-MLB side effect exists
