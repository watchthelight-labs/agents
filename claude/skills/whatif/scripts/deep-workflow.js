export const meta = {
  name: 'whatif-deep',
  description: 'Deep-mode research pass for a What If? answer: parallel angle agents, a cold numbers adversary, then name verification and reconciliation.',
  whenToUse: 'Invoked by the whatif skill when the user asks for /whatif deep. Not useful on its own.',
  phases: [
    { title: 'Angles', detail: 'one agent per physical regime, plus a cold recompute' },
    { title: 'Verify', detail: 'check every candidate name; reconcile the numbers' },
  ],
}

// Runs BEFORE any prose exists. Everything here feeds the compute step and the
// claims ledger; none of it is written by the agents themselves. The parent
// writes angles.json and claims.tsv from what this returns, so there is one
// writer and no race.
//
// args: {
//   question: string,          the asker's question, verbatim
//   angles:  [{ name, lens, brief }],   3-5, chosen by the parent
//   granted: string,           the one impossibility being waived, or ""
// }

const { question, angles, granted } = args || {}
if (!question || !angles || !angles.length) {
  throw new Error('deep-workflow needs args.question and a non-empty args.angles')
}
if (angles.length > 6) {
  log(`angles capped at 6; dropping: ${angles.slice(6).map(a => a.name).join(', ')}`)
}
const ANGLES = angles.slice(0, 6)

// ---- schemas ----------------------------------------------------------------

const QUANTITY = {
  type: 'object',
  required: ['name', 'value', 'unit', 'routeA', 'routeB', 'agreementNote', 'anchor'],
  properties: {
    name: { type: 'string', description: 'what this quantity is' },
    value: { type: 'number', description: 'central estimate, SI' },
    unit: { type: 'string', description: 'SI unit, explicit, e.g. "kg/m2"' },
    low: { type: 'number' },
    high: { type: 'number' },
    routeA: { type: 'string', description: 'first derivation, with its inputs' },
    routeB: { type: 'string', description: 'an INDEPENDENT second derivation; say so plainly if you could only find one' },
    agreementNote: { type: 'string', description: 'do the two routes agree inside an order of magnitude, and if not what went wrong' },
    anchor: { type: 'string', description: 'a familiar magnitude this was compared against' },
    anchorRatio: { type: 'string', description: 'how many times the anchor this is' },
    loadBearing: { type: 'boolean', description: 'does the answer change if this is wrong' },
  },
}

const CANDIDATE = {
  type: 'object',
  required: ['name', 'kind', 'claim'],
  properties: {
    name: { type: 'string', description: 'the thing exactly as it would be printed' },
    kind: { type: 'string', enum: ['statute', 'product', 'facility', 'paper', 'institution', 'person', 'incident', 'unit', 'figure', 'other'] },
    claim: { type: 'string', description: 'what the answer would assert about it' },
    url: { type: 'string', description: 'a real URL you actually opened, or "" if none' },
    title: { type: 'string' },
  },
}

const ANGLE_SCHEMA = {
  type: 'object',
  required: ['angle', 'quantities', 'candidates', 'gaps'],
  properties: {
    angle: { type: 'string' },
    headline: { type: 'string', description: 'the one-sentence flat answer from this regime alone' },
    quantities: { type: 'array', items: QUANTITY },
    candidates: { type: 'array', items: CANDIDATE },
    ladder: { type: 'array', items: { type: 'string' }, description: 'real named hardware or precedents in ascending order, each of which you could hand a reader a link to' },
    complication: { type: 'string', description: 'the thing a tidy model of this regime leaves out' },
    gaps: { type: 'array', items: { type: 'string' }, description: 'what you expected to find and could not verify' },
  },
}

const ADVERSARY_SCHEMA = {
  type: 'object',
  required: ['quantities', 'assumptions'],
  properties: {
    quantities: { type: 'array', items: {
      type: 'object',
      required: ['name', 'value', 'unit', 'working'],
      properties: {
        name: { type: 'string' },
        value: { type: 'number' },
        unit: { type: 'string' },
        working: { type: 'string' },
      },
    } },
    assumptions: { type: 'array', items: { type: 'string' } },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['rows'],
  properties: {
    rows: { type: 'array', items: {
      type: 'object',
      required: ['name', 'status', 'note'],
      properties: {
        name: { type: 'string' },
        status: { type: 'string', enum: ['VERIFIED', 'UNVERIFIED', 'WRONG'] },
        url: { type: 'string' },
        title: { type: 'string' },
        note: { type: 'string', description: 'for WRONG, what the truth is; for UNVERIFIED, what you tried' },
      },
    } },
  },
}

const RECONCILE_SCHEMA = {
  type: 'object',
  required: ['disagreements', 'verdict'],
  properties: {
    disagreements: { type: 'array', items: {
      type: 'object',
      required: ['quantity', 'ratio', 'suspect', 'why'],
      properties: {
        quantity: { type: 'string' },
        angleValue: { type: 'string' },
        adversaryValue: { type: 'string' },
        ratio: { type: 'number', description: 'larger over smaller' },
        suspect: { type: 'string', enum: ['angle', 'adversary', 'both', 'neither'] },
        why: { type: 'string', description: 'name the unit slip or the differing assumption' },
      },
    } },
    verdict: { type: 'string', enum: ['CLEAN', 'CHECK', 'BROKEN'] },
  },
}

// ---- shared standard --------------------------------------------------------

const STANDARD = `
RULES YOU INHERIT FROM THE SKILL

1. Do the arithmetic in Python, in SI, carrying units explicitly through every
   line. Do not do it in your head. Print intermediate values with their units.
2. Two significant figures is the ceiling. Never report four significant figures
   derived from an input you guessed.
3. Estimate every load-bearing number two INDEPENDENT ways and say whether they
   agree. Independent means the routes do not share assumptions: per-capita
   consumption and industry production totals are independent; two slightly
   different per-capita figures are the same route twice.
4. Compare every load-bearing number against a magnitude a reader already has a
   feel for - a person is about 100 watts, sea-level air is about 1.2 kg per
   cubic metre, the atmosphere is about 10 tonnes per square metre. The one real
   error in this skill's history was a factor of a thousand that survived
   because nothing was compared against anything.
5. NEVER NAME WHAT YOU CANNOT POINT TO. Statutes, products, facilities, papers,
   institutions, people, incidents, figures. If you could not open a page about
   it, it goes in candidates with url "" and it will be checked, not printed. An
   escalation ladder missing a rung gets shorter; it does not get an invented
   rung. Do not invent URLs, titles, dates or numbers.
6. Where you cannot source a quantity, say so and bound it. "I could not find a
   reliable figure, so the range is between X and Y and I have taken Z" is a
   legitimate result. A precise-looking number with no provenance is not.

SOURCES, best first: standards bodies and physical-constant tables; government
and agency datasets; peer-reviewed papers; manufacturer datasheets and technical
manuals; textbooks; reputable technical journalism; forum and practitioner
reports only for things nobody else measures. Skip SEO pages, content mills and
AI-written explainers entirely.

TOOLS: search the web. Prefer Exa MCP search tools if ToolSearch finds them,
otherwise WebSearch and WebFetch. Open the source; do not rely on the snippet.

You are producing working material, not prose. Return data. Nobody reads your
sentences for style.
`

function angleBrief(a) {
  return [
    'You are one of several agents computing ONE physical regime of a What If?-style question.',
    `\nQUESTION (verbatim):\n${question}`,
    granted ? `\nONE IMPOSSIBILITY HAS BEEN GRANTED, and only this one: ${granted}. Everything downstream of it obeys physics.` : '',
    `\nYOUR REGIME:\n${a.name} - lens: ${a.lens}`,
    a.brief ? `\nWHAT THE PARENT WANTS FROM YOU:\n${a.brief}` : '',
    STANDARD,
    `\nStay inside your regime. Another agent has the others. If your regime turns out to be irrelevant to this question, say so in gaps rather than inventing work for yourself.`,
  ].filter(Boolean).join('\n')
}

// ---- phase 1: regimes, plus a cold recompute --------------------------------
// The adversary runs in the same wave deliberately. It must not see the angle
// agents' work, or it stops being an independent check and becomes a reviewer.

phase('Angles')

const wave = await parallel([
  ...ANGLES.map(a => () => agent(angleBrief(a), {
    label: `angle:${a.name}`, phase: 'Angles', schema: ANGLE_SCHEMA,
  })),
  () => agent([
    'You are a numbers adversary. You have the question and nothing else.',
    `\nQUESTION (verbatim):\n${question}`,
    granted ? `\nGRANTED IMPOSSIBILITY: ${granted}` : '',
    '\nWork out, from scratch and in Python, every quantity you think this question turns on. Do not look for anyone else\'s answer to it. Show the working for each so a disagreement can be traced to the line that caused it. Other agents are computing the same question and your value will be compared against theirs; the point of you is to be independent, not to be right by agreement.',
    STANDARD,
  ].filter(Boolean).join('\n'), {
    label: 'adversary:cold-recompute', phase: 'Angles', schema: ADVERSARY_SCHEMA,
  }),
])

const angleResults = wave.slice(0, ANGLES.length).filter(Boolean)
const adversary = wave[ANGLES.length] || { quantities: [], assumptions: [] }

if (angleResults.length < ANGLES.length) {
  log(`${ANGLES.length - angleResults.length} angle agent(s) returned nothing; continuing without them`)
}

// Dedupe candidate names across regimes. This barrier is real: the verifier has
// to see the whole set at once or it checks the same statute four times.
const seen = {}
const candidates = []
for (const r of angleResults) {
  for (const c of (r.candidates || [])) {
    const key = (c.name || '').trim().toLowerCase()
    if (!key || seen[key]) continue
    seen[key] = true
    candidates.push(c)
  }
}
log(`${angleResults.length} regimes, ${candidates.length} distinct names to verify`)

// ---- phase 2: verify the names, reconcile the numbers -----------------------

phase('Verify')

const [verify, reconcile] = await parallel([
  () => candidates.length ? agent([
    'You are verifying the named things a What If?-style answer wants to print.',
    'For each candidate below, search for it and decide:',
    '  VERIFIED   - it exists, the claim about it is right, and you have the URL and title of a page that says so.',
    '  UNVERIFIED - you could not confirm it. Say what you tried.',
    '  WRONG      - it does not exist, or the claim about it is false. Say what the truth is.',
    '',
    'Be strict. A plausible-sounding fake reference is a joke when a human writes it and a hallucination when a model does, and the reader cannot tell which they are looking at. If the URL you were given does not say what it was claimed to say, that is WRONG, not VERIFIED.',
    'Never invent a URL or a title. If you have no URL, the row is UNVERIFIED.',
    '',
    `QUESTION FOR CONTEXT:\n${question}`,
    `\nCANDIDATES:\n${JSON.stringify(candidates, null, 1).slice(0, 60000)}`,
  ].join('\n'), { label: 'verify:names', phase: 'Verify', schema: VERIFY_SCHEMA })
    : Promise.resolve({ rows: [] }),

  () => agent([
    'You are reconciling two independent estimates of the same quantities.',
    'Set A came from agents that each researched one physical regime. Set B came from an agent that recomputed the question cold, having seen nothing but the question.',
    '',
    'Match quantities that are the same thing under different names. For each match, compute the ratio of the larger to the smaller. Report every pair disagreeing by more than 2x. For each, say which side looks wrong and name the specific cause - a unit slip, a different assumed size, a different definition of the quantity. Do not report a disagreement you cannot explain; say the cause is unclear instead.',
    '',
    'Verdict: CLEAN if nothing disagrees by more than 2x. CHECK if something does but the cause is a defensible difference in assumptions. BROKEN if any disagreement looks like a unit error - those are the ones that produce a confident answer wrong by a factor of a thousand.',
    '',
    `SET A (regimes):\n${JSON.stringify(angleResults.map(r => ({ angle: r.angle, quantities: r.quantities })), null, 1).slice(0, 60000)}`,
    `\nSET B (cold recompute):\n${JSON.stringify(adversary, null, 1).slice(0, 20000)}`,
  ].join('\n'), { label: 'reconcile:numbers', phase: 'Verify', schema: RECONCILE_SCHEMA }),
])

const rows = (verify && verify.rows) || []
const okCount = rows.filter(r => r.status === 'VERIFIED').length
log(`verified ${okCount}/${rows.length} names; numbers verdict ${(reconcile && reconcile.verdict) || 'UNKNOWN'}`)

return {
  question,
  granted: granted || '',
  angles: angleResults,
  adversary,
  verify: { rows },
  reconcile: reconcile || { disagreements: [], verdict: 'UNKNOWN' },
  summary: {
    regimes: angleResults.length,
    namesChecked: rows.length,
    namesVerified: okCount,
    numbersVerdict: (reconcile && reconcile.verdict) || 'UNKNOWN',
  },
}
