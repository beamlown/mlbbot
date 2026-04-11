# HANDOFF: SINGLE_STACK_LAUNCH_GUARD_001

## What you are doing
Add one narrow guard so a second live stack cannot come up alongside an existing one.

## Why this exists
Tonight's runtime evidence allowed mixed-stack confusion. We need one operationally obvious guard at launch time.

## Acceptable strategies
- refuse second launch if lock already held
- controlled replacement of old stack
- lockfile/PID guard

Pick one. Keep it narrow and operational.

## Scope
launch_all.py only.
Do not redesign the launcher. Do not touch bot logic.

## Deliver back
- chosen strategy
- files changed
- exact second-launch behavior
- py_compile result
- whether operator launch steps changed

## Do not do
- no broad process manager rewrite
- no dashboard work
- no bot_core changes
- no repo sweep