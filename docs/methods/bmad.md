<!-- <wtl> project: agents | file: docs/methods/bmad.md | author: watchthelight </wtl> -->
# BMAD

Big projects fail at the start, when an agent builds the first plausible thing instead of the thing I meant. BMAD is how I stop that: interrogate the idea until it's sharp, then build it in phases that each have to pass a gate.

## 1. Interrogate: `/deepstorm`

[deepstorm](../../claude/skills/deepstorm/SKILL.md) is a brainstorming skill that asks before it answers, in four stages:

- **B, Broad extraction:** what I want, why, for whom, what success looks like, what I refuse to accept.
- **M, Map the design space:** the real options and their trade-offs, laid out side by side.
- **A, Architecture interrogation:** hard questions about the chosen shape: constraints, failure modes, what has to be true.
- **D, Decide the direction:** one recommendation, the non-negotiables, the open questions.

Questions come as single-choice, multiple-choice or free text depending on what they are probing, with forced trade-offs ("you can't have both, pick"). Contradictions in my answers get called out instead of averaged away. The output is a **brief**: core intent, non-negotiables, the architecture, the plan, and the risks.

## 2. Build in gated phases

The brief becomes a numbered series of phase prompts in the project, `plan/00-begin.md` through `plan/12-ship.md` for a big one. Each phase:

- has a goal, inputs (the brief plus the earlier phases' outputs) and a definition of done;
- ends at a **gate**: tests, a measurement, or my explicit OK on the result;
- is run by a fresh agent session that reads only what that phase needs, so a long project never depends on one context window remembering everything.

Smaller projects use one bootstrap prompt with lettered checkpoints (A to F) instead of separate files.

## Why it works

- The interrogation is cheap compared to building the wrong thing.
- Gates make "done" something the agent has to prove, not claim.
- Fresh sessions per phase keep the quality of the last phase as high as the first.

The memory server keeps the brief, each gate's result and every open question, so any session (or any device) can pick the project up where it stopped.
