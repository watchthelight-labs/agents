# Slop

Read this at the draft step with `voice.md`. It holds only the deltas between generic anti-AI-writing advice and this form. The full catalogue lives in the `humanize` skill; everything needed here is written out, so nothing breaks if that skill is not installed.

## Precedence

Corpus evidence outranks a generic anti-slop rule. Where the corpus is silent, the anti-slop rule applies.

Over-applying them has a failure mode and it deserves a name: **flattening toward generic-human**. The target is not "reads like a person wrote it". It is "reads like a page of What If?" — a narrower register, drier and flatter than most human writing. A de-slopped draft that reads like a competent blog post is a regression exactly as caricature is, and the fix is to put the voice back, not to quietly relax the rule.

## Contested, with the measurement

Rates are per thousand words of body prose, measured over all 162 archive articles (113,340 words).

**The deflation beat survives.** A one-to-four-word paragraph standing alone after a long technical one is the timing device, not a fragment habit. Runs of exactly one short paragraph occur 224 times; runs of two, 20 times; runs of three or more, twice in the whole archive. One beat is the device. Three stacked is the machine-gun cadence the rule is actually about.

**Rhetorical reframes are out; factual corrections stay.** The negate-then-assert pair runs at 0.05 — six instances in 162 articles — and every one of them corrects a claim about the world rather than repositioning the argument. The problem with getting to orbit isn't that space is high up; it's that you have to go sideways very fast. So: a negation that corrects a real expectation is allowed, about once per answer. A negation that reframes what the question is *about* and carries no fact is not, and "the question isn't whether it works, it's how many" is the shape to watch for.

**Self-posed questions are authentic; the snap answer is not.** Interior questions run at 2.2, and 1.3 of those are answered by a full sentence. That is the structure — a question used as a pivot into the derivation. The snap form, a short question answered by a fragment, occurs exactly once in the archive. Pose the question, then answer it in a sentence.

**Chained repetition is allowed when it carries the physics.** Clause-to-clause hand-offs, where the object of one clause becomes the subject of the next, run at 0.26 strictly counted and 0.94 loosely. That is a causal path being traced, and it is a different thing from the same sentence opener stamped three times, which occurs twice in the archive and is banned. The test: each repetition has to move the energy, the water or the argument one step along. If the repeated element is doing rhythm rather than work, cut it.

**Escalation ladders are not tricolons.** A ladder is real named hardware climbed in order and it stays. Three-part lists run at 0.70 with five adjacent pairs across the archive, comfortably inside the one-per-500-words ceiling, so no separate rule is needed — just do not stack them.

**Straight-ASCII does not apply.** The deliverable is a typeset page. Em dashes are corpus-measured at 7.6 and have a band in `check.py`; the archive itself sets 9.0 curly quotes per thousand words. Write drafts in plain ASCII for your own convenience — `render.py` converts quotes, apostrophes and ellipses at layout time.

**Ban the framing phrase, keep the device.** "Think of it as" and "it's like a" occur zero times between them. The underlying move occurs constantly and is core to the form: assert the identity flatly and move on. A laptop *is* a space heater that has been persuaded to do arithmetic on the way through. Nobody is asked to think of it as one. The plain simile survives at 0.02, so it is not banned either — it is just rare enough that you should have a reason.

## Flattening at length

The patterns above are phrases, and a phrase is easy to find. Past about a
thousand words the failure stops being a phrase.

What goes instead is variation. Sentences converge on one length. Paragraphs
converge on one shape. The same two words start sentences scattered right through
the piece — "So the", "But the", "That's the" — without ever repeating adjacently
enough to trip the anaphora rule. Nothing in the draft is quotable as slop and the
whole thing reads as machine-set.

Three rows in `check.py` measure it: SENT VAR, PARA VAR and OPENER REPEAT. They
are the only rows in the file that flag LOW rather than HIGH. Floors are
exemplar-derived rather than corpus-derived and the code comment says so — over
the three worked answers and two fresh drafts, sentence sd ran 8.3 to 11.1,
paragraph sd 25.7 to 35.5, and no two-word opener repeated more than twice.

The fix is the same one this whole file argues for: put the voice back, rather
than smooth the draft further. A long answer that has been de-slopped into an
even, readable, unremarkable rhythm has failed in the direction nobody checks for.

## Adopted without argument

None of these occur in the archive at a rate worth defending, and most already have a home in the existing rules. False ranges, the Not-X-Not-Y-Just-Z countdown, stakes inflation (Rule 6 and the intensifier list), filler transitions (the formal-hedge list), invented concept labels and vague attributions (Rule 2 — if you cannot name it, you do not have it), ornate nouns, here's-the-kicker, the listicle in a trench coat, the-truth-is-simple, and participial tack-ons that tell the reader what a fact means.

One caveat on ornate nouns: *landscape* appears fourteen times in the archive and every one of them is literal terrain. Ban the figure of speech, not the ground.
