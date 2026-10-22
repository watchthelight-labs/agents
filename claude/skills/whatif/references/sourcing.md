# Sourcing

Deep mode only. Read this before the workflow step, and again before drafting.

Rule 2 says never name what you cannot point to. In standard mode that is a
ceiling: with no way to check anything, the honest move is to hedge, and hedged
prose is less interesting than named prose. Deep mode is the way out. It does not
relax Rule 2 — it gives you a way to satisfy it, and specificity is the reward.

## Contents

- The trade
- Tiers
- What verified means
- The ledger
- What a WRONG verdict does
- The obscurity budget
- Numbers

## The trade

Research buys names. Nothing else does.

An answer's texture comes from the real thing that turns out to exist: a
documented incident, a unit nobody uses any more, a piece of hardware built for
one purpose in one place. Deep mode exists so those can appear on the page
instead of being hedged into "something like" and "a facility somewhere".

The exchange rate is one-way. Verification lets you name something. Confidence
never does, no matter how sure the thing feels, because a plausible-sounding fake
reference reads exactly like a real one and the reader has no way to tell.

## Tiers

Best first. Weight what you keep accordingly.

**S** — standards bodies and physical-constant tables (BIPM, NIST, CODATA);
national statistical and scientific agencies and their published datasets;
peer-reviewed papers; laws, treaties and regulations in their own text; court
records; official incident and accident reports.

**A** — manufacturer datasheets and technical manuals; engineering handbooks and
textbooks; university course material with the working shown; long-standing
reference works; domain-expert writing where the author is named and checkable.

**B** — reputable technical journalism; museum and archive catalogue entries;
maintainer and operator write-ups; forum and practitioner reports, but only for
quantities nobody else bothers to measure.

**C** — general news and summaries. Fine for the existence of an event, weak for
any number attached to it.

**D** — generic explainers and aggregators. Leads only. Follow them to the source
or drop the claim.

**X** — SEO pages, content mills, AI-written explainers, and anything that repeats
another page's sentences. Skip entirely. These are where a wrong number goes to
become four independent-looking citations.

Two sources from the same tier that trace to the same original are one source.
Citation loops are the specific failure — a figure gets quoted, then quoted from
the quote, until five pages agree and none of them measured anything.

## What verified means

You opened a page. The page says the thing. The thing is what you are about to
print.

All three. A page that exists is not verification of a claim it does not make. A
correct claim you did not open a page for is not verified either; it may well be
true, and it still goes in the answer as your own estimate.

Recency matters where the fact moves. Production figures, prices, records and
legal status need a date. Physical constants and historical events do not.

## The ledger

The workflow returns verification rows; write them to `claims.tsv` in the scratch
directory, tab-separated, one row per named thing:

```
status      name                    url                 title           note
VERIFIED    Minamata Convention     https://...         UNEP text       in force 2017
UNVERIFIED  the Odense heat scheme                                      no primary source found
WRONG       flask = 35 kg                               —               a flask is 34.5 kg
```

`check.py --claims claims.tsv` reads it back and reports every capitalised name
in the body or the footnotes that is not on it. That check covers names only;
numbers are the PRECISION row's job and yours.

**The ledger is a whitelist.** The draft may name a thing only if it has a
VERIFIED row. Everything else is either dropped or given as your own estimate
with its basis stated in the same sentence.

The check is advisory, as everything in `check.py` is. It over-reports, and a
flag means look. What it cannot do is tell you that something absent from the
ledger was checked anyway — so do not let it become the reason you stopped
thinking about Rule 2.

## What a WRONG verdict does

The ladder gets shorter.

It does not get a substitute rung invented to fill the space, and the surrounding
sentences do not get rewritten to imply the rung is still there. Three real rungs
beat four with one hollow one, and the hollow one is the only part a reader will
remember checking.

The same applies to a whole movement. If verification kills the fact a movement
was built on, the movement goes. That is the system working.

## The obscurity budget

At least one genuinely obscure verified thing per movement, and it has to be
load-bearing rather than decorative — it appears because the argument reached it,
not because it was interesting and got fitted in.

A unit that fell out of use. An incident with a report number. A machine built
once. A measurement somebody made for an unrelated reason forty years ago and
nobody has needed since.

One of those beats three hedged estimates, and it is the entire reason deep mode
goes online.

## Numbers

Never invent a URL, a title, a date, or a figure. Omit what you could not verify
and say you could not verify it — "I couldn't find a reliable figure for this, so
we'll take a shot in the dark and say ten million" is a legitimate and
characteristic sentence.

Where a sourced figure and your own estimate disagree, say so on the page. That
disagreement is usually more interesting than either number.
