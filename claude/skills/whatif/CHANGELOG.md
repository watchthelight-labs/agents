# Changelog

Author-facing. Not referenced from SKILL.md and never loaded by the model.

## 2026-08-02 (later) — deep mode

### What changed

**A second register, opt-in.** `/whatif` is untouched: same 550–850 words, same
offline single pass, same everything. `/whatif deep` adds a research pass, a
1,400–2,600 word band, movements separated by `[break]`, and a rule that a name
may be printed only if a verifier confirmed it. The two modes share every rule in
`SKILL.md`; deep adds Step 0c and swaps three reference loads.

Opt-in rather than a raised default, deliberately. The evals already name length
inflation across a session as the most likely failure, and a skill that can drift
into long form has no reference point left to detect the drift against.

**`scripts/deep-workflow.js`.** Seven agents in two waves: four regime agents and
a cold numbers adversary together, then a name verifier and a number reconciler
over the barrier. The adversary shares the first wave on purpose — it must not
see the regime agents' output or it stops being independent and becomes a
reviewer. Shipped as a file and invoked by `scriptPath`, so it costs nothing
until used.

**`references/sourcing.md`** (deep only). Source tiers retargeted from
`supersearch`'s business/tech framing to physical fact-checking, the definition of
"verified", the `claims.tsv` format, and the rule that the ledger is a whitelist.
The framing that made this cohere: Rule 2 is not a tax, it is a ceiling on
specificity, and research is the only thing that raises it. Nicheness is bought
with verification.

**`references/longform.md`** (deep only). Movements, escalation across them, the
one-impossibility discipline restated because it is the rule most likely to erode
per-movement, and the rhythm guidance imported from `humanize`.

**`examples/deep-answer.md`** (deep only). One complete 1,465-word answer with its
ledger printed after it. Written the way deep mode is meant to be run — the
figures for Lake Maracaibo, the NSSL voltage range, the CBECS hospital intensity
and the NFPA 110 classes were all fetched and checked, and the two UNVERIFIED
rows became the answer's most honest paragraph rather than a hedged sentence.

**`scripts/estimate.py`.** `Q` carries units through arithmetic with derived
units expanded to SI base, so `J/W` reduces to `s` and `Q(0.5,"kg/m2") * 1000`
comes back as kg/m² rather than quietly becoming millimetres. `.to()` asserts
rather than converts. Plus `band()` for three-point inputs and `compare()` against
a table of familiar magnitudes.

**`check.py`** gained `--deep`, `--claims`, a BREAKS row, and three
prose-variance rows. **`render.py`** gained the `[break]` asterism.

### Numbers behind the new rows

The archive has no deep mode, so the deep band set is a design decision and the
code says so. The variance floors are measured, but over the exemplars rather
than the corpus, and the comment says that too — the file's existing values are
labelled "measured, not invented" and that distinction had to survive.

| row | observed range | floor set | source |
|---|---|---|---|
| SENT VAR | 8.27 – 11.13 | 7.0 | 3 worked answers + 2 fresh drafts |
| PARA VAR | 25.67 – 35.49 | 20.0 | same |
| OPENER REPEAT | max 2 occurrences | 4, or 5.0/1k | same |

OPENER REPEAT earned its place immediately: the first draft of the deep exemplar
opened seven sentences with "It is" and nothing else in the file noticed.

### Two parser bugs, found by the exemplar

Both pre-existing, both invisible until a draft had wrapped captions.

A `[drawing: …]` caption spanning more than one line was split: the first line
became a drawing, the rest became body prose. It inflated the word count by 75,
and it fed the caption's tail into the sentence splitter, which then read the next
sentence's first word as a proper noun. `check.py` and `render.py` now both
consume to the closing bracket. Wrapped footnotes had the same shape and got the
same fix.

`render.py --outdir` with a relative path reached `Path.as_uri()` and raised,
after doing all the layout work. Resolved at parse time now.

### Deliberately not done

- **No third mode.** Deep always researches. A `/whatif research` that only
  verified, without the extra angles or length, would have been a third band set
  to keep calibrated for very little.
- **The ledger check covers names, not numbers.** Detecting "a figure presented as
  sourced" mechanically produces mostly noise, and PRECISION already covers the
  tell that matters. Eval F keeps the numbers half manual and says why.
- **No per-movement footnote quota.** Distribution is a judgement about where the
  jokes sit, and a count would have been enforced without being understood.

### Verification run

- Both standard drafts from this session re-checked: `Nothing flagged`, word
  counts unmoved.
- Deep exemplar: `Nothing flagged` at `--deep --claims`, 1,465 words, 5 drawings,
  9 footnotes, 3 breaks, ledger clean.
- Rendered twice to separate directories: 84,827 bytes both times.
- Structural read of the paginated output: 3 asterisms, 5 panels, 9 inline
  footnote spans, no orphan endnote block.
- `estimate.py` self-test, and `node --check` on the workflow script wrapped the
  way the runtime wraps it.

## 2026-08-02 — slop defenses, foot-of-page footnotes, page furniture

### What changed

**New `references/slop.md`.** Loaded at the draft step alongside `voice.md`.
Holds the precedence rule, the contested verdicts with their measurements, and
a one-paragraph sweep of everything adopted without argument. It restates what
it needs from the `humanize` skill rather than depending on it being installed.
About 650 words, which is the price of not having the model rediscover these
collisions per answer.

**`check.py` grew six slop rows** — REFRAME, SNAP Q&A, FRAG RUN, TRICOLON,
ANAPHORA and a grouped SLOP row for the near-zero-rate phrases. Same reporting
style as the existing table: a count, a note, a verdict. The notes say what the
legitimate version looks like, because four of these patterns have a
corpus-attested form that must not be deleted on sight. Thresholds are set from
the archive, not from taste.

**Step 3 gained two sentences** saying the slop rows have carve-outs and a flag
means look rather than delete. No new step and no loop; the check still runs
once.

**`render.py` now paginates properly.** Paged.js is vendored into `assets/`,
which gets `@page` margin boxes, `float: footnote` and a page counter that
Chrome does not implement. Footnotes now sit at the foot of the page that
refers to them, under a short rule, with the number hung in the margin. Pages
after the first carry a running head and a folio. Straight quotes, apostrophes,
double hyphens and ellipses are typeset at render time, so drafts stay plain
ASCII.

**Drawings stayed captions.** The compositor described in the brief was built
and then removed at the author's instruction mid-session: captions are
sufficient, no generated imagery wanted. The `[scene: ...]` draft format was
reverted from `check.py` and `render.py` together, and the framed panel is now
the intended output rather than a placeholder.

### Collision verdicts

Measured over all 162 archive articles, 113,340 words of body prose, using the
same extraction as the author's `measure.py`. The extraction was validated
against the numbers already in `voice.md`: em dash 7.79 vs 7.59 published,
semicolon 1.46 vs 1.45, exclamation 0.67 vs 0.65.

| # | Pattern | Rate | Verdict |
|---|---------|------|---------|
| 1 | Negative parallelism | 0.05 | **Carve-out.** All six instances correct a claim about the world. The cross-sentence rhetorical reframe is the banned shape. |
| 2 | False ranges | ~0 slop | Adopt. The nine hits are genuine spectra. |
| 3 | Not X. Not Y. Just Z. | 0.00 | Adopt. |
| 4 | Stakes inflation | — | Adopt; already Rule 6 and the intensifier list. |
| 5 | Filler transitions | 0.07 | Adopt; already the formal-hedge list. |
| 6 | The X? A Y. | 2.2 questions, 0.01 snaps | **Carve-out.** Structure authentic, snap form banned — one instance archive-wide. |
| 7 | Invented concept labels | 0.00 | Adopt; already Rule 2. |
| 8 | Tricolon abuse | 0.70, 5 adjacent pairs | **Compatible.** Already inside the one-per-500 ceiling. Escalation ladders are not tricolons and are explicitly protected. |
| 9 | Tapestry and landscape | 0.12 | Adopt, with a caveat: all fourteen *landscape* hits are literal terrain. |
| 10 | Anaphora | 2 instances | **Split.** Anaphora adopted; the causal clause hand-off carved out at 0.26 strict / 0.94 loose. |
| 11 | Here's the kicker | 0.00 | Adopt. |
| 12 | Short punchy fragments | runs of 1: 224, 2: 20, 3+: 2 | **Carve-out.** The single deflation beat is the device; three stacked is the failure. |
| 13 | Listicle in a trench coat | 0.00 | Adopt. |
| 14 | The truth is simple | 0.03 | Adopt. |
| 15 | Think of it as | 0.00 | **Split.** Phrase banned, flat recategorisation protected. Plain simile survives at 0.02. |
| 16 | Participial tack-ons | 0.01 | Adopt. |
| 17 | Plain ASCII | curly quotes 9.0 | **Overridden.** Typeset output; smart punctuation moved into the renderer. |
| 18 | Vague attributions | 0.00 | Adopt; already Rule 2. |

### Exemplar reconciliation

The reconciled audit flagged REFRAME twice in each of the three worked answers.
Adjudicating each of the six against the carve-out: five were factual
corrections and stayed, one was rhetorical and was cut. Two more were removed
to bring each exemplar to a single instance, since two per answer in all three
exemplars is a pattern the model would copy and is far off the archive's rate.

- **Laptops** — "So the question isn't whether it works. It's how many." became
  "So the only question is how many." Rhetorical repositioning, no fact, and
  the exact shape the corpus never uses. *Exemplar edited.*
- **Laptops** — "Two hundred is not an unimaginable number. It's four pallets."
  *Carve-out; kept.*
- **Shrew** — "The shrew isn't eating constantly because it's greedy. It's
  eating constantly because..." *Carve-out; kept.* This is the answer's pivot.
- **Shrew** — the hard-floor sentence was restructured into a single sentence
  so the negation stops being a cross-sentence pair. *Exemplar edited for rate.*
- **Clouds** — "It isn't. It's mostly air." shortened to "It's mostly air."
  *Exemplar edited for rate.*
- **Clouds** — "A cloud is not a bucket. It's the working end of a pump."
  *Carve-out; kept.* Also the protected recategorisation device.

The laptop exemplar's chained energy-flow sentences were checked against the
anadiplosis carve-out and left alone. ANAPHORA reads 0 on all three, which is
the carve-out working mechanically rather than by instruction.

All three now report Nothing flagged.

### Why the renderer drives Playwright

`--print-to-pdf` fires on the load event, which is partway through Paged.js's
chunking, so the PDF comes out as a near-empty 796-byte file. Five runs per
flag combination against the same document:

| flags | complete documents |
|---|---|
| bare | 0/5 |
| `--virtual-time-budget=15000` | 1/5 |
| `--virtual-time-budget=15000 --run-all-compositor-stages-before-draw` | 1/5 |
| `--timeout=8000` | 2/5, one of them partially paginated |
| `--virtual-time-budget=8000 --timeout=20000` | 1/5 |

It is a race, not a timing constant, so no budget value fixes it. The page now
sets `window.__pagedDone` from `PagedConfig.after`, and `render.py` drives
Playwright, waits on that beacon, then calls `page.pdf(prefer_css_page_size)`.
That is 4/4 in isolation and 9/9 byte-identical across the exemplar suite. The
command-line path is kept only for the unpaged fallback, where there is nothing
to race.

### Verification run

- Three exemplars and two fresh questions rendered end to end. Each exemplar
  rendered three times: nine PDFs, byte-identical per document.
- Visual inspection against the section D checklist passed on all five.
- Drift test across this session's three answers — pool, bicycle, hair — shows
  no length inflation (699, 567, 555), stable footnote count, stable em-dash
  density, no headings, no exclamation marks. The single flag was `745.7`
  tripping the four-significant-figure rule; it is the definition of
  mechanical horsepower, so it was judged and kept, which is the intended use
  of that row.

### Deliberately not done

- **No body serif was vendored.** Georgia was kept. It has old-style figures,
  which is what a trade book uses and what makes the numbers on the page read
  as set rather than typed, and the fallback to Times New Roman is adequate on
  a machine that has neither. Adding 400 KB for a marginal change would have
  been novelty.
- **No `@page` running head on the opening page.** It is a chapter opener and
  carries the mark instead.
