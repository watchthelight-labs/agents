# Evals

Author-facing. Not referenced from SKILL.md and never loaded by the model.

There is no built-in runner for these. Run them by hand in fresh sessions.

## A. Trigger set

Run each 3×, in a clean session, and record whether the skill fired. Target: should-fire ≥ 0.5. **Any false fire in group A2 is a blocker** — this skill lives in a coding tool where "what if" is overwhelmingly an engineering phrase.

If A2 leaks, tighten the description first. If it still leaks, set `disable-model-invocation: true` in the frontmatter and rely on `/whatif`. A skill that misses half its real invocations is a nuisance; a skill that hijacks every architecture discussion is worse.

### A1 — should fire

Four of these carry no skill-adjacent keyword at all, which is the real test.

1. What if everyone on Earth flushed a toilet at the same moment?
2. What if I tried to heat my flat with candles?
3. How many balloons would it actually take to lift a house?
4. If I jumped off the Empire State Building holding a helium balloon, how big would it need to be?
5. Could you actually survive a fall into water from a plane if you hit it feet first?
6. What would happen if the Moon were made of cheese?
7. Suppose every ant on Earth pulled in the same direction. Would anything move?
8. Give me a back-of-envelope estimate for how much a cloud weighs.
9. Answer this like Randall Munroe: what if my coffee never went cold?
10. If all the world's ice melted into my bathtub, roughly how big a bathtub?

### A2 — must NOT fire

1. What if we used Redis instead of Postgres here?
2. What if this function returns null?
3. What if I refactor this into a hook?
4. What would happen if we deployed this on Friday?
5. Explain how a refrigerator works.
6. What's the boiling point of liquid nitrogen?
7. What if the user has no network connection — how should we handle it?
8. What if we raised prices by 10%?
9. How many requests per second can this endpoint handle?
10. What if I ran the migration twice?

Note that A2.5 and A2.6 are ordinary physics questions with no hypothetical in them. They should get a normal answer, not an 800-word deadpan essay. This distinction is easy to lose and worth checking.

## B. Quality cases

Run each **twice**: once in a clean session with the skill unavailable (baseline), once with it. Save both. Anthropic's guidance is to establish the baseline before writing extensive instructions, so that every rule has to justify its tokens against what the model already does unprompted.

1. What if I tried to fill my swimming pool with sparkling water instead of tap water?
2. What if human hair grew a thousand times faster?
3. What if the Earth stopped absorbing sunlight for one day?

Compare on voice, not on correctness. Look specifically for: did the baseline already produce the flat opener without being told, does the skill version have more jokes per paragraph rather than fewer, and did the skill version invent any named hardware or citation the baseline avoided.

## C. Drift test

The important one, and the one most likely to fail.

Ask all three B questions in a **single** session, in order, and run `check.py` on each answer.

Watch for: answer three running long, a heading appearing, footnote count drifting up, exclamation marks arriving, the bureaucratic closer being reused all three times. Persona drift shows first as length inflation and formatting-contract breaks.

If answer three is materially worse than answer one, the check step is not firing reliably and needs to be more prominent in the workflow — or the skill needs to be smaller.

## C2. Deep-mode drift test

Same idea as C, run with `/whatif deep` and `check.py --deep`. Three deep answers
in one session.

Deep mode fails differently from standard mode, and the failures to watch for are
not the same ones:

1. **The ends inflating.** OPENER and CLOSER use the same thresholds in both
   modes deliberately. A deep answer that opens with a paragraph of throat
   clearing or closes with a summary of its own movements has lost the register,
   whatever the middle looks like.
2. **Movements becoming sections.** A `[break]` followed by a sentence that
   announces what the next movement is about is a heading in prose. So is a
   movement that could be reordered with its neighbour.
3. **A second impossibility.** The most likely erosion, because each new movement
   feels like a fresh start entitled to its own waiver. Count them. There is one.
4. **The ladder outrunning the ledger.** Run `--claims` on all three. A name in
   answer three that is not in `claims.tsv` means Rule 2 stopped being enforced
   somewhere around the second answer.
5. **Variance collapsing.** SENT VAR and PARA VAR falling toward their floors
   across the three answers is flattening, and it will not show up as any other
   flag.

## D. Render fidelity

By hand, on a rendered PDF. The question is whether a page would pass at arm's length as a photograph of the book, so look at it before reading it.

1. Opening page carries the mark, the question in italic, the attribution right-aligned under it, then the rule. No running head and no folio on that page.
2. First paragraph flush left; every later one indented. Indent resets to flush after a drawing panel.
3. Justified, hyphenated, no rivers, no line ending in a single stranded word.
4. Panels sit whole on one page — never split across a break.
5. Footnotes at the foot of the page that refers to them, under a short rule, numbered, hanging indent. Not collected at the end. If they are collected at the end, Paged.js did not run and the fallback fired; check whether Playwright is still installed.
6. Folio bottom-centre and running head top-centre on every page after the first.
7. Hand lettering is xkcd Script — narrow and even. If it looks like Comic Sans or Segoe Print, the font asset is missing and the fallback fired.
8. Quotes and apostrophes curled, dashes em. Nothing straight survives into the PDF.
9. No browser furniture: no date, no URL, no "about:blank", no double rules.

Deep mode adds two:

10. Movement breaks are centred asterisms, optically centred rather than sitting
    a letter-space right of centre, and the paragraph after each one is flush
    left. A break stranded at the top of a page or orphaned at the foot means the
    `break-before`/`break-after: avoid` pair is not being honoured.
11. A page carrying three or four footnote references still sets them all at its
    own foot. If the footnote block has pushed body text off the page or
    collected at the end, Paged.js gave up and the fallback fired.

Render the same draft twice and compare file sizes. They should be byte-identical. If they are not, the render is racing something.

## E. Slop-collision probes

Each of these baits a pattern that has a written verdict in `references/slop.md`. Run the answer through `check.py` and then read the flagged line yourself — the point is whether the carve-out was applied correctly, not whether the row is zero.

1. What if I replaced my morning coffee with an equivalent dose of caffeinated toothpaste? — baits the corrective negation. One factual correction is fine; "the question isn't X, it's Y" is not.
2. What if I had to walk everywhere at exactly one mile per hour? — baits the deflation beat. One short paragraph after a long technical one is the device; three stacked is the failure.
3. How much would the sky weigh if you could put it on a scale? — baits the self-posed question. Pose and answer in a sentence; no snap fragment.
4. What if every book ever printed were stacked in one pile? — baits chained repetition and the tricolon. A causal hand-off is allowed; a rhetorical drumbeat is not.
5. What if I tried to power my house by pedalling a bicycle? — baits the escalation ladder. It should survive untouched; if it has been sanded into a smooth paragraph, the slop rules are being over-applied.

The failure to watch for across all five is flattening toward generic-human. If an answer reads like a competent blog post rather than a page of *What If?*, that is the regression, and the fix is to restore the voice rather than relax the rule.

## F. Honesty spot-check

Take one full answer and extract every named thing: statute, product, facility, paper, institution, person, and every figure presented as sourced rather than estimated. Verify each one independently.

This is the rule most likely to fail silently, because a fabricated citation reads exactly like a real one. Rule 2 exists for this and it is the only rule whose failures are invisible without deliberate checking.

In deep mode the name half of this is mechanical: `check.py --claims claims.tsv`
reports every capitalised name in the body or footnotes that the ledger does not
carry as VERIFIED. Run it, and then still open two or three of the VERIFIED URLs
by hand, because the check proves a row exists and cannot prove the row is true.
The numbers half stays manual — the ledger check deliberately covers names only.

The failure to watch for is a ledger with a row for everything and a page behind
none of it. A whitelist that is never contradicted is not evidence that the
whitelist is working.

## G. Model coverage

Run section A on Haiku, Sonnet and Opus. Description discovery behaves differently across tiers and the description is the entire trigger surface.

## Recording results

Append failures to the Gotchas section of SKILL.md — but only things that actually happened. A speculative rule costs tokens on every invocation and prevents nothing.
