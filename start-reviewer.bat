@echo off
:: Open a Sonnet Claude Code session in the mlbbot repo, preloaded with
:: the reviewer role. Paste ROLES\REVIEWER.md as the first message,
:: then drive with `review`.
::
:: --strict-mcp-config + empty --mcp-config: see start-worker.bat.
cd /d "%~dp0"
echo Starting REVIEWER (Sonnet). Paste ROLES\REVIEWER.md as the first prompt.
echo Then type 'review' to pull the next RESULT without a REVIEW yet.
echo.
claude --model claude-sonnet-4-6 --strict-mcp-config --mcp-config "%~dp0ROLES\empty-mcp.json"
