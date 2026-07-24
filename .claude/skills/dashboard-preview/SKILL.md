---
name: dashboard-preview
description: Run the contributor-metrics dashboard locally against the real deployed JSON and prove main.js renders without throwing. Use this whenever touching public/main.js, public/index.html, public/style.css, or the shape of anything the pipeline writes into results/*.json — including asks like "run it locally", "start a local server", "preview the page", "check the dashboard still works", "動作確認", or verifying a chart, metric card, or section before opening a PR. Use it for pipeline-side changes too: the page reads those JSON files directly, so adding, renaming, or dropping a field can blank the whole dashboard even though no front-end file changed.
---

# Previewing and verifying the dashboard

The dashboard is static HTML that fetches JSON at runtime and draws everything
client-side. Nothing about a front-end change is checked before deploy — no
build, no type check, no test — so a wrong assumption about the data's shape
first shows up as a blank page for real visitors.

That is not hypothetical. A change once made the Top Repositories ranking
include repositories that have a current star count but no history series. The
chart builder iterated the same list and reached for `json[repo_stars_history]`,
which was `undefined`, and the resulting throw escaped the top-level render
sequence and aborted **every section after it**. The page had rendered fine in
every earlier version, and the fetch-level error handling looked thorough — it
just didn't cover errors thrown *during* rendering.

So the goal here is to run the actual `main.js` against actual data before it
reaches anyone. Two levels, both cheap:

1. **Headless run** — catches throws, in about a second, no browser needed.
2. **Local server** — for looking at layout, colours, and wording yourself.

Do the headless run even when you plan to look at the page anyway. It reports
the failing line and stack, which a blank browser tab does not.

## 1. Get real data

```bash
.claude/skills/dashboard-preview/scripts/fetch_data.sh public
```

This downloads the ten published JSON files into `public/`. They are gitignored,
so this never dirties a commit.

Use the deployed copies rather than hand-written fixtures. They are real and
current, and they contain the awkward shapes that actually break things —
repositories missing from one file but present in another, empty series, fields
that only some entries carry. Regenerating them locally is not a practical
alternative: that needs a GitHub token and roughly an hour.

## 2. Run it headless

```bash
node .claude/skills/dashboard-preview/scripts/verify_render.mjs public
```

The script evaluates `public/main.js` in a stubbed DOM with `fetch` served from
local files and `ApexCharts` recorded rather than drawn. It exits non-zero if
anything threw, so it also works as a pre-commit or pre-deploy gate.

A healthy run names each chart and how many series it drew, plus which sections
produced content:

```
PASS — main.js ran with no uncaught errors
  charts rendered: 12
    GitHub Star Growth Over Time: 22 series
    ...
  sections with content: 7
    #stars-stats (3262 chars)
```

Read those numbers, don't just check for PASS. A chart that renders with zero
series, or a stats section that never appears, is a real defect the script
cannot call a failure — it only knows nothing threw.

To inspect what a specific element received:

```bash
node .claude/skills/dashboard-preview/scripts/verify_render.mjs public --dump '#stars-note'
```

`--json` prints the whole report as JSON if you want to assert on it.

### If node is missing

The repo has no Node dependency, so it may not be installed. Fetch a private
copy into the scratchpad rather than installing system-wide:

```bash
curl -sSL -o /tmp/node.tar.xz https://nodejs.org/dist/v22.11.0/node-v22.11.0-linux-x64.tar.xz
tar -xf /tmp/node.tar.xz -C /tmp
/tmp/node-v22.11.0-linux-x64/bin/node --version
```

Then invoke that binary by path.

### What the stub does not cover

It proves the code runs and what data reached each element. It says nothing
about how any of it looks — layout, contrast, overflow, dark mode, and whether
ApexCharts itself is happy with the options all need a browser. Say so plainly
when reporting results; "verified" without that qualifier overstates it.

## 3. Serve it for a human look

```bash
cd public && python3 -m http.server 8000 --bind 127.0.0.1
```

Then open <http://localhost:8000/index.html>. Run it in the background so the
session stays usable, and confirm it is actually up before handing over the URL:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/index.html
```

Opening `index.html` as a `file://` URL does not work — the page fetches JSON by
relative path, which needs an HTTP origin.

Tell the user the URL, what you changed, and what specifically to look at.

## Verifying a change the pipeline hasn't published yet

Deployed data only exercises the fields that already exist. If your change adds
or renames one, the deployed copies will silently take the fallback path and the
new code never runs — a PASS then means very little.

When that applies, write the new shape into a copy of the data and point the
script at it, keeping `public/` untouched:

```bash
cp -r public /tmp/newdata
# edit /tmp/newdata/<file>.json to add the new field
node .claude/skills/dashboard-preview/scripts/verify_render.mjs public /tmp/newdata
```

Derive the synthetic values from the real data instead of inventing them, so the
preview matches what the pipeline will actually produce. Check both paths: with
the field, and with the deployed data that lacks it, since older cached payloads
are served until the next successful run.

## Reporting back

Say which of these you did and what each showed. Distinguish "ran without
throwing" from "looks right" — only a browser establishes the second, and if you
could not open one, ask the user to confirm that part.
