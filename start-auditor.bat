@echo off
:: Open an Opus Claude Code session in the mlbbot repo, preloaded with
:: the auditor role. Paste ROLES\AUDITOR.md as the first message, then
:: drive with `audit vX.Y.Z` when a patch is ready for ship-gate.
cd /d "%~dp0"
echo Starting AUDITOR (Opus). Paste ROLES\AUDITOR.md as the first prompt.
echo Then type 'audit v0.2.0' (or whichever patch) to run the ship-gate audit.
echo.
claude --model claude-opus-4-7
