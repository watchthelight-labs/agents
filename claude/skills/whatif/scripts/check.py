#!/usr/bin/env python3
"""
Mechanical audit for a What If?-form draft.

Usage:  python check.py draft.md [--deep] [--claims claims.tsv]

Reports objective, countable properties only. It does not judge whether the
writing is good, whether the joke lands, or whether the physics is right.
Those are your job. This catches the things that drift silently: length
inflation across a session, formatting contracts breaking, exclamation marks
creeping in, false precision in numbers.

Corpus reference values come from a scripted pass over all 162 What If? web
articles (2012-07-10 through 2022-12-06), measured on body prose only.

--deep switches to the deep-mode band set. Only the counts that legitimately
scale with length move: words, drawings, footnotes, breaks. Everything already
expressed per thousand words is unchanged, and so are the opener, closer,
fragment-run and anaphora thresholds — a longer answer is not licence for a
longer ending.

--claims cross-references the proper nouns in the body against a deep-mode
claims ledger and reports any that are not listed as VERIFIED. It checks names
only; numbers are the PRECISION row's job.
"""

import argparse
import re
import statistics
import sys
from pathlib import Path

# ---- corpus reference values (measured, not invented) -----------------------
BODY_LO, BODY_HI = 550, 850          # p25-p75 = 534-845, median 680
BODY_FLOOR, BODY_CEIL = 400, 1300    # hard outer band
OPENER_MEDIAN = 10                   # median first sentence, body mean 18.9
CLOSER_MEDIAN = 11                   # median last sentence
EXCLAM_PER_1K = 0.65                 # ~1 per 1,540 words
EMDASH_PER_1K = 7.59
SEMICOLON_PER_1K = 1.45              # em dash outruns it ~5:1
DRAWINGS_LO, DRAWINGS_HI = 2, 3      # every article has >=2; ~1 per 130 words
FOOTNOTES_LO, FOOTNOTES_HI = 4, 6    # post-#51 median 5

# ---- deep-mode bands (chosen, not measured) ---------------------------------
# The archive has no deep mode, so these are a design decision rather than a
# measurement, and they are labelled that way on purpose. Drawings and footnotes
# hold roughly the archive's per-word density across the longer band; breaks
# give three to six movements.
DEEP_BODY_LO, DEEP_BODY_HI = 1400, 2600
DEEP_BODY_FLOOR, DEEP_BODY_CEIL = 1100, 3200
DEEP_DRAWINGS_LO, DEEP_DRAWINGS_HI = 4, 7
DEEP_FOOTNOTES_LO, DEEP_FOOTNOTES_HI = 6, 12
DEEP_BREAKS_LO, DEEP_BREAKS_HI = 2, 5      # movements = breaks + 1

# ---- prose-variance floors (exemplar-derived, not corpus-derived) -----------
# Measured over the three worked answers in examples/ plus two fresh drafts:
# sentence sd 8.27-11.13, paragraph sd 25.67-35.49, and no two-word sentence
# opener repeating more than twice in any of the five. The floors sit below the
# lowest observed value, so they catch flattening rather than policing rhythm.
# Low variance is the failure; high variance is not.
SENT_SD_FLOOR = 7.0
PARA_SD_FLOOR = 20.0
OPENER_REPEAT_MAX = 4                # absolute count of the same two-word start
OPENER_REPEAT_RATE = 5.0             # per 1k words, for long drafts

INTENSIFIERS = [
    "incredibly", "insanely", "utterly", "absolutely", "unbelievably",
    "extremely", "massively", "ridiculously", "wildly", "immensely",
    "tremendously", "enormously", "staggeringly", "mind-blowing",
    "mind-boggling", "literally exploded",
]

FORMAL_HEDGES = ["approximately", "on the order of", "it is worth noting",
                 "it should be noted", "in essence", "fundamentally"]

# ---- slop patterns ----------------------------------------------------------
# Deltas from the generic anti-AI-writing catalogue, adjudicated against the
# archive in references/slop.md. Several of these have a corpus-attested form
# that must survive, so the notes say what the legitimate version looks like.
# A flag here is a prompt to look, not an instruction to delete.

RE_REFRAME = re.compile(
    r"\b\w+ (?:isn'?t|is not|aren'?t|are not|wasn'?t)\b[^.?!]{0,60}[.!]\s*"
    r"(?:It'?s|That'?s|They'?re|The \w+ is)\b", re.I)
RE_SNAP = re.compile(
    r"[.!?]\s+(?:The|Your|Their|His|Her|Its) [a-z][\w' ]{0,22}\?\s+"
    r"[A-Z][^.?!]{0,28}[.!]")
RE_TRICOLON = re.compile(r"\b\w+, \w+, and \w+\b")

# These four run at or near zero across the archive; any hit is worth a look.
SLOP_PHRASES = [
    ("tack-on", r",\s+(?:highlighting|underscoring|showcasing|reflecting|"
                r"emphasizing|demonstrating|illustrating|contributing to)\b"),
    ("vague attribution", r"\b(?:experts?\s+(?:say|argue|believe|agree)|"
                          r"observers have|industry reports?|several publications|"
                          r"some critics|studies suggest)\b"),
    ("ornate noun", r"\b(?:tapestry|paradigm|synergy|ecosystem|holistic|"
                    r"multifaceted)\b"),
    ("filler opener", r"\b(?:here'?s (?:the kicker|where it gets|what most)|"
                      r"think of it (?:as|like)|the (?:real|simple) "
                      r"(?:story|truth) is)\b"),
]

# ---- claims ledger ----------------------------------------------------------
# Capitalised words that carry no claim about the world and never need a ledger
# row. Everything else the body capitalises mid-sentence is a name, and Rule 2
# says a name has to be pointable.
LEDGER_ALLOW = {
    "i", "i'd", "i'm", "i've", "i'll", "earth", "moon", "sun", "mars",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "mach",
    "celsius", "fahrenheit", "kelvin", "what", "if", "god", "english",
    "btu", "mbtu", "roman", "metric",
}

RE_BREAK = re.compile(r"^\[break\]\s*$", re.I)      # duplicated in render.py
RE_CAPS = re.compile(r"\b[A-Z][A-Za-z'’]*(?:\s+(?:of|the|de|van|von)\s+)?"
                     r"(?:\s[A-Z][A-Za-z'’]*)*")


def split_sections(text):
    """Separate question header, body prose, drawing captions, footnotes, breaks.

    These marker regexes are duplicated verbatim in render.py. If the draft
    format changes, both files change together or the two scripts will disagree
    about what counts as prose.
    """
    question, body, drawings, footnotes = [], [], [], []
    breaks = 0

    # Footnote block: trailing lines like "[1] text" or "^1 text"
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            body.append(lines[i])
            i += 1
            continue
        if s.startswith(">"):                       # quoted question / attribution
            question.append(s.lstrip("> ").strip())
        elif re.match(r"^\[drawing:", s, re.I):     # illustration caption
            # A caption may be wrapped across lines. Swallow to the closing
            # bracket, or the tail of it lands in the body and drags the
            # sentence splitter with it.
            cap = [s]
            while not cap[-1].rstrip().endswith("]") and i + 1 < len(lines):
                i += 1
                cap.append(lines[i].strip())
            drawings.append(" ".join(cap))
        elif RE_BREAK.match(s):                     # movement break
            breaks += 1
            body.append("")                         # still a paragraph boundary
        elif re.match(r"^\[\^?\d+\]\s+\S", s) or re.match(r"^\^\d+\s+\S", s):
            # Same for a wrapped footnote: its continuation lines are not body
            # prose and must not be counted as such.
            note = [s]
            while i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if not nxt or re.match(r"^\[", nxt) or re.match(r"^\^\d", nxt):
                    break
                i += 1
                note.append(nxt)
            footnotes.append(" ".join(note))
        elif re.fullmatch(r"-{3,}|\*{3,}|_{3,}", s):  # horizontal rule
            pass
        else:
            body.append(lines[i])
        i += 1

    return "\n".join(question), "\n".join(body), drawings, footnotes, breaks


def strip_markers(s):
    """Remove inline footnote markers so they don't break sentence splitting."""
    return re.sub(r"\[\^?\d+\]", "", s)


def words(s):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", s)


def sentences(s):
    s = re.sub(r"\s+", " ", strip_markers(s)).strip()
    if not s:
        return []
    # crude: split on terminal punctuation followed by space + capital/quote/digit
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“\'])', s)
    return [p.strip() for p in parts if p.strip()]


def sig_figs(token):
    """Count significant figures. 0.067 -> 2, 1500 -> 2, 3766.4 -> 5."""
    t = token.replace(",", "").lstrip("+-")
    if "." in t:
        intpart, frac = t.split(".", 1)
        digits = (intpart + frac).lstrip("0")
    else:
        digits = t.strip("0") or "0"
    return len(digits)


def spread(lengths):
    """Population sd of a list of word counts, 0.0 when there is nothing to
    vary. Sample sd would punish short drafts for having few paragraphs."""
    return statistics.pstdev(lengths) if len(lengths) > 1 else 0.0


def top_opener(sents):
    """Most-repeated two-word sentence opening, as (phrase, count).

    ANAPHORA already catches three in a row inside one paragraph. This catches
    the same start scattered across a long answer, which is what the drumbeat
    actually looks like past a couple of thousand words.
    """
    keys = [" ".join(words(s)[:2]).lower() for s in sents]
    keys = [k for k in keys if k]
    if not keys:
        return "", 0
    best = max(set(keys), key=keys.count)
    return best, keys.count(best)


def read_ledger(path):
    """Read a claims ledger. Returns (verified, seen) as lowercased name sets.

    Format is tab-separated: status, name, url, title, note. Lines starting
    with # and a header row naming the first column 'status' are skipped.
    """
    verified, seen = set(), set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = [c.strip() for c in line.split("\t")]
        if len(cells) < 2 or cells[0].lower() == "status":
            continue
        name = cells[1].lower()
        seen.add(name)
        if cells[0].upper() == "VERIFIED":
            verified.add(name)
    return verified, seen


def named_things(sents):
    """Capitalised phrases that are not merely sentence-initial.

    Walks tokens rather than matching a phrase regex, because the interesting
    case is "The Minamata Convention on Mercury" — a real name wearing a
    sentence-initial article. Dropping the whole match on a leading capital
    would lose exactly the names worth checking. Deliberately crude otherwise:
    it over-reports, and the report says to look rather than to delete.
    """
    # "and" is not a connector here. It joins two names far less often than it
    # produces "Class and Type", and the false positive is the common case.
    connectors = {"of", "the", "de", "van", "von", "for", "on"}
    found = []
    for s in sents:
        toks = re.findall(r"[A-Za-z][A-Za-z'’]*|\d[\d,]*", s)
        run, runs = [], []
        for i, t in enumerate(toks):
            if t[0].isupper():
                run.append((i, t))
            elif t[0].isdigit() and run:
                # a number attached to a name is part of it: NFPA 110, Class 96
                run.append((i, t))
            elif run and t.lower() in connectors and i + 1 < len(toks) \
                    and toks[i + 1][:1].isupper():
                run.append((i, t))
            else:
                if run:
                    runs.append(run)
                run = []
        if run:
            runs.append(run)

        for r in runs:
            if r[0][0] == 0 and not r[0][1][0].isdigit():   # started the sentence
                r = r[1:]
            while r and r[-1][1].lower() in connectors:
                r = r[:-1]
            if not r or all(t[0].isdigit() for _, t in r):
                continue
            phrase = " ".join(t for _, t in r)
            if phrase.lower() in LEDGER_ALLOW or len(phrase) < 3:
                continue
            found.append(phrase)
    return found


def status(value, lo, hi, low_label="LOW", high_label="HIGH"):
    if value < lo:
        return low_label
    if value > hi:
        return high_label
    return "OK"


def row(label, value, note, verdict):
    return f"{label:<14}{value:<10}{note:<38}{verdict}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--deep", action="store_true",
                    help="use the deep-mode band set")
    ap.add_argument("--claims", metavar="TSV",
                    help="claims ledger to check named things against")
    args = ap.parse_args()

    path = Path(args.draft)
    if not path.exists():
        print(f"no such file: {path}")
        return 2

    deep = args.deep
    body_lo, body_hi = (DEEP_BODY_LO, DEEP_BODY_HI) if deep else (BODY_LO, BODY_HI)
    body_floor, body_ceil = ((DEEP_BODY_FLOOR, DEEP_BODY_CEIL) if deep
                             else (BODY_FLOOR, BODY_CEIL))
    draw_lo, draw_hi = ((DEEP_DRAWINGS_LO, DEEP_DRAWINGS_HI) if deep
                        else (DRAWINGS_LO, DRAWINGS_HI))
    note_lo, note_hi = ((DEEP_FOOTNOTES_LO, DEEP_FOOTNOTES_HI) if deep
                        else (FOOTNOTES_LO, FOOTNOTES_HI))
    break_lo, break_hi = (DEEP_BREAKS_LO, DEEP_BREAKS_HI) if deep else (0, 0)

    text = path.read_text(encoding="utf-8")
    question, body, drawings, footnotes, breaks = split_sections(text)

    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    prose = " ".join(paras)
    wc = len(words(prose))
    per_1k = (lambda n: (n * 1000.0 / wc) if wc else 0.0)

    sents = sentences(prose)
    opener = len(words(sents[0])) if sents else 0
    # closer = final paragraph, which is what a reader experiences as the
    # closing line (corpus median 12 words). Last *sentence* is often a
    # three-word fragment and reads as noise.
    closer = len(words(strip_markers(paras[-1]))) if paras else 0

    headings = len([l for l in body.splitlines() if re.match(r"^#{1,6}\s", l)])
    bullets = len([l for l in body.splitlines()
                   if re.match(r"^\s*([-*+]\s+|\d+[.)]\s+)", l)])
    tables = len([l for l in body.splitlines() if l.count("|") >= 2])

    exclam = prose.count("!")
    emdash = prose.count("—") + len(re.findall(r"(?<!-)--(?!-)", prose))
    semis = prose.count(";")

    found_int = [w for w in INTENSIFIERS if re.search(rf"\b{re.escape(w)}\b",
                                                      prose, re.I)]
    found_formal = [w for w in FORMAL_HEDGES if re.search(rf"\b{re.escape(w)}\b",
                                                          prose, re.I)]

    # false precision: any number carrying 4+ significant figures.
    # 0.067 is two sig figs and fine; 3766.4 is five and is not.
    precise = [n for n in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", prose)
               if sig_figs(n) >= 4 and not re.fullmatch(r"(19|20)\d\d", n)]

    about = len(re.findall(r"\babout\b", prose, re.I))
    approx = len(re.findall(r"\bapproximately\b", prose, re.I))

    # ---- slop ----
    reframes = len(RE_REFRAME.findall(prose))
    snaps = len(RE_SNAP.findall(prose))
    tricolons = len(RE_TRICOLON.findall(prose))
    tri_sents = [i for i, s in enumerate(sents) if RE_TRICOLON.search(s)]
    tri_adjacent = sum(1 for i in range(len(tri_sents) - 1)
                       if tri_sents[i + 1] - tri_sents[i] == 1)

    # longest run of consecutive short paragraphs. One beat is the device;
    # the archive contains a run of three exactly twice in 162 articles.
    frag_run, run = 0, 0
    for p in paras:
        if len(words(strip_markers(p))) <= 6:
            run += 1
            frag_run = max(frag_run, run)
        else:
            run = 0

    # same two-word sentence opener three times running inside a paragraph
    anaphora = 0
    for p in paras:
        ss = sentences(p)
        keys = [" ".join(words(s)[:2]).lower() for s in ss]
        for i in range(len(keys) - 2):
            if keys[i] and keys[i] == keys[i + 1] == keys[i + 2]:
                anaphora += 1

    slop_hits = [name for name, pat in SLOP_PHRASES
                 if re.search(pat, prose, re.I)]

    # ---- prose variance ----
    sent_sd = spread([len(words(s)) for s in sents])
    para_sd = spread([len(words(strip_markers(p))) for p in paras])
    open_word, open_n = top_opener(sents)

    # ---- claims ledger ----
    unlisted, unverified = [], []
    if args.claims:
        try:
            verified, seen = read_ledger(args.claims)
        except OSError as exc:
            print(f"claims ledger unreadable: {exc}", file=sys.stderr)
            verified, seen = set(), set()
        # Footnotes are where citations live, so they are in scope. Drawing
        # captions are not: a hand-lettered sign in a panel is a joke, not a
        # claim about the world.
        note_sents = sentences(" ".join(strip_markers(f) for f in footnotes))
        def listed(phrase, names):
            # Singularised substring either way, so "Maracaibos" matches the
            # row for "Lake Maracaibo" instead of reading as a new name.
            low = phrase.lower().rstrip("s") or phrase.lower()
            return any(low in n or n.rstrip("s") in low for n in names)

        for phrase in dict.fromkeys(named_things(sents + note_sents)):
            if listed(phrase, verified):
                continue
            if listed(phrase, seen):
                unverified.append(phrase)
            else:
                unlisted.append(phrase)

    out = []
    label = "deep" if deep else "standard"
    out.append(f"--- {path.name} [{label}] "
               + "-" * max(0, 58 - len(path.name) - len(label) - 3))
    if question:
        out.append(f"question:     {question.splitlines()[0][:60]}")
    out.append("")
    if wc < body_floor:
        wc_verdict = "TOO SHORT"
    elif wc > body_ceil:
        wc_verdict = "TOO LONG"
    elif wc < body_lo:
        wc_verdict = "SHORT"
    elif wc > body_hi:
        wc_verdict = "LONG"
    else:
        wc_verdict = "OK"
    out.append(row("WORDS", wc, f"target {body_lo}-{body_hi}", wc_verdict))
    out.append(row("OPENER", opener, f"median {OPENER_MEDIAN}, vary it",
                   "LONG" if opener > 25 else "OK"))
    out.append(row("CLOSER", closer, f"last para, median {CLOSER_MEDIAN}",
                   "LONG" if closer > 30 else "OK"))
    out.append(row("PARAGRAPHS", len(paras),
                   f"~{wc // max(1, len(paras))} words each", "OK"))
    out.append(row("STRUCTURE",
                   f"h{headings}/b{bullets}/t{tables}",
                   "headings/bullets/tables",
                   "FLAG" if (headings or bullets or tables) else "OK"))
    out.append(row("EXCLAM", exclam,
                   f"{per_1k(exclam):.1f}/1k vs corpus {EXCLAM_PER_1K}",
                   "HIGH" if per_1k(exclam) > 1.5 else "OK"))
    out.append(row("EM-DASH", emdash,
                   f"{per_1k(emdash):.1f}/1k vs corpus {EMDASH_PER_1K}",
                   status(per_1k(emdash), 2.0, 14.0)))
    out.append(row("SEMICOLON", semis,
                   f"{per_1k(semis):.1f}/1k vs corpus {SEMICOLON_PER_1K}",
                   "HIGH" if per_1k(semis) > 3.5 else "OK"))
    out.append(row("DRAWINGS", len(drawings),
                   f"expect {draw_lo}-{draw_hi}",
                   status(len(drawings), draw_lo, draw_hi)))
    out.append(row("FOOTNOTES", len(footnotes),
                   f"expect {note_lo}-{note_hi}",
                   status(len(footnotes), note_lo, note_hi)))
    if deep:
        out.append(row("BREAKS", breaks,
                       f"movements {breaks + 1}, expect {break_lo + 1}-"
                       f"{break_hi + 1}",
                       status(breaks, break_lo, break_hi)))
    elif breaks:
        out.append(row("BREAKS", breaks, "standard mode has no movements",
                       "FLAG"))
    out.append(row("ABOUT/APPROX", f"{about}/{approx}",
                   "prefer 'about'", "FLAG" if approx else "OK"))

    if found_int:
        out.append(row("INTENSIFIERS", len(found_int),
                       ", ".join(found_int)[:36], "FLAG"))
    else:
        out.append(row("INTENSIFIERS", 0, "none", "OK"))

    if found_formal:
        out.append(row("FORMAL", len(found_formal),
                       ", ".join(found_formal)[:36], "FLAG"))

    if precise:
        out.append(row("PRECISION", len(precise),
                       "4+ sig figs: " + ", ".join(precise[:3]), "FLAG"))
    else:
        out.append(row("PRECISION", 0, "no false precision", "OK"))

    out.append("")
    out.append(row("REFRAME", reframes, "ok if it corrects a fact",
                   "FLAG" if reframes > 1 else "OK"))
    out.append(row("SNAP Q&A", snaps, "pose it, answer in a sentence",
                   "FLAG" if snaps else "OK"))
    out.append(row("FRAG RUN", frag_run, "1 beat is the device, 3 is cadence",
                   "FLAG" if frag_run >= 3 else "OK"))
    out.append(row("TRICOLON", f"{tricolons}/{tri_adjacent}",
                   f"{per_1k(tricolons):.1f}/1k vs corpus 0.6, adjacent",
                   "HIGH" if per_1k(tricolons) > 2.0 or tri_adjacent else "OK"))
    out.append(row("ANAPHORA", anaphora, "chained hand-off is not this",
                   "FLAG" if anaphora else "OK"))
    out.append(row("SLOP", len(slop_hits),
                   ", ".join(slop_hits)[:36] if slop_hits else "none",
                   "FLAG" if slop_hits else "OK"))
    out.append(row("SENT VAR", f"{sent_sd:.1f}",
                   f"sd of sentence words, floor {SENT_SD_FLOOR}",
                   "LOW" if sent_sd < SENT_SD_FLOOR else "OK"))
    out.append(row("PARA VAR", f"{para_sd:.1f}",
                   f"sd of paragraph words, floor {PARA_SD_FLOOR}",
                   "LOW" if para_sd < PARA_SD_FLOOR else "OK"))
    out.append(row("OPENER REPEAT", f"{open_n}x",
                   f"'{open_word}' {per_1k(open_n):.1f}/1k"[:36],
                   "HIGH" if (open_n >= OPENER_REPEAT_MAX
                              or per_1k(open_n) > OPENER_REPEAT_RATE)
                   else "OK"))

    if args.claims:
        out.append("")
        out.append(row("LEDGER", f"{len(unlisted)}/{len(unverified)}",
                       "unlisted / listed-but-unverified",
                       "FLAG" if (unlisted or unverified) else "OK"))
        for phrase in unlisted[:8]:
            out.append(f"  unlisted     {phrase}")
        for phrase in unverified[:8]:
            out.append(f"  unverified   {phrase}")

    out.append("")
    flags = [l for l in out
             if l.rstrip().endswith(("FLAG", "HIGH", "LOW", "LONG", "SHORT"))]
    out.append(f"{len(flags)} item(s) to look at."
               if flags else "Nothing flagged.")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
