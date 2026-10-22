# Estimation method

Read this at the compute step, before any prose exists. Everything here is about getting the number right. Nothing here is about how the answer sounds.

## Contents

- Do the arithmetic in code
- The angle sweep
- Two routes
- Two passes, one of them shown
- Two significant figures
- Name the gap
- Error cancellation is not a licence
- What reaches the page
- Deep mode

## Do the arithmetic in code

Write the chain in Python and run it. Do not do it in your head and do not do it inside the draft.

This is not ceremony. Composing under a voice constraint is measurably worse for reasoning than computing plainly, and unit conversion is the specific thing that breaks — a misplaced factor of a thousand reads exactly like a correct answer. Carry units explicitly through every line, in SI, and print intermediate values with their units attached so a wrong one is visible rather than inferred.

The working goes to a scratch file. The reader never sees it.

A worked example of why: while writing the cloud exemplar in `examples/worked-answers.md`, the first pass multiplied kg/m² by 1000 to reach millimetres. But a kilogram of water per square metre already *is* a millimetre of depth. The error was a factor of a thousand, it produced the confident and completely wrong figure of 67 mm, and it was invisible until the number was compared against something known. Footnote 2 of that answer is about this.

## The angle sweep

Before computing, run down this list and pick the regimes the question actually
turns on. It takes a minute and it is the cheapest way to find the second good
answer, which is usually more interesting than the first.

Energy · momentum · mass and volume · heat · structural load · physiology ·
chemistry · rate and time · scale and geometry · logistics and cost ·
institutional and legal · ecological · historical precedent · nearest real-world
analogue.

Pick two or three in standard mode. Do not run all fourteen — a sweep that
touches everything produces an answer that is about nothing, and length spent on
a regime the question does not turn on is length taken from the one it does.

The nearest real-world analogue is the one people skip and it is often the whole
answer. Somebody has usually already built the closest legal version of the thing
being asked about, and what they ran into is better material than a clean
derivation.

## Two routes

Estimate any load-bearing number two independent ways and say whether they agree.

Independent means the routes don't share their assumptions. Per-capita consumption and industry production figures are independent. Two slightly different per-capita figures are the same route twice.

State the comparison out loud when it's interesting: agreement within an order of magnitude is the pass mark for this kind of work, and saying so is part of the form rather than an apology for it. If the two routes disagree by more than that, you have found something and should say what you think went wrong.

## Two passes, one of them shown

Before running anything, write down what you expect, anchored on a magnitude you already know. A person is about 100 watts. A car is about a tonne. The atmosphere is about 10 tonnes per square metre. Sea level air is about 1.2 kg per cubic metre.

Then compute, and compare. When the intuition pass was interestingly wrong, narrating it is often better material than the answer — it's the moment the reader learns the shape of the thing rather than its value.

## Two significant figures

Round hard. Two significant figures is the ceiling and one is frequently right.

Never print four significant figures derived from an input you guessed. "About 6,800 watts" is honest. "6,782.4 watts" is a lie about how much you know, and it is the single clearest tell that a number was generated rather than estimated. Round intermediates to simple powers of ten while you work.

Large round numbers are fine. Precision you did not earn is not.

## Name the gap

When a quantity cannot be sourced, say so in the answer and bound it, rather than inventing a figure that looks researched.

The move is to state the ignorance plainly, give the range you are confident about, pick a value inside it, and carry on. "I couldn't find a reliable figure for this, so we'll take a shot in the dark and say ten million" is a legitimate and characteristic sentence. A precise-looking number with no provenance is not.

The same rule covers hardware, statutes, papers, institutions and people: name only what you could hand a reader a link to. If an escalation ladder needs a rung you cannot verify, the ladder gets shorter. It does not get an invented rung. This constraint is stricter than the source material's own practice, deliberately — a plausible-sounding fake reference is a joke when a human writes it and a hallucination when you do, and the reader cannot tell which they are looking at.

## Error cancellation is not a licence

You will be tempted to justify a long chain of guesses on the grounds that the errors cancel. They do not reliably cancel here.

Cancellation needs independent, unbiased factors. Estimates generated in sequence from the same source share their biases, so the errors correlate and compound instead. Munroe published the counter-argument himself, in the title text of xkcd 2295: "Garbage In, Garbage Out" should not be taken to imply any sort of conservation law limiting the amount of garbage produced.

Practically: the more steps in the chain, the more of them need a real anchor. A five-step chain with one sourced number in it is not an estimate, it is a story with arithmetic in it.

## What reaches the page

Almost none of this. The reader gets the numbers that carry the answer, the assumptions that were interesting to state, and the one place where the tidy model turned out to be wrong. They do not get the spreadsheet, a methodology section, or a list of everything you considered and discarded.

Methodology in this form lives in footnotes, and it arrives as self-deprecation rather than as a disclosure statement.

## Deep mode

Three additions. Everything above still applies.

**Three-point bands, not point estimates.** Every load-bearing input gets a low,
a central and a high value, and the chain runs on all three. Report the spread
rather than the midpoint alone. This is already the archive's own move — "I ran
it three ways, because a number that small is exactly where a decimal point goes
missing" — and at four movements' worth of arithmetic it stops being optional,
because the spread is what tells you which movement is resting on a guess.

`scripts/estimate.py` has `band(name, lo, mid, hi, unit)` for this. It prints the
three values and the ratio between the ends.

**Assert the units; do not eyeball them.** `estimate.py` also has `Q`, a quantity
whose units survive multiplication and division, and `.to("unit")`, which does
not convert — it refuses when the units are not what you claimed. Put it in front
of anything the answer rests on. `Q(0.5, "kg/m2") * 1000` comes back as kg/m²,
not as millimetres, which is the exact error that got through once and produced a
confident answer wrong by a factor of a thousand.

**The anchor comparison is mandatory.** Not advisory, not "when it seems useful".
Every load-bearing number gets printed beside a magnitude a reader already has a
feel for, and you look at the ratio. `compare(label, value)` does it against a
table of standard magnitudes. If nothing in the table carries the unit, find
something yourself and say what it was.

The deep workflow independently recomputes the same quantities cold and reports
any pair disagreeing by more than 2×. Read that verdict before you draft. A
BROKEN verdict means a unit slipped somewhere, and there is no version of the
answer worth writing until you know where.
