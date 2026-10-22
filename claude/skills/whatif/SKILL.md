---
name: whatif
description: >
  Answers absurd physical hypotheticals with real arithmetic in the What If?/xkcd form —
  flat one-line answer, sourced Fermi estimation, escalation through real hardware, deadpan
  closer. Use when the user asks what would physically happen in an impossible or extreme
  scenario ("what if everyone jumped at once", "how many X would it take to Y", "could you
  actually survive Z", "if I did X, what would happen"), asks for a back-of-envelope or
  order-of-magnitude estimate about the physical world, or explicitly asks for a What If?,
  xkcd, or Randall Munroe style answer. Applies to physical, biological, astronomical and
  everyday-scale questions. Not for software, architecture, debugging, product or business
  hypotheticals — "what if we used Redis instead" and "what if this returns null" are not
  this skill.
user-invocable: true
argument-hint: "[deep] <your what-if question>"
---

# What If?

Serious arithmetic, absurd question, flat delivery.

This skill writes in a form. It does not pretend to be a person. Write the answer the way What If? answers are written, but never claim to be Randall Munroe, never invent biography, and never claim research you did not do — no "I emailed a physicist", no "back when I worked at NASA". The self-deprecating register is part of the form and you should use it. The fake credentials are not.

Some facts the model tends to get wrong. The What If? web archive is 162 articles, 10 July 2012 through 6 December 2022, and it is dormant — its feed still advertises "every Tuesday" and has done since 2022, so do not claim the blog is currently publishing. Footnotes do not appear in it until article 51. This skill contains no copied xkcd or What If? text; if asked to reproduce an actual article, decline and offer to write a new answer in the form instead.

## Rules

Seven, hardest first.

1. Compute before you write a word of prose. Run the arithmetic in Python, in SI, with units carried explicitly. Composing under a voice constraint is where order-of-magnitude and unit errors happen, and they are invisible once they are inside a confident sentence.

2. Never name what you cannot point to. Statutes, products, facilities, papers, institutions, people, figures. If you cannot verify it, give it as your own estimate and say what it rests on. An escalation ladder missing a rung gets shorter; it does not get an invented rung. A plausible fake reference is a joke when a human writes it and a hallucination when you do. In deep mode a name is earned by verification, never by confidence: the claims ledger is the whitelist.

3. Answer the literal question in the first sentence, flat and short — then vary how you do it, because half the archive runs longer than the median and an answer that hits the median every time is more regular than the source.

4. Grant exactly one impossibility. Name it, waive it in a clause, then obey physics for everything downstream. Never a second one, and never argue the premise is impossible. The premise is the deal.

5. Aim every deflation at physics, institutions, or the universe. Never at the asker. This is the one place the source material itself drew complaints, and a generated answer has none of the goodwill that absorbs it.

6. Keep the body prose flat. The jokes live in the drawings and the footnotes so the sentences do not have to carry them. Losing that separation is the most likely way this goes wrong.

7. Run the check script before you emit, including on the third answer of a session. Drift shows up as length inflation and as headings appearing in something that should have none.

## Workflow

**Step 0a — Mode.** Two registers. Pick one before anything else.

`/whatif <question>` is **standard**: the whole workflow below, 550–850 words, offline, no subagents. This is the default and it is what the measured corpus values describe.

`/whatif deep <question>` — also `long` or `max` — is **deep**: a research pass first, then 1,400–2,600 words in movements, with names verified rather than hedged. Deep adds Step 0c, loads three more references, and changes the bands in Steps 3 and 4. Nothing else differs.

You may *propose* deep when a question genuinely turns on three or more separate physical regimes. Say so in one line and answer standard if the user does not take it up. Never drift into deep — an answer that grew is not the same thing as an answer that was built long, and length inflation across a session is the documented failure this skill guards against.

**Step 0b — Triage.** Decide which of four things you have.

Quantitative and answerable goes to the full form. Underdetermined but narratable gets reframed into a version you can answer, and you say in the answer that you are doing so. Semantic rather than physical — "is a hot dog a sandwich" — gets two flat lines and no lecture; a short non-answer is a legitimate output and the archive contains them. Anything with real-world hazard gets the adjacent physics plus a disclaimer in the comic register ("I am not an authority on lightning safety") and a pointer to the actual authority. Do not refuse merely because a scenario is absurd, catastrophic, or ends with the asker dying — the whole genre depends on taking those literally.

**Step 0c — Research.** *Deep only.* Read `references/sourcing.md`. Pick three to five regimes from the angle sweep in `method.md`, name the one impossibility you are granting, then run the workflow:

```
Workflow({ scriptPath: "~/.claude/skills/whatif/scripts/deep-workflow.js",
           args: { question, angles: [{name, lens, brief}, ...], granted } })
```

Invoking `/whatif deep` **is** the user's opt-in to `Workflow` and to subagents; you do not need to ask again. One agent per regime plus a numbers adversary recomputing cold, then a name verifier and a reconciler over what they returned — six to eight agents in total. If `Workflow` is unavailable, launch the same roster as parallel `Agent` calls in one message.

When it returns, write `angles.json` and `claims.tsv` to the scratch directory yourself — the agents do not write files. Read the reconciler's verdict before going on. `BROKEN` means a unit slipped; find it before drafting.

**Step 1 — Compute.** Read `references/method.md`. Do the arithmetic in Python and write the working to a scratch file. The reader never sees the working. `scripts/estimate.py` carries units through arithmetic and prints anchor comparisons; deep mode should use it, standard mode may.

**Step 2 — Draft.** Read `references/voice.md`, `references/slop.md` and `examples/worked-answers.md`. In deep mode also read `references/longform.md` and `examples/deep-answer.md`. The examples are the target; match their rhythm rather than a description of it. Write the answer into a file so it can be checked.

The draft file opens with the quoted question and the attribution line, exactly as the answer will be emitted. Both scripts read them from there, and `check.py` already keeps quoted lines out of the body word count, so nothing about the numbers changes.

**Step 3 — Check.** Run the script on the draft. Paths here are relative to this skill's own directory, not to the working directory:

```
python ~/.claude/skills/whatif/scripts/check.py <draft file>
python ~/.claude/skills/whatif/scripts/check.py <draft file> --deep --claims claims.tsv
```

It reports word count, opener and closer length, structure violations, punctuation density, drawing and footnote counts, intensifiers, any number carrying more significant figures than it earned, a block of slop rows, and three prose-variance rows that flag LOW rather than HIGH. `--deep` moves only the counts that legitimately scale with length; the opener, closer and per-thousand-word thresholds are the same in both modes on purpose. `--claims` lists every name in the body or footnotes that the ledger does not carry as VERIFIED. Fix what it flags. Once — do not loop, and do not treat every flag as an order. It counts things; it does not know whether the answer is good.

The slop rows have carve-outs written into `references/slop.md`, because several of those patterns have a form the archive genuinely uses. A flag there means look, not delete.

**Step 4 — Render.** Lay the draft out as a book page and print it to PDF. This runs every time, without being asked for:

```
python ~/.claude/skills/whatif/scripts/render.py <draft file>
```

It writes `~/Documents/whatif/whatif-<slug>.pdf`, opens it in Chrome, and prints the path. Add `--outdir DIR` to write somewhere else, `--no-open` to skip the browser, `--keep-html` to leave the intermediate page next to the PDF, `--no-paged` to skip pagination and get end-notes.

The page is 6.5 × 9.5in book trim: the mark and the question on the opening page, a running head and folio after it, footnotes at the foot of whichever page refers to them, and straight quotes typeset on the way through — so drafts stay plain ASCII. A `[break]` line becomes a centred asterism with the next paragraph flush left.

Drawing captions become framed empty panels — the honest version of a cartoon that does not exist. Do not describe the panels as illustrations in the body text; they are still captions.

If it fails, say so in one line and carry on to Step 5. The PDF is the presentation, not the answer.

**Step 5 — Emit.** Reproduce the question verbatim as a quoted header with an attribution line, then the answer, then a closing line giving the PDF path.

## Format

The question, quoted, with the asker on its own line. Use `— Anonymous` when the asker did not give a name. Then flowing prose paragraphs — no headings, no bullet lists, no tables. Two or three `[drawing: ...]` captions on their own lines, each carrying its own joke rather than restating the paragraph above it. Four to six footnotes at the end, numbered `[1]`, mixing a real caveat with a gag and giving no signal which is which.

Deep mode keeps all of that and scales three counts: 1,400–2,600 words, four to seven drawings, six to twelve footnotes. It adds one marker, `[break]` on its own line, separating three to six movements. A break is not a heading and never acquires a title — headings are flagged in both modes.

## Gotchas

Observed failures go here as they are found. Do not pre-populate this with speculation — a rule earns its place after it prevents something that actually happened.

- Installed Chrome cannot render the PDF. Given `--print-to-pdf` it hands the flags to whatever browser session is already running, exits 0, and writes nothing — a silent success that looks exactly like a working command. It is still the right thing for *opening* the finished file, where that hand-off is what you want.

- Chrome implements neither `@page` margin boxes nor `float: footnote`, and a `position: fixed` running foot repeats at the wrong offset, inside the text block. That is why the page goes through Paged.js.

- `--print-to-pdf` fires on the load event, halfway through Paged.js, and yields a near-empty 796-byte PDF. It is a race, not a timing constant, and no combination of `--virtual-time-budget`, `--timeout` or `--run-all-compositor-stages-before-draw` fixed it. `render.py` drives Playwright and waits on a beacon the polyfill sets instead; without Playwright it switches pagination off rather than leaving it to chance. Numbers in `CHANGELOG.md`.

- Setting `display: block` on a footnote inside Paged.js silently deletes its number. The marker hangs off `display: list-item`, so the hanging indent has to be built on top of that rather than replacing it.

- The unit error is real and it is the one to watch. While writing the cloud exemplar, a kg/m² figure was multiplied by 1000 to reach millimetres, when a kilogram of water per square metre already is a millimetre of depth. It produced a confident answer that was wrong by a factor of a thousand and it survived until the number was compared against something known. Compare every load-bearing number against something you already have a feel for.
