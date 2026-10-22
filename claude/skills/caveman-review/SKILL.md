---
name: caveman-review
description: >
  One-line code review feedback with exact line references. Format: L<line>: <problem>. <fix>.
  Severity prefixes for mixed-severity reviews. Cuts filler, keeps line numbers, symbol names,
  and concrete fixes. Use when user says "review this code", "code review", or invokes /caveman-review.
user_invocable: true
arg_description: '[file or PR number]'
---

Code review: one comment per line. No throat-clearing.

## Format

Single-file: `L<line>: <problem>. <fix>.`
Multi-file: `<file>:L<line>: <problem>. <fix>.`

## Severity Prefixes (optional, use for mixed-severity reviews)

- `🔴 bug` — broken, will fail at runtime or produce wrong results
- `🟡 risk` — fragile, works now but breaks under edge cases or future changes
- `🔵 nit` — style, naming, or convention — not blocking
- `❓ q` — question, not a suggestion — need clarification before judging

## Rules

**Include:** exact line numbers, symbol names in backticks, concrete fix (not "consider improving"), reasoning when non-obvious (one clause, not a paragraph).

**Drop:** "I noticed that...", "It might be worth considering...", "Perhaps you could...", "Great job on...", self-congratulation, restating what the code already shows.

## Examples

Bad:
> I noticed that on line 42, the `user` variable could potentially be null after the `.find()` call, which might cause issues when you try to access `.email` on the next line. You might want to consider adding a null check here to handle the case where the user isn't found in the database.

Good:
> L42: 🔴 bug: `user` can be null after `.find()`. Add guard before `.email`.

Bad:
> The error handling in this function looks good overall, but I think it would be beneficial to add a more specific error type instead of catching all errors with a generic catch block.

Good:
> L89: 🟡 risk: bare `catch(e)` swallows typed errors. Catch `HttpError` explicitly, rethrow rest.

## Exceptions

Security findings, architectural disagreements, and onboarding reviews (first PR from a new contributor): revert to full explanation. These need rationale beyond the surface problem. Resume terse after the long comment.

## Boundaries

Only review format — not a gate on whether to approve/request changes. "stop caveman-review" or "normal mode": revert to verbose review style.
