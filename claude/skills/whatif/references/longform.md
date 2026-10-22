# Voice at length

Deep mode only. Read this at the draft step **in addition to** `voice.md`, not
instead of it — every rule there still holds. This file only covers what changes
when an answer runs three times as long.

## Contents

- What actually breaks
- Movements
- The shape of a movement
- Escalating across movements
- Still one impossibility
- Where the drawings and footnotes go
- The ends do not scale
- Rhythm

## What actually breaks

Not the jokes. Not the physics. The register.

A flat voice is easy to hold for six hundred words and hard to hold for two
thousand, and the failure is not that it becomes funny — it is that it becomes
uniform. Sentences settle into the same length. Paragraphs settle into the same
shape. The same two words start every third sentence. By the last movement the
answer reads like a competent explainer with drawings in it, which is the
regression `slop.md` names as flattening toward generic-human.

`check.py --deep` has three rows aimed at exactly this: SENT VAR, PARA VAR and
OPENER REPEAT. They are the only rows in the file that flag LOW rather than
HIGH, because at length the failure is too little variation rather than too much.

## Movements

A deep answer is three to six **movements**, separated by `[break]` on its own
line. The renderer sets that as a centred asterism. It is not a heading, it does
not get a title, and it never becomes one — `check.py` flags headings in both
modes and that is deliberate.

A movement is not a section of an essay. It is a complete short answer to a
different question the same scenario raises. If a movement could not stand alone
as a paragraph of the archive, it is a subsection wearing a break and it should
be merged back into its neighbour.

Three movements is a real answer. Six is the ceiling and it is rarely right.

## The shape of a movement

Each one runs the same arc the whole form runs, in miniature:

A flat claim. The derivation that earns it. The deflation.

What makes the movements a piece rather than a list is that each one starts from
where the last one landed. Movement two is not the second thing you thought of;
it is the question movement one's answer forces. If the movements could be
reordered without loss, they are a listicle and the breaks are decoration.

The reliable progression, when the physics allows it:

1. The literal answer, and the regime that produces it.
2. A second regime that changes the character of the first answer.
3. The complication the tidy model left out — `voice.md`'s second pass, given
   room to be a real argument rather than a paragraph.
4. The genuinely useful thing hiding in the wreckage.

## Escalating across movements

Escalate by re-categorising the noun, per `voice.md`, and let each break be one
category up. Never by inflating the adjective, and never by widening the blast
radius — an answer that ends larger than it started is not the same thing as an
answer that ends with more destruction than it started.

Where a ladder of real named hardware exists, it usually deserves its own
movement rather than a paragraph. In deep mode the rungs are verified, so the
ladder can be longer than standard mode would allow. It still stops where the
ledger stops.

## Still one impossibility

One. For the whole answer. Not one per movement.

This is the rule most likely to erode at length, because each new movement feels
like a fresh start that could use its own small waiver. It cannot. Three granted
impossibilities is not a What If? answer, it is worldbuilding, and the arithmetic
stops meaning anything the moment the second one is granted.

## Where the drawings and footnotes go

Roughly one drawing per movement, four to seven overall. A movement with no
drawing is fine; two movements running with no drawing means the second channel
has gone quiet and the prose is carrying the jokes alone.

Six to twelve footnotes, distributed across the movements rather than pooled at
the end of the argument. Keep the mix inside each stretch — a real caveat, a unit
pedantry, a genuine citation, a gag, all wearing the same face. A long answer
where all the jokes are in notes 9 through 12 has sorted them, and sorting them
tells the reader which is which.

## The ends do not scale

The opening sentence is still short. Median 10 words, and the flat one-word
opener is still available.

The closing paragraph is still short. Median 12 words. Do not summarise the
movements, do not gesture back across them, and do not write a paragraph whose
job is to feel like an ending. Length inflation at the close is the clearest
single tell that the register slipped somewhere in the middle and never
recovered.

`check.py` uses the same opener and closer thresholds in both modes for this
reason.

## Rhythm

Vary sentence length on purpose. A thirty-word sentence, then a six-word one,
then a twenty. Nest clauses — "although X, Y happened, because Z" — instead of
breaking every idea into its own main clause. Connect with words that carry
logic: because, so, which means, although, even though. Dramatic sentence breaks
are not an argument structure.

The deflation beat still works and still stands alone, and it is still one
paragraph. Two in a row is rare. Three is the machine-gun cadence and the archive
contains it twice in 162 articles.

At two thousand words you will reach for a familiar sentence opening without
noticing. Watch for the same two words starting sentences scattered through the
piece — "So the", "But the", "That's the". OPENER REPEAT counts them.
