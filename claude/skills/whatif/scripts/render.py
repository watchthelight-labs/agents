#!/usr/bin/env python3
"""
Lay a What If?-form draft out as a book page and print it to PDF.

Usage:  python render.py draft.md [--outdir DIR] [--no-open] [--keep-html]

Builds a single-column 6.5x9.5in page from the draft, renders it with headless
Chrome, writes the PDF to ~/Documents/whatif/ and opens it in Chrome.

Drawing captions become empty framed panels with the caption inside. Nothing is
illustrated; the panel is an honest placeholder for a cartoon that does not
exist.

The marker regexes below are deliberately identical to the ones in check.py, so
the two scripts never disagree about what counts as a drawing or a footnote.
check.py's own splitter is not reused: it discards block order, and the page
needs paragraphs and panels interleaved.
"""

import argparse
import base64
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT = ASSETS / "xkcd-script.ttf"
PAGED = ASSETS / "paged.polyfill.js"
HAND = '"xkcd Script", "Segoe Print", "Comic Sans MS", cursive'

# These marker regexes are duplicated verbatim in check.py. If the draft format
# changes, both files change together or the two scripts will disagree about
# what counts as prose.
RE_DRAWING = re.compile(r"^\[drawing:", re.I)
RE_BREAK = re.compile(r"^\[break\]\s*$", re.I)
RE_FOOTNOTE = re.compile(r"^\[\^?(\d+)\]\s+(\S.*)$")
RE_FOOTNOTE_ALT = re.compile(r"^\^(\d+)\s+(\S.*)$")
RE_RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
RE_MARKER = re.compile(r"\[\^?(\d+)\]")

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", ""))
PROGRAMFILES = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
PROGRAMFILES_X86 = Path(
    os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
)

# For opening the finished PDF. An installed Chrome hands the URL to whatever
# session is already running, which is exactly what we want here.
CHROME_CANDIDATES = [
    PROGRAMFILES / "Google/Chrome/Application/chrome.exe",
    PROGRAMFILES_X86 / "Google/Chrome/Application/chrome.exe",
    LOCALAPPDATA / "Google/Chrome/Application/chrome.exe",
]

# For rendering. Installed Chrome is last because that same hand-off makes it
# useless for --print-to-pdf: it forwards the flags to the running session,
# exits 0, and writes nothing. Playwright's headless shell has no singleton and
# renders reliably, so it goes first when present.
RENDERER_GLOBS = [
    (LOCALAPPDATA / "ms-playwright",
     "chromium_headless_shell-*/chrome-headless-shell-win64/"
     "chrome-headless-shell.exe", []),
    (LOCALAPPDATA / "ms-playwright",
     "chromium-*/chrome-win/chrome.exe", ["--headless=new"]),
]
RENDERER_FIXED = [
    (PROGRAMFILES / "Google/Chrome/Application/chrome.exe", ["--headless=new"]),
    (PROGRAMFILES_X86 / "Microsoft/Edge/Application/msedge.exe",
     ["--headless=new"]),
    (PROGRAMFILES / "Microsoft/Edge/Application/msedge.exe", ["--headless=new"]),
]


# ---- parsing ----------------------------------------------------------------

def parse(text):
    """Return (question, attribution, blocks, footnotes).

    blocks is an ordered list of ("para", str), ("drawing", str) and
    ("break", ""). footnotes is an ordered list of (number, text).
    """
    question, attribution = "", ""
    blocks, footnotes, buf = [], [], []

    def flush():
        if buf:
            blocks.append(("para", " ".join(buf).strip()))
            buf.clear()


    # Indexed rather than a plain for-loop because captions and footnotes may be
    # wrapped across lines, and the continuation has to be swallowed with the
    # block it belongs to. Left in the body it becomes a stray paragraph.
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()

        if not s:
            flush()
            i += 1
            continue

        if s.startswith(">"):
            flush()
            q = s.lstrip("> ").strip()
            if not q:
                i += 1
                continue
            if q.startswith(("—", "–", "--", "-")) or q.lower().startswith("by "):
                attribution = q.lstrip("-–— ").strip()
            elif not question:
                question = q
            else:
                question += " " + q
            i += 1
            continue

        if RE_DRAWING.match(s):
            flush()
            cap = [s]
            while not cap[-1].rstrip().endswith("]") and i + 1 < len(lines):
                i += 1
                cap.append(lines[i].strip())
            joined = " ".join(cap)
            blocks.append(("drawing", joined.strip("[]").split(":", 1)[1].strip()))
            i += 1
            continue

        if RE_BREAK.match(s):
            flush()
            blocks.append(("break", ""))
            i += 1
            continue

        m = RE_FOOTNOTE.match(s) or RE_FOOTNOTE_ALT.match(s)
        if m:
            flush()
            body = [m.group(2).strip()]
            while i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if not nxt or nxt.startswith("[") or re.match(r"^\^\d", nxt):
                    break
                i += 1
                body.append(nxt)
            footnotes.append((m.group(1), " ".join(body)))
            i += 1
            continue

        if RE_RULE.match(s):
            flush()
            i += 1
            continue

        buf.append(s)
        i += 1

    flush()
    return question, attribution or "Anonymous", blocks, footnotes


def smart(s):
    """Typeset the punctuation. Drafts stay plain ASCII for the author's
    convenience; the page is where quotes get their curl."""
    s = s.replace("---", "\u2014").replace("--", "\u2014")
    s = s.replace("...", "\u2026")
    s = re.sub(r'(^|[\s(\[\u2014])"', "\\1\u201c", s)
    s = s.replace('"', "\u201d")
    s = re.sub(r"(?<=[A-Za-z0-9])'(?=[A-Za-z])", "\u2019", s)
    s = re.sub(r"(?<=[A-Za-z])'(?=\s|$|[.,;:!?)])", "\u2019", s)
    s = re.sub(r"(^|\s)'(?=\d\ds\b)", "\\1\u2019", s)
    return s


def inline(s, notes=None):
    """Escape and typeset, then resolve [n] markers.

    With `notes`, each marker becomes the footnote body inline at the reference
    point, which is what Paged.js needs to float it to the foot of the page it
    lands on. Without, it becomes a superscript link to the endnote block.
    """
    out = html.escape(smart(s))

    def sub(m):
        n = m.group(1)
        if notes and n in notes:
            return (f'<span class="fn" id="fn-{n}">'
                    f'{html.escape(smart(notes[n]))}</span>')
        return f'<sup><a href="#fn-{n}">{n}</a></sup>'

    return RE_MARKER.sub(sub, out)


def slugify(s, limit=60):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if len(s) > limit:
        s = s[:limit].rsplit("-", 1)[0]
    return s or "answer"


# ---- page -------------------------------------------------------------------

CSS = """
@page {
  size: 6.5in 9.5in;
  margin: 0.82in 0.75in 0.86in;
  @top-center {
    content: "What If?";
    font: 7.5pt HANDFONT; letter-spacing: 0.26em;
    text-transform: uppercase; color: #8a827a;
    margin-bottom: 0.16in;
  }
  @bottom-center {
    content: counter(page);
    font: 8.5pt Georgia, serif; color: #56514a;
    margin-top: 0.20in;
  }
}

/* The opening page is a chapter opener: it carries the mark in the text block
   and wants neither running head nor folio. */
@page :first {
  @top-center { content: none; }
  @bottom-center { content: none; }
}

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font: 10.5pt/1.62 Georgia, "Times New Roman", serif;
  color: #14120f;
  margin: 0;
  text-align: justify;
  -webkit-hyphens: auto; hyphens: auto;
  orphans: 2; widows: 2;
}

.head {
  font-family: HANDFONT;
  font-size: 8.5pt;
  letter-spacing: 0.30em;
  text-transform: uppercase;
  text-align: center;
  color: #8a827a;
  margin: 0 0 0.34in;
}

.q {
  font-size: 15pt;
  line-height: 1.32;
  font-style: italic;
  text-align: left;
  -webkit-hyphens: none; hyphens: none;
  margin: 0 0 0.10in;
}

.by {
  text-align: right;
  font-style: normal;
  font-size: 8pt;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #56514a;
  margin: 0;
}

.rule {
  border: 0;
  border-top: 0.7pt solid #14120f;
  margin: 0.13in 0 0.24in;
}

p.b { margin: 0; text-indent: 1.45em; }
p.b.first { text-indent: 0; }

.panel {
  border: 1.1pt solid #14120f;
  padding: 12pt 16pt 15pt;
  margin: 17pt 0 18pt;
  text-align: center;
  break-inside: avoid; page-break-inside: avoid;
}

.panel .tag {
  font-family: HANDFONT;
  font-size: 7pt;
  line-height: 1;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: #8a827a;
  margin-bottom: 10pt;
}

/* Movement break. A book sets this as an asterism, not a heading — deep-mode
   answers are still one continuous piece of prose with pauses in it. */
.brk {
  text-align: center;
  font-family: HANDFONT;
  font-size: 10pt;
  letter-spacing: 0.85em;
  text-indent: 0.85em;          /* recentre: letter-spacing pads only the right */
  color: #8a827a;
  margin: 20pt 0 19pt;
  break-before: avoid; page-break-before: avoid;
  break-after: avoid; page-break-after: avoid;
  break-inside: avoid; page-break-inside: avoid;
}

.panel .cap {
  font-family: HANDFONT;
  font-size: 10pt;
  line-height: 1.55;
  text-align: center;
  -webkit-hyphens: none; hyphens: none;
}

/* --- footnotes ---------------------------------------------------------- */
/* With Paged.js these float to the foot of whichever page the reference
   lands on. Without it, the same markup is emitted as an endnote block. */

span.fn { float: footnote; }

::footnote-call { font-size: 0.66em; vertical-align: super; line-height: 0; }
::footnote-marker { font-size: 8.2pt; padding-right: 0.35em; }

/* Paged.js draws its own separator as a full-measure border on the footnote
   content box. A book uses a short rule, so that border is turned off and
   replaced with one. These class names are Paged.js internals; they are the
   only handle it offers. */
.pagedjs_footnote_content {
  border-top: 0 !important;
  padding-top: 0 !important;
}
.pagedjs_footnote_content::before {
  content: "";
  display: block;
  width: 1.4in;
  border-top: 0.7pt solid #14120f;
  margin: 9pt 0 5pt;
}
.pagedjs_footnote_area .pagedjs_footnote_content,
span.fn {
  font-size: 8.2pt;
  line-height: 1.42;
  text-align: left;
  -webkit-hyphens: auto; hyphens: auto;
}
/* list-item, not block: Paged.js hangs the footnote number off the list
   marker, and switching the display type silently deletes the number. */
.pagedjs_footnote_inner_content span.fn {
  display: list-item;
  padding-left: 1.15em;
  text-indent: -1.15em;
  margin-bottom: 2.5pt;
}

/* endnote fallback */
.notes { margin-top: 0.30in; }
.notes hr {
  border: 0;
  border-top: 0.7pt solid #14120f;
  width: 1.4in;
  margin: 0 0 0.14in;
}
.notes p {
  font-size: 8.2pt;
  line-height: 1.45;
  text-align: left;
  padding-left: 1.7em;
  text-indent: -1.7em;
  margin: 0 0 0.075in;
  break-inside: avoid; page-break-inside: avoid;
}

sup { font-size: 0.66em; line-height: 0; vertical-align: super; }
sup a { color: inherit; text-decoration: none; }
"""


def font_face():
    """Embed the hand face as a data URI so the PDF carries it and nothing has
    to be installed. Silently skipped if the asset is missing."""
    if not FONT.is_file():
        return ""
    b64 = base64.b64encode(FONT.read_bytes()).decode("ascii")
    return (
        '@font-face { font-family: "xkcd Script"; font-style: normal;'
        ' font-weight: 400; src: url(data:font/ttf;base64,'
        + b64
        + ') format("truetype"); }\n'
    )


def build_html(question, attribution, blocks, footnotes, paged=True):
    parts = ['<p class="head">What If?</p>']
    if question:
        parts.append(f'<p class="q">{inline(question)}</p>')
        parts.append(f'<p class="by">&mdash;&#8202;{html.escape(attribution)}</p>')
        parts.append('<hr class="rule">')

    notes = dict(footnotes) if paged else None
    used = set()
    first = True
    for kind, content in blocks:
        if kind == "para":
            cls = "b first" if first else "b"
            if notes:
                used.update(RE_MARKER.findall(content))
            parts.append(f'<p class="{cls}">{inline(content, notes)}</p>')
            first = False
            continue

        if kind == "break":
            parts.append('<p class="brk">* * *</p>')
            first = True   # a movement opens flush, like a chapter
            continue

        parts.append(
            '<div class="panel"><div class="tag">Drawing</div>'
            f'<div class="cap">{html.escape(smart(content))}</div></div>')
        first = True  # a paragraph after a panel starts flush, as after a break

    # Anything never referenced in the body still has to reach the reader.
    orphans = [(n, b) for n, b in footnotes if not paged or n not in used]
    if orphans:
        parts.append('<div class="notes"><hr>')
        for n, body in orphans:
            parts.append(f'<p id="fn-{n}"><span class="n">[{n}]</span> '
                         f"{inline(body)}</p>")
        parts.append("</div>")

    title = question or "What If?"
    css = font_face() + CSS.replace("HANDFONT", HAND)
    # The beacon is what makes the render deterministic: printing is held until
    # Paged.js says it has finished chunking, rather than guessing with a timer.
    script = ('<script>window.PagedConfig={after:function(){'
              'window.__pagedDone=true;}};</script>\n'
              '<script src="paged.polyfill.js"></script>\n') if paged else ""
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{css}</style></head>\n<body>\n"
        + "\n".join(parts)
        + f"\n{script}</body></html>\n"
    )


# ---- chrome -----------------------------------------------------------------

def find_chrome():
    """Chrome for opening the finished PDF."""
    for p in CHROME_CANDIDATES:
        if p and p.is_file():
            return p
    for name in ("chrome", "chrome.exe", "google-chrome"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def find_renderers():
    """Every browser binary that might render, best first."""
    out = []
    for root, pattern, flags in RENDERER_GLOBS:
        if root.is_dir():
            for p in sorted(root.glob(pattern), reverse=True):
                out.append((p, flags))
    for p, flags in RENDERER_FIXED:
        if p.is_file():
            out.append((p, flags))
    return out


def have_playwright():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        return False


def render_playwright(src, pdf, paged):
    """Drive the browser directly so printing can wait on a condition.

    The command-line --print-to-pdf fires on the load event, which is halfway
    through Paged.js's work: measured over five runs per flag combination, no
    combination of --virtual-time-budget, --timeout or
    --run-all-compositor-stages-before-draw got above 2/5 complete documents.
    Waiting on the polyfill's own completion beacon is 4/4.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return f"playwright unavailable: {exc}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(src.as_uri(), wait_until="load")
                if paged:
                    page.wait_for_function("window.__pagedDone === true",
                                           timeout=60000)
                page.pdf(path=str(pdf), prefer_css_page_size=True,
                         print_background=True)
            finally:
                browser.close()
    except Exception as exc:
        return f"playwright: {str(exc).splitlines()[0][:200]}"
    if pdf.exists() and pdf.stat().st_size > 0:
        return None
    return "playwright wrote nothing"


def render_pdf(src, pdf, tmp):
    """Try each command-line renderer until one actually writes a file.

    Returns an error string, or None on success. This path cannot paginate
    reliably — see render_playwright — so it is only used for the unpaged
    fallback."""
    tried = []
    for i, (binary, flags) in enumerate(find_renderers()):
        cmd = [str(binary), *flags, "--disable-gpu", "--no-pdf-header-footer",
               f"--user-data-dir={tmp / f'profile{i}'}",
               f"--print-to-pdf={pdf}", src.as_uri()]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            tried.append(f"{binary.name}: {exc}")
            continue
        if pdf.exists() and pdf.stat().st_size > 0:
            return None
        tried.append(f"{binary.name}: exit {proc.returncode}, no output"
                     + (f" — {proc.stderr.strip()[:200]}" if proc.stderr else ""))
    if not tried:
        return "no Chrome, Chromium or Edge binary found"
    return "every renderer failed:\n  " + "\n  ".join(tried)


def unique(path):
    if not path.exists():
        return path
    n = 2
    while True:
        cand = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--outdir", default=str(Path.home() / "Documents" / "whatif"))
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--no-paged", action="store_true",
                    help="skip the Paged.js pass: end-notes, no folio")
    args = ap.parse_args()

    draft = Path(args.draft)
    if not draft.exists():
        print(f"no such file: {draft}", file=sys.stderr)
        return 2

    question, attribution, blocks, footnotes = parse(
        draft.read_text(encoding="utf-8")
    )
    if not blocks:
        print("draft has no body prose", file=sys.stderr)
        return 2

    # Pagination needs Paged.js and Paged.js needs Playwright to wait for it.
    # Without either, drop to end-notes rather than ship a coin-flip render.
    paged = not args.no_paged and PAGED.is_file() and have_playwright()

    # resolve(): a relative --outdir would otherwise reach Path.as_uri() and
    # blow up there, after the layout work has already been done.
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    pdf = unique(outdir / f"whatif-{slugify(question or draft.stem)}.pdf")
    tmp = Path(tempfile.mkdtemp(prefix="whatif-"))
    src = (outdir if args.keep_html else tmp) / (pdf.stem + ".html")

    def lay_out(paged_):
        src.write_text(
            build_html(question, attribution, blocks, footnotes, paged_),
            encoding="utf-8")
        if paged_:
            shutil.copyfile(PAGED, src.with_name("paged.polyfill.js"))

    lay_out(paged)
    err = render_playwright(src, pdf, paged) if have_playwright() else "skipped"
    if err:
        if paged:
            print(f"paged render failed ({err}); falling back to end-notes",
                  file=sys.stderr)
            paged = False
            lay_out(False)
        err = render_pdf(src, pdf, tmp)
    if err:
        print(err, file=sys.stderr)
        return 1

    chrome = find_chrome()
    if not args.no_open and chrome:
        subprocess.Popen(
            [str(chrome), pdf.as_uri()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print(pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
