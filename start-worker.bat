@echo off
:: Open a Haiku Claude Code session in the mlbbot repo, preloaded with
:: the worker role. Paste ROLES\WORKER.md as the first message, then
:: drive with `go`.
::
:: --strict-mcp-config + an empty --mcp-config disables every MCP server
:: (Gmail / Drive / Calendar / context7). Those need OAuth the operator
:: hasn't completed and would otherwise throw 'mcp failed' banners at
:: every session start. None of them are needed for worker duties.
cd /d "%~dp0"
echo Starting WORKER (Haiku). Paste ROLES\WORKER.md as the first prompt.
echo Then type 'go' to pull the next task from BOT_BRIDGE\05_INBOX_FROM_MANAGER.
echo.
claude --model claude-haiku-4-5-20251001 --strict-mcp-config --mcp-config "%~dp0ROLES\empty-mcp.json"
