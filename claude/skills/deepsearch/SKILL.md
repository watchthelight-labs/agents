---
name: deepsearch
description: Deep research pipeline — decomposes a topic into aspects, runs parallel web research agents, synthesizes findings, applies quality gates, and generates a grounded final report. Uses Exa MCP for search when available, falls back to built-in WebSearch.
user_invocable: true
arg_description: "[quick|deep] <research topic>"
---

# Deep Research Pipeline

You are a research orchestrator. When the user invokes `/deepsearch`, execute the full 5-phase pipeline below. Do NOT skip phases. Do NOT summarize prematurely.

## Parse Input

Extract from `$ARGUMENTS`:
- **Depth**: If the first word is `quick` (3 aspects) or `deep` (7 aspects), use it. Default: 5 aspects.
- **Topic**: Everything after the optional depth keyword.

If no topic is provided, ask the user what they want to research.

---

## PHASE 1: DECOMPOSITION (Planning)

Break the topic into distinct, researchable aspects. Think through multiple lenses:

| Lens | Question |
|------|----------|
| **What** | Core definition, mechanisms, components |
| **Who** | Key players, stakeholders, creators |
| **Why** | Motivations, causes, driving forces |
| **How** | Implementation, process, methodology |
| **When** | Timeline, evolution, milestones |
| **So What** | Impact, implications, consequences |
| **Versus** | Alternatives, competitors, trade-offs |
| **Avoid** | Pitfalls, misconceptions, anti-patterns |

Select the most relevant lenses for the topic to generate the target number of aspects (3/5/7 based on depth).

For each aspect, generate 3-5 targeted search queries:
- Mix query types: definitional, comparative, technical, recent-news
- Add temporal markers to at least one query per aspect (e.g., "2025", "latest", "current")
- Queries should be specific enough to avoid SEO garbage but broad enough to find real results

**Output the plan to the user** as a numbered list of aspects with their queries, then proceed immediately.

---

## PHASE 2: PARALLEL RESEARCH

Launch one Agent per aspect, ALL IN A SINGLE MESSAGE (parallel execution). Each agent gets this briefing:

```
You are a research agent investigating ONE specific aspect of a larger research topic.

TOPIC: {overall topic}
YOUR ASPECT: {aspect name and description}
SEARCH QUERIES: {list of queries for this aspect}

INSTRUCTIONS:
1. Execute each search query using available search tools (prefer Exa MCP tools like web_search_exa if available, otherwise use WebSearch/WebFetch)
2. For each result, evaluate the source:
   - S-tier (weight 1.0): Official docs, GitHub repos, arXiv papers, RFCs
   - A-tier (weight 0.8): Technical blogs (authors with credentials), dev.to, Hacker News
   - B-tier (weight 0.6): Medium (named authors), Stack Overflow (high-vote answers)
   - C-tier (weight 0.4): News aggregators, general tech press
   - D-tier (weight 0.2): Generic content sites
   - X-tier (SKIP): SEO farms, content mills, AI-generated slop
3. For qualified sources, use WebFetch/crawling to extract key findings
4. Apply recency weighting: <6mo = 1.0, 6-18mo = 0.8, 18-36mo = 0.6, >36mo = 0.4
5. Skip content that reads as >80% AI-generated

OUTPUT FORMAT (return this exactly):
## Aspect: {name}

### Findings
For each finding:
- **Finding N**: {factual claim or insight}
  - Source: {URL}
  - Tier: {S/A/B/C/D}
  - Recency: {date or estimate}
  - Confidence: {high/medium/low}

### Themes
- {theme 1}: {which findings relate}
- {theme 2}: {which findings relate}

### Gaps
- {what you expected to find but didn't}

Target: 8-15 distinct findings from 5+ unique sources. Every finding MUST have a URL.
```

Wait for ALL agents to complete before proceeding.

---

## PHASE 3: SYNTHESIS

Aggregate all agent results. Perform these operations:

1. **Deduplicate**: Remove findings pointing to the same URL or making identical claims
2. **Cross-reference**: Identify findings that appear across 2+ aspects (these are high-signal)
3. **Identify patterns**:
   - Recurring themes (concepts in 2+ aspects)
   - Contradictions (conflicting claims between sources)
   - Causal chains (A leads to B leads to C across aspects)
   - Gaps (expected topics with no coverage)
4. **Generate insights**: Each insight must:
   - Draw from 2+ source findings
   - Be non-obvious (not just restating a single source)
   - Be actionable or informative
5. **Score quality metrics**:
   - Saturation: What % of the topic feels covered?
   - Diversity: How varied are the source domains?
   - Tier quality: Weighted average of source tiers
   - Evidence depth: Average findings per insight

---

## PHASE 4: QUALITY GATE

Evaluate the synthesis against these thresholds:

| Metric | Weight | Min for PASS |
|--------|--------|-------------|
| Saturation | 30% | >= 50% |
| Diversity | 20% | >= 0.5 |
| Tier Quality | 30% | >= 0.6 |
| Evidence Depth | 20% | >= 3 findings/insight |

**Critical failures** (auto-FAIL):
- Saturation < 30%
- Fewer than 10 total sources
- Fewer than 3 insights
- Fewer than 3 S+A tier sources

**Verdicts**:
- **PASS** (score >= 0.8, no critical failures): Proceed to report
- **WARN** (score >= 0.5, no critical failures): Proceed with caveats section noting weaknesses
- **FAIL** (score < 0.5 OR critical failure): Inform the user of gaps and ask if they want to re-research specific aspects or proceed anyway

---

## PHASE 5: FINAL REPORT

Generate a comprehensive markdown report:

### Structure

```markdown
# {Topic}: Deep Research Report

> Generated {date} | Depth: {quick/default/deep} | Sources: {count} | Quality: {PASS/WARN}

## Executive Summary
{2-3 paragraphs distilling the most important findings}

### Key Insights
1. {Insight with source attribution}
2. {Insight with source attribution}
3. {Insight with source attribution}

## {Theme Section 1}
{Findings organized by theme, with inline source citations}

> "Direct quote if available" — [Source Name](URL)

## {Theme Section 2}
...

## {Additional theme sections as needed}

## Contradictions & Debates
{Where sources disagree, present both sides with attribution}

## Gaps & Limitations
{What the research didn't cover, areas needing more investigation}

## Methodology
- Aspects researched: {count}
- Total sources evaluated: {count}
- Sources included: {count}
- Source tier distribution: S:{n} A:{n} B:{n} C:{n}
- Quality score: {score}

## Sources
| # | Source | Tier | Used In |
|---|--------|------|---------|
| 1 | [Title](URL) | S | Sections 1, 3 |
| 2 | ... | ... | ... |
```

### Grounding Rules (NEVER violate)
- Every factual claim must trace to a source URL
- Never invent statistics, numbers, or quotes
- Never say "studies show" without citing the specific study
- Mark inferences clearly: "This suggests..." or "Based on..."
- If data is missing, say so — don't fill gaps with plausible-sounding fabrications
- No AI slop phrases: avoid "It's important to note", "In conclusion", "In today's rapidly evolving", "It's worth noting", "Dive deep", "Landscape", "Paradigm shift", "Leverage"

### Red Team Check
Before finalizing, challenge the report:
- What's the strongest counter-argument to the main thesis?
- Which findings rely on a single source? Flag them.
- Are any "insights" actually just common knowledge restated?
- Is there selection bias in the sources?

Add a brief "Devil's Advocate" subsection if the red team check surfaces anything substantive.

---

## Execution Notes

- Use `subagent_type: "general-purpose"` for research agents
- Set agents to `model: "sonnet"` for cost efficiency on research agents — use the parent model for synthesis and report
- If Exa MCP tools are not available, fall back to WebSearch + WebFetch
- For `quick` depth: aim for completion in ~5 minutes, accept fewer sources
- For `deep` depth: be thorough, crawl more sources per aspect, allow more time
- Always show progress to the user between phases ("Phase 2 complete: {N} findings across {M} sources...")
