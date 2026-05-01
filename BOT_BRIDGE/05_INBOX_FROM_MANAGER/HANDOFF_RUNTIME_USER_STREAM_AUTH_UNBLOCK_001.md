# HANDOFF - RUNTIME_USER_STREAM_AUTH_UNBLOCK_001
## Verify presence of server-side Polymarket user-stream auth in active runtime

Secrets will not be printed.

Required credential fields:
- `apiKey`
- `secret`
- `passphrase`

Runtime/config surfaces inspected:
- active runtime process serving `dashboard_server.py`
- runtime interpreter environment used by the bot/dashboard
- local `.env` config surface

Only presence/missing status should be reported.
