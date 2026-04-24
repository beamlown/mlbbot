# Review Rules

Follow `BOT_BRIDGE_OPERATING_PRINCIPLES.md` as the top-level doctrine.

Claude review must decide one of:
- APPROVED
- CHANGES_REQUESTED
- BLOCKED

## Review must check
- scope stayed inside allowed files
- acceptance criteria were actually met
- commands/tests were run
- rollback is still possible
- restart requirement is stated correctly
- board/shared status should be updated if task state changed
- whether proof is source-only or runtime-proven
- whether browser refresh is required or not
- what remains unproven

## Review should state clearly
- observed
- proven
- likely
- ruled out
- next step
