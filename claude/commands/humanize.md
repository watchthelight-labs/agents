---
name: 'humanize'
description: 'Strip AI writing anti-patterns from text. Rewrite robotic prose into natural human writing, or audit text for specific AI slop patterns. Use when the user says "humanize", "de-slop", "remove AI patterns", "make it sound human", "rewrite naturally", "audit for AI writing", "slop check", or any request to remove robotic/AI-sounding language from text.'
---

# Humanize

Strip AI writing anti-patterns from text. Rewrite robotic prose into natural human writing, or audit text for specific AI slop patterns.

## Mode Detection

- **Rewrite mode**: user says "humanize", "rewrite", "de-slop", "make human", "clean up" -- return rewritten text with anti-patterns removed.
- **Audit mode**: user says "audit", "check", "flag", "review for AI", "slop check" -- return an annotated report flagging each detected anti-pattern.
- If ambiguous, default to **Rewrite mode**.

---

## Modes

### Rewrite Mode

1. Read the input text completely.
2. Scan for all 18 anti-patterns listed below.
3. Rewrite the text, removing every instance that harms the prose. Use the Rewrite Principles as your guide for what to replace patterns with.
4. A single isolated instance of a pattern is not necessarily slop -- density matters. In rewrite mode, use judgment: remove instances that make the text sound robotic or manufactured, but don't destroy a genuinely effective rhetorical move just because it matches a pattern name.
5. Preserve the author's meaning, argument structure, and tone. You are cleaning the prose, not changing the message.
6. Do not add new content, opinions, or arguments that weren't in the original.
7. Output the clean rewritten text only. No commentary, no "Here's the rewritten version:", no preamble -- unless the user explicitly asks for explanation of changes.

### Audit Mode

1. Read the input text completely.
2. Scan for every instance of all 18 anti-patterns.
3. Flag everything -- in audit mode, err on the side of over-flagging. The user wants to see all potential issues.
4. Produce the structured audit report described in the Output Format: Audit Mode section below.
5. Include a summary with total flags, most frequent pattern, and slop density (flags per 100 words).

---

## The 18 Anti-Patterns Reference

### 1. NEGATIVE PARALLELISM
- **Category:** Sentence Structure
- **Description:** The "It's not X -- it's Y" pattern, often with an em dash. Includes the causal variant "not because X, but because Y" where every explanation is framed as a surprise reveal, the em-dash dismissal "X -- not Y", and the cross-sentence reframe where the same noun is negated then repositioned: "The question isn't X. The question is Y."
- **Banned examples:**
  - "This isn't just technical -- it's a mindset change."
  - "The question isn't whether to optimize. The question is when to stop."
  - "Half the bugs you chase aren't in your code. They're in your head."

### 2. FALSE RANGES
- **Category:** Sentence Structure
- **Description:** Using "from X to Y" constructions where X and Y aren't on any real scale. In legitimate use, "from X to Y" implies a spectrum with a meaningful middle. AI uses it as a fancy way to list two loosely related things.
- **Banned examples:**
  - "From innovation to implementation to cultural transformation."
  - "From the singularity of the Big Bang to the grand cosmic web."
  - "From problem-solving and tool-making to scientific discovery, artistic expression, and technological innovation."
  - "From fundamental physics to medicine and neuroscience."

### 3. NOT X. NOT Y. JUST Z.
- **Category:** Sentence Structure
- **Description:** The dramatic countdown pattern. AI builds tension by negating two or more things before revealing the actual point. Creates a false sense of narrowing down to the truth.
- **Banned examples:**
  - "Not ambition. Not ego. Just a person who never learned to say enough."
  - "Not broken. Not behind -- Just building something no one has a name for yet."
  - "Not confidence. Not charm. Just the audacity of someone who was never told no."
  - "Not a pivot. Not a rebrand. The same product with a different story about why you should care this time."

### 4. GRANDIOSE STAKES INFLATION
- **Category:** Tone
- **Description:** Everything is the most important thing ever. AI inflates the stakes of every argument to world-historical significance. A blog post about API pricing becomes a meditation on the fate of civilization.
- **Banned examples:**
  - "This will fundamentally reshape how we think about everything."
  - "will define the next era of computing"
  - "something entirely new"
  - "What you're about to do has never been done by you. That matters more than you think."
  - "This isn't just a presentation. It's the argument you've been building your whole career."
  - "You are not running a race. You are setting the pace for everyone behind you."

### 5. IT'S WORTH NOTING
- **Category:** Sentence Structure
- **Description:** Filler transitions that signal nothing. AI uses these phrases to introduce new points without actually connecting them to the previous argument. Also includes: "It bears mentioning", "Importantly", "Interestingly", "Notably".
- **Banned examples:**
  - "It's worth noting that this approach has limitations."
  - "Importantly, we must consider the broader implications."
  - "Interestingly, this pattern repeats across industries."

### 6. THE X? A Y.
- **Category:** Sentence Structure
- **Description:** Self-posed rhetorical questions answered immediately in the next sentence or clause. The model asks a question nobody was asking, then answers it for dramatic effect.
- **Banned examples:**
  - "The result? Devastating."
  - "The worst part? Nobody saw it coming."
  - "The scary part? This attack vector is perfect for developers."
  - "The impact? Immediate."

### 7. INVENTED CONCEPT LABELS
- **Category:** Tone
- **Description:** AI clusters invented compound labels that sound analytical without being grounded. It appends abstract problem-nouns (paradox, trap, creep, divide, vacuum, inversion) to domain words and uses them as if they're established, rigorously defined terms. They function as rhetorical shorthand: name a thing, skip the argument. Multiple such labels in the same piece is a strong signal of AI slop.
- **Banned examples:**
  - "the supervision paradox"
  - "the acceleration trap"
  - "workload creep"
  - "the complexity divide"
  - "the identity inversion"

### 8. TRICOLON ABUSE
- **Category:** Sentence Structure
- **Description:** Overuse of the rule-of-three pattern, often extended to four or five. A single tricolon is elegant; three back-to-back tricolons are a pattern recognition failure.
- **Banned examples:**
  - "Products impress people; platforms empower them. Products solve problems; platforms create worlds. Products scale linearly; platforms scale exponentially."
  - "One thread loose. One seam pulled. The whole thing undone."
  - "Flour, water, salt, time. That's it. That's the whole secret."
  - "It bloomed, it browned, it dropped. Nobody was watching."

### 9. TAPESTRY AND LANDSCAPE
- **Category:** Word Choice
- **Description:** Overuse of ornate or grandiose nouns where simpler words would do. "Tapestry" for anything interconnected, "Landscape" for any field or domain. Other offenders: "paradigm", "synergy", "ecosystem", "framework".
- **Banned examples:**
  - "The rich tapestry of human experience..."
  - "Navigating the complex landscape of modern AI..."
  - "The ever-evolving landscape of technology..."
  - "A tapestry woven from diverse threads..."

### 10. ANAPHORA ABUSE
- **Category:** Sentence Structure
- **Description:** Repeating the same sentence opening multiple times in quick succession.
- **Banned examples:**
  - "They assume that users will pay... They assume that developers will build... They assume that ecosystems will emerge... They assume that..."
  - "They have built engines, but not vehicles. They have built power, but not leverage. They have built walls, but not doors."
  - "It wasn't the budget that failed. It wasn't the timeline that failed. It wasn't the team that failed. It was the premise."

### 11. HERE'S THE KICKER
- **Category:** Tone
- **Description:** False suspense transitions that promise a revelation but deliver a point that did NOT need the buildup. The model uses these phrases to manufacture drama before an otherwise unremarkable observation.
- **Banned examples:**
  - "Here's the kicker."
  - "Here's where it gets interesting."
  - "Here's what most people miss about this."
  - "Here's what most people miss"

### 12. SHORT PUNCHY FRAGMENTS
- **Category:** Paragraph Structure
- **Description:** Excessive use of very short sentences or sentence fragments as standalone paragraphs for manufactured emphasis. RLHF training has pushed models toward "writing for readability" aimed at the lowest common denominator: one thought per sentence, no mental state-keeping required. It's an inhuman style. No real person writes first drafts this way because it doesn't match how humans think or speak.
- **Banned examples:**
  - "He published this. Openly. In a book. As a priest."
  - "The policy changed. No announcement. New terms. Same checkbox."
  - "Sleep is not a reward. It's not a treat. It's not laziness. It's the whole thing."
  - "The body kept score. Quietly. Accurately. Without judgment."

### 13. LISTICLE IN A TRENCH COAT
- **Category:** Paragraph Structure
- **Description:** Numbered or labeled points dressed up as continuous prose. The model writes what is essentially a listicle but wraps each point in a paragraph that starts with "The first... The second... The third..." to disguise the format.
- **Banned examples:**
  - "The first step is research. The second is drafting. The third is review."
  - "The first reason is timing. The second is trust. The third is tone."
  - "The first factor is price. The second is quality. The third is availability."

### 14. THE TRUTH IS SIMPLE
- **Category:** Tone
- **Description:** Asserting that something is obvious, clear, or simple instead of actually proving it. If you have to tell the reader your point is clear, it very likely isn't. Also includes the dramatic reveal variant: "but none of them is the real story. The real story is..." -- claiming privileged insight while waving away everything before it.
- **Banned examples:**
  - "The reality is simpler and less flattering"
  - "The path forward is not complicated."
  - "...but none of them is the real story. The real story is that..."

### 15. THINK OF IT AS...
- **Category:** Tone
- **Description:** The patronizing analogy. AI constantly reaches for "Think of it as..." or "It's like a..." to simplify concepts. The model defaults to teacher mode and assumes the reader needs a metaphor to understand anything. Often produces analogies that are less clear than the original concept.
- **Banned examples:**
  - "Think of it like a highway system for data."
  - "Think of it as a Swiss Army knife for your workflow."
  - "It's like asking someone to buy a car they're only allowed to sit in while it's parked."

### 16. SUPERFICIAL ANALYSES
- **Category:** Sentence Structure
- **Description:** Tacking a present participle ("-ing") phrase onto the end of a sentence to inject shallow analysis that says nothing. The model attaches significance, legacy, or broader meaning to mundane facts using phrases like "highlighting its importance", "reflecting broader trends", or "contributing to the development of...".
- **Banned examples:**
  - "contributing to the region's rich cultural heritage"
  - "This etymology highlights the enduring legacy of the community's resistance and the transformative power of unity in shaping its identity."
  - "underscoring its role as a dynamic hub of activity and culture"
  - "showcasing how these dishes have integrated into the traditional diet alongside rice"

### 17. UNICODE DECORATION
- **Category:** Formatting
- **Description:** Use of unicode arrows, smart/curly quotes, and other special characters that can't be easily typed on a standard keyboard. Real writers typing in a text editor produce straight quotes and -> or =>. Claude in particular loves the unicode arrow.
- **Banned examples:**
  - "Input -> Processing -> Output" written as "Input -> Processing -> Output"
  - "This leads to better outcomes -> which means higher engagement"
  - Using curly/smart quotes instead of straight "quotes"

### 18. VAGUE ATTRIBUTIONS
- **Category:** Tone
- **Description:** Attributing claims to unnamed authorities instead of being specific. AI loves to invoke "experts", "observers", "industry reports", and "several publications" without naming anyone. It also inflates the quantity of sources -- presenting what one person said as a widely held view, or writing "several publications have cited" when it means two. If you can't name the expert, you don't have a source.
- **Banned examples:**
  - "Experts argue that this approach has significant drawbacks."
  - "Industry reports suggest that adoption is accelerating."
  - "Observers have cited the initiative as a turning point."
  - "Some critics argue that the methodology is flawed."

---

## Rewrite Principles

When rewriting, follow these positive guidelines for what TO do. Knowing what to avoid is useless without knowing what to write instead.

- **Vary sentence length naturally.** Mix long compound sentences with short ones. Don't default to fragments or to uniform medium-length sentences. A paragraph might have a 30-word sentence followed by a 6-word one followed by a 20-word one. That's how people actually write.

- **Use subordinate clauses.** Real human prose nests ideas: "Although X, Y happened because Z." Not everything needs to be a main clause standing on its own.

- **Be specific, not grand.** Replace sweeping claims with concrete details. Instead of "This will reshape everything," say what it actually does and for whom.

- **Connect ideas with actual logic.** Use "because", "so", "which means", "although", "even though" -- words that carry logical relationships. Don't substitute dramatic pauses and sentence breaks for actual argument structure.

- **Use straight quotes and plain ASCII.** No unicode arrows, no curly quotes, no decorative special characters. Write `->` not the unicode arrow. Use `"` not curly quotes.

- **Name sources or drop the attribution.** If you can't say who said it, don't write "experts say." Either find the specific source or present the claim on its own merits.

- **Let the reader decide significance.** Present facts and evidence. Don't append participial phrases that tell the reader what to think about them ("highlighting its importance", "underscoring the significance").

- **Write transitions that carry information.** Every transition sentence should either advance the argument or provide new context. If removing the transition doesn't lose any information, the transition was filler.

- **Avoid rhetorical questions you immediately answer.** If you know the answer, state it directly. "The result was devastating" not "The result? Devastating."

- **Use one tricolon max per 500 words.** And never stack them back-to-back. If you've used a three-part list, vary the next structure.

- **Don't negate before asserting.** Just assert the thing. "We need better tests" beats "It's not about more code -- it's about better tests."

- **Use plain nouns.** "field" not "landscape", "mix" not "tapestry", "tool" not "Swiss Army knife for your workflow", "area" not "ecosystem."

---

## Output Format: Rewrite Mode

Return the rewritten text only. No preamble, no "Here's the rewritten version:", no commentary on what was changed. Just the clean text.

If the user asks for an explanation of changes after receiving the rewrite, then provide a brief summary of what was removed and why.

---

## Output Format: Audit Mode

Produce a markdown table with these columns:

| # | Pattern | Category | Offending Text | Suggested Fix | Severity |
|---|---------|----------|---------------|---------------|----------|

Where:
- **#** is a sequential number
- **Pattern** is the anti-pattern name from the 18 above (e.g., NEGATIVE PARALLELISM)
- **Category** is the pattern's category (Sentence Structure, Tone, Word Choice, Paragraph Structure, Formatting)
- **Offending Text** is the exact quoted passage from the input
- **Suggested Fix** is a concrete rewrite of that specific passage
- **Severity** is Low / Medium / High based on how much the instance damages the prose (a single "Notably" opener is Low; a paragraph of stacked tricolons is High)

After the table, provide a summary:

```
**Summary**
- Total flags: [count]
- Most frequent pattern: [pattern name] ([count] instances)
- Slop density: [flags per 100 words, to one decimal place] flags/100 words
- Overall assessment: [one sentence on the text's AI-pattern saturation]
```

---

## Important Notes

- A single instance of any pattern is not necessarily slop. Humans use rhetorical questions, tricolons, and even the occasional "Notably" opener. What makes text read as AI-generated is the accumulation and density of these patterns.
- In **audit mode**, flag everything and let the user decide what to keep. Over-flag rather than under-flag.
- In **rewrite mode**, use judgment. Remove instances that make the text sound manufactured, but don't destroy a genuinely effective rhetorical move just because it technically matches a pattern.
- Never add new arguments, opinions, or claims that weren't in the original text. You are editing, not co-authoring.
- Preserve the author's voice and intent. If the original is casual, keep it casual. If it's formal, keep it formal. Strip the AI patterns, not the personality.
