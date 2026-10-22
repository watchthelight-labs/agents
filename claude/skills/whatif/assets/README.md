# assets

Both files are vendored so the renderer works offline. Neither is installed
anywhere; deleting this folder is the whole uninstall, and `render.py` degrades
rather than failing if either goes missing.

`xkcd-script.ttf` — the hand-lettering face used for the drawing panels and the
running head. From https://github.com/ipython/xkcd-font, which digitised Randall
Munroe's handwriting with his permission and releases it under CC BY-NC 3.0.
Embedded in the page as a base64 `@font-face` rather than installed. If it is
missing the renderer falls back to Segoe Print, then Comic Sans.

Non-commercial only. That is the licence, not a suggestion.

`paged.polyfill.js` — Paged.js v0.4.3, MIT, licence text in
`paged.LICENSE.md`. It implements the parts of the paged-media spec Chrome does
not: `@page` margin boxes for the running head and folio, and `float: footnote`
so footnotes land at the foot of the page that refers to them. Copied next to
the HTML at render time. If it is missing, or if Playwright is not available to
wait for it, the renderer drops to end-notes with no folio.
