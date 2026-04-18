@echo off
cd /d "%~dp0.claude-roles\worker"
title Worker (Haiku)
claude --model claude-haiku-4-5-20251001
