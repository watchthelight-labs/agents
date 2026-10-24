<!-- <wtl> project: agents | file: THIRD-PARTY.md | author: watchthelight </wtl> -->
# Third-party pieces

## Vendored here (their licences apply)

| What | From | Licence |
|---|---|---|
| `claude/skills/caveman*`, `claude/hooks/caveman-*.js` | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Apache-2.0 or MIT ([licenses/caveman-APACHE-2.0.txt](licenses/caveman-APACHE-2.0.txt)) |
| `claude/skills/rea` (adapted from the `reverse-engineer-anything` skill) | [morluto/rea](https://github.com/morluto/rea) | MIT ([licenses/rea-MIT.txt](licenses/rea-MIT.txt)); text adapted, no REA code copied |
| `claude/skills/whatif/assets/paged.polyfill.js` | [Paged.js](https://pagedjs.org) | MIT |
| `claude/skills/whatif/assets/xkcd-script.ttf` | [xkcd script font](https://github.com/ipython/xkcd-font) | CC BY-NC 3.0 |

## Used, not copied

Install these from their own sources.

| What | Where | How |
|---|---|---|
| Cloudflare skills (agents-sdk, cloudflare, durable-objects, wrangler, workers-best-practices, sandbox-sdk, web-perf, cloudflare-email-service, turnstile-spin) | [cloudflare/skills](https://github.com/cloudflare/skills) | follow its README |
| graphify (by safishamsi) | [graphifyy on PyPI](https://pypi.org/project/graphifyy/) | `pip install graphifyy`, then its skill |
| Playwright MCP | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | `claude mcp add playwright -- npx -y @playwright/mcp@latest` |
| frontend-design, rust-analyzer-lsp | Claude Code's official plugin marketplace | `/plugin` |
| Anthropic's document skills (docx, pdf, pptx, xlsx, ...) | built into claude.ai | nothing to install |
