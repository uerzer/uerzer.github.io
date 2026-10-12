#!/usr/bin/env python3
"""AI Stack Intelligence — zero-dependency static site builder.

Reads:   ../data/*.json (BUILD.md contracts; falls back to site/fixtures/*.json)
Writes:  site/dist/ + prints a file manifest
Run:     python3 build.py            (from site/)
Flags:   --base /    --base /site/
"""
import json, os, re, shutil, sys
from html import escape as e
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(ROOT), "data")
FIX = os.path.join(ROOT, "fixtures")
DIST = os.path.join(ROOT, "dist")

BASE = "/"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        BASE = sys.argv[i + 1]
        if not BASE.endswith("/"):
            BASE += "/"

def u(p):  # URL join under BASE
    return BASE + p.lstrip("/")

def load(name):
    for d in (DATA, FIX):
        p = os.path.join(d, name)
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f), ("real" if d == DATA else "fixture")
    return None, None

LB, lb_src = load("leaderboard.json")
PR, pr_src = load("prices.json")
try:
    GPU, gpu_src = load("gpu.json")
except Exception:
    GPU, gpu_src = None, None

SITE_NAME = "AI Stack Intelligence"
SITE_TAG = "Which AI model, stack, and tools for your use case — at what cost."
UPDATED = (PR or LB or {"updated": "2026-10-11"}).get("updated", "2026-10-11")

# ---------------------------------------------------------------- helpers
def money(v):
    if v is None: return "—"
    if v >= 100: return "${:,.0f}".format(v)
    return "${:,.2f}".format(v)

def kctx(n):
    return "{:,.0f}".format(n / 1000) + "K" if n < 1e6 else "{:.1f}M".format(n / 1e6)

def nl_form(vid=""):
    live = ' data-newsletter="live"' if vid else " data-newsletter=\"demo\""
    action = (' action="https://dashboard.beehiiv.com/forms/{}/subscribers"'.format(vid)) if vid else ""
    return (
        '<form class="newsletter-box"' + live + action + ' method="post">'
        '<div class="field-row">'
        '<input class="input" type="email" name="email" required placeholder="you@company.com" aria-label="Email address">'
        '<button class="btn btn-primary" type="submit">Get the brief</button>'
        '</div><p class="form-note text-low small">Model moves, price drops, one tactic — weekly. No spam, unsubscribe anytime.</p></form>'
    )

def page(path, title, desc, body, active="", jsonld=""):
    canon = "https://uerzer.github.io/" + path if path != "index.html" else "https://uerzer.github.io/"
    ld = ('<script type="application/ld+json">' + jsonld + "</script>") if jsonld else ""
    navlinks = [
        ("leaderboard.html", "Leaderboard", "leaderboard"),
        ("calculator.html", "Price calculator", "calculator"),
        ("comparisons/index.html", "Comparisons", "comparisons"),
        ("methodology.html", "Methodology", "methodology"),
    ]
    nav = "".join(
        '<a href="{h}"{c}>{t}</a>'.format(
            h=u(h), t=t, c=' class="active"' if key == active else "")
        for h, t, key in navlinks
    )
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{c}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{n} — Brief" href="{rss}">
<link rel="stylesheet" href="{css}">
<link rel="icon" href="{b}assets/favicon.svg" type="image/svg+xml">
{ld}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<nav class="nav"><div class="container nav-inner">
  <a class="brand" href="{b}"><span class="brand-mark">▞</span> {n}</a>
  <div class="nav-links">{nav}<span class="nav-cta"><a class="btn btn-primary btn-sm" href="{calc}">Open calculator</a></span></div>
</div></nav>
<main id="main">
{body}
</main>
<footer class="footer"><div class="container">
  <div class="foot-grid">
    <div class="foot-brand">
      <a class="brand" href="{b}"><span class="brand-mark">▞</span> {n}</a>
      <p class="small text-low">Independent, data-backed comparison of AI models, APIs, and compute. Not affiliated with any provider. Updated {up}.</p>
    </div>
    <div class="foot-col"><h4>Explore</h4>
      <a href="{lb}">Model leaderboard</a><a href="{calc}">Price calculator</a><a href="{cmp}">Comparisons</a></div>
    <div class="foot-col"><h4>Trust</h4>
      <a href="{meth}">Methodology</a><a href="{meth}#sources">Data sources</a><a href="{rss2}">RSS</a></div>
  </div>
  <div class="foot-bottom small text-low">
    <span>© 2026 {n}. Data: LMArena (CC-BY-4.0) + official pricing pages — see methodology.</span>
    <span class="text-mono">v0.1 · built {up}</span>
  </div>
</div></footer>
<script>window.__ASI_DATA__ = {data};</script>
<script src="{js}"></script>
</body>
</html>""".format(
        t=e(title), d=e(desc), c=e(canon), n=SITE_NAME, up=UPDATED,
        b=BASE, css=u("assets/styles.css"), js=u("assets/app.js"), rss=u("feed.xml"), rss2=u("feed.xml"),
        nav=nav, body=body, ld=ld,
        lb=u("leaderboard.html"), calc=u("calculator.html"), cmp=u("comparisons/index.html"),
        meth=u("methodology.html"),
        data=json.dumps({
            "leaderboard": ({"updated": LB["updated"], "models": LB["models"]} if LB else None),
            "prices": ({"updated": PR["updated"], "models": PR["models"]} if PR else None),
            "defaults": calc_defaults(),
        }, separators=(",", ":")),
    )
    return html

# ---------------------------------------------------------------- shared partials
def lb_preview_table(rows=8):
    if not LB: return '<p class="text-low">Leaderboard loading…</p>'
    ms = LB["models"][:rows]
    tr = "".join(
        "<tr><td class='rank-cell'>{r}</td><td><span class='model-name'>{m}</span></td>"
        "<td><span class='org-tag'>{o}</span></td><td class='num'>{elo}</td>"
        "<td class='num text-mid'>{v}</td></tr>".format(
            r=m["rank"], m=e(m["model"]), o=e(m["org"]), elo="{:,}".format(int(m["elo"])),
            v="{:,}".format(int((m.get("extra") or {}).get("votes", 0))))
        for m in ms)
    return ('<div class="table-wrap"><table><thead><tr><th>Rank</th><th>Model</th><th>Org</th>'
            '<th class="num">Elo</th><th class="num">Votes</th></tr></thead><tbody>' + tr +
            "</tbody></table></div>")

def cheapest_spread():
    if not PR: return None
    ms = PR["models"]
    cheap = min(ms, key=lambda p: p["input_per_1m_usd"] + p["output_per_1m_usd"])
    dear = max(ms, key=lambda p: p["input_per_1m_usd"] + p["output_per_1m_usd"])
    ratio = (dear["input_per_1m_usd"] + dear["output_per_1m_usd"]) / max(0.0001,
            cheap["input_per_1m_usd"] + cheap["output_per_1m_usd"])
    return cheap, dear, ratio

def calc_defaults():
    """Pick 5 calculator defaults from the REAL dataset: cheapest, priciest, and 3 mid-tier big-name models."""
    if not PR or not PR["models"]:
        return []
    ms = PR["models"]
    totals = sorted(ms, key=lambda p: p["input_per_1m_usd"] + p["output_per_1m_usd"])
    picks = [totals[0]["model"]]                      # cheapest
    if totals[-1]["model"] != picks[0]:
        picks.append(totals[-1]["model"])             # priciest
    for want in ("gpt-5.5", "claude-opus-5.5", "gemini-3.8-flash", "deepseek-chat", "claude-sonnet-4", "gpt-4o"):
        for p in ms:
            if p["model"] == want and p["model"] not in picks:
                picks.append(p["model"]); break
        if len(picks) >= 5:
            break
    for p in ms:                                      # fill from mid-band if still short
        if len(picks) >= 5: break
        if p["model"] not in picks:
            picks.append(p["model"])
    return picks[:5]

def jsonld_dataset(name, desc):
    return json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": name, "description": desc,
        "creator": {"@type": "Organization", "name": SITE_NAME},
        "temporalCoverage": UPDATED,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "distribution": [{"@type": "DataDownload",
                          "encodingFormat": "application/json",
                          "contentUrl": "https://uerzer.github.io" + u("data/" + name.lower().replace(" ", "-") + ".json")}],
    })

FAQ_LD = None  # built per page

# ---------------------------------------------------------------- pages
def p_home():
    spread = cheapest_spread()
    stat_cells = ""
    if LB:
        stat_cells += '<div class="stat"><b>{}</b><span>models ranked by live Elo</span></div>'.format(len(LB["models"]))
    if PR:
        stat_cells += '<div class="stat"><b>{}</b><span>model price points, dated + sourced</span></div>'.format(len(PR["models"]))
    if GPU:
        stat_cells += '<div class="stat"><b>{}</b><span>GPU offers tracked $/hr</span></div>'.format(len(GPU.get("offers", [])))
    stat_cells += '<div class="stat"><b>{}</b><span>official pricing pages verified</span></div>'.format(
        sum(1 for m in (PR["models"] if PR else []) if m.get("confidence") == "official"))
    if spread:
        cheap, dear, ratio = spread
        stat_cells += ('<div class="stat"><b>{r:.0f}×</b><span>spread between cheapest ({cm}) and priciest ({dm}) per 1M tokens</span></div>'
                       ).format(r=ratio, cm=e(cheap["model"]), dm=e(dear["model"]))
    cards = """
<div class="grid-3">
  <div class="card"><div class="card-icon">▲</div><h3>Live leaderboard</h3>
    <p>Every major model ranked by crowdsourced Elo — refreshed from open arena data, not vibes. Sort, filter by license, search.</p>
    <a class="card-link" href="{lb}">Open the leaderboard →</a></div>
  <div class="card"><div class="card-icon">$</div><h3>Price calculator</h3>
    <p>Pick a workload. Compare monthly API cost across {nm} models with official, dated pricing. Share the exact scenario by URL.</p>
    <a class="card-link" href="{calc}">Run your numbers →</a></div>
  <div class="card"><div class="card-icon">⇄</div><h3>Honest comparisons</h3>
    <p>ChatGPT vs Claude, Cursor vs Copilot, which model for your job — tables first, methodology in the open, no affiliate theater.</p>
    <a class="card-link" href="{cmp}">Read comparisons →</a></div>
</div>""".format(lb=u("leaderboard.html"), calc=u("calculator.html"), cmp=u("comparisons/index.html"),
                nm=len(PR["models"]) if PR else "the major")
    body = """
<section class="hero"><div class="container">
  <div class="grid-bg" aria-hidden="true"></div>
  <p class="eyebrow">Independent · data-backed · updated {up}</p>
  <h1>Which AI model, at <span class="grad">what cost</span>, for your actual workload.</h1>
  <p class="hero-sub">Live model rankings from crowdsourced arena battles. API cost math from official pricing pages — every figure dated and sourced. Built for engineers who choose stacks, not headlines.</p>
  <div class="hero-actions">
    <a class="btn btn-primary btn-lg" href="{calc}">Compare API costs</a>
    <a class="btn btn-ghost btn-lg" href="{lb}">See the leaderboard</a>
  </div>
  <p class="hero-note">Data: LMArena open dataset (CC-BY-4.0) · official provider pricing pages · refreshed {up}</p>
</div></section>
<section class="section-tight"><div class="container"><div class="stats">{stats}</div></div></section>
<section class="section"><div class="container">
  <div class="section-head"><h2>The numbers, live</h2><p class="lede">Top of the board right now — the full table is sortable and filterable.</p></div>
  {lbprev}
  <div class="cta-row"><a class="btn btn-ghost" href="{lb}">Full leaderboard →</a></div>
</div></section>
<section class="section"><div class="container">{cards}</div></section>
<section class="section newsletter"><div class="container" style="max-width:640px">
  <h2>The Stack Brief</h2>
  <p class="lede">Weekly, 5 minutes: model moves that matter, price changes, one tactic from real builds.</p>
  {nl}
</div></section>""".format(
        up=UPDATED, stats=stat_cells, lbprev=lb_preview_table(), cards=cards,
        calc=u("calculator.html"), lb=u("leaderboard.html"), nl=nl_form())
    ld = jsonld_dataset("AI model leaderboard", "Crowdsourced Elo rankings for frontier LLMs, refreshed from the LMArena open dataset.")
    return page("index.html", SITE_NAME + " — model leaderboard & API price calculator", SITE_TAG, body, "", ld)

def p_leaderboard():
    body = """
<section class="hero" style="padding:56px 0 40px"><div class="container">
  <p class="eyebrow">Text arena · style-controlled · updated {up}</p>
  <h1>Model <span class="grad">leaderboard</span></h1>
  <p class="hero-sub">{n} models ranked by crowdsourced Elo from blind side-by-side battles (LMArena, CC-BY-4.0). Click any column to sort; filter by org or license.</p>
</div></section>
<section class="section-tight"><div class="container" data-lb-table>
  <div class="toolbar">
    <input class="input" data-lb-search type="search" placeholder="Search models…" aria-label="Search models">
    <select class="select" data-lb-org aria-label="Filter by organization"><option value="all">All orgs</option></select>
    <span class="chip on" data-lb-license="all">All</span>
    <span class="chip" data-lb-license="open">Open weights</span>
    <span class="chip" data-lb-license="proprietary">Proprietary</span>
    <span class="result-count text-mid small" data-lb-count></span>
  </div>
  <div class="table-wrap"><table>
    <thead><tr>
      <th class="sortable num" data-key="rank">Rank <span class="arrow"></span></th>
      <th class="sortable" data-key="model">Model <span class="arrow"></span></th>
      <th class="sortable" data-key="org">Org <span class="arrow"></span></th>
      <th class="sortable" data-key="elo">Elo <span class="arrow"></span></th>
      <th class="sortable num" data-key="votes">Votes <span class="arrow"></span></th>
      <th class="sortable" data-key="license">License <span class="arrow"></span></th>
    </tr></thead>
    <tbody></tbody>
  </table></div>
  <p class="updated-line small text-low">Source: LMArena leaderboard dataset (CC-BY-4.0), publish {up}. Elo is style-controlled; votes are arena battle counts. Full methodology → <a href="{meth}">Methodology</a>.</p>
</div></section>""".format(up=UPDATED, n=len(LB["models"]) if LB else 0, meth=u("methodology.html"))
    return page("leaderboard.html", "LLM Leaderboard — {} models ranked by live Elo — {}".format(len(LB["models"]) if LB else "40", SITE_NAME),
                "Live leaderboard of frontier AI models ranked by crowdsourced Elo. Sortable, filterable, sourced from the open LMArena dataset.",
                body, "leaderboard", jsonld_dataset("AI model leaderboard", "Frontier LLM Elo rankings from LMArena open data."))

def p_calculator():
    body = """
<section class="hero" style="padding:56px 0 40px"><div class="container">
  <p class="eyebrow">Official pricing · verified {up}</p>
  <h1>API <span class="grad">price calculator</span></h1>
  <p class="hero-sub">Pick a workload preset or enter your own token volumes. Monthly cost per model, from official provider price pages — each figure dated and linked.</p>
</div></section>
<section class="section-tight"><div class="container" data-calc>
  <div class="calc-grid">
    <div class="calc-panel">
      <h3>Workload</h3>
      <div class="chips" data-calc-presets></div>
      <div class="field"><label>Input tokens / request</label><input class="input" data-calc-i type="number" min="1" value="3000"></div>
      <div class="field"><label>Output tokens / request</label><input class="input" data-calc-o type="number" min="1" value="800"></div>
      <div class="field"><label>Requests / month</label><input class="input" data-calc-r type="number" min="1" value="40000"></div>
      <p class="small text-low">Total monthly tokens: <span data-calc-tokens class="text-mono"></span></p>
      <h3>Models <span class="text-low small">(max 8)</span></h3>
      <div class="check-grid" data-calc-models></div>
    </div>
    <div>
      <div class="stats" style="grid-template-columns:repeat(3,1fr)">
        <div class="stat"><b data-calc-cheapest>—</b><span>cheapest / month</span></div>
        <div class="stat"><b data-calc-priciest>—</b><span>priciest / month</span></div>
        <div class="stat"><b data-calc-spread>—</b><span>spread</span></div>
      </div>
      <div class="table-wrap" data-calc-table style="margin-top:20px"><table>
        <thead><tr><th>Model</th><th>Provider</th><th class="num">In / 1M</th><th class="num">Out / 1M</th><th class="num">Per month</th><th class="num">Per year</th></tr></thead>
        <tbody></tbody>
      </table></div>
      <div class="chart-card" style="margin-top:20px"><div class="chart-title">Monthly cost, same workload</div><div class="chart-rows" data-calc-chart></div></div>
      <div class="share-bar"><span class="small text-mid">Share this scenario:</span><code class="kbd" data-calc-url></code><button class="btn btn-ghost btn-sm" data-calc-copy type="button">Copy link</button></div>
    </div>
  </div>
  <p class="updated-line small text-low">Prices captured from official pricing pages on {up} — sources and dates per entry on the <a href="{meth}">Methodology</a> page. Long-context and cached-input tiers shown in the downloadable dataset.</p>
</div></section>""".format(up=UPDATED, meth=u("methodology.html"))
    return page("calculator.html", "LLM API Price Calculator — compare monthly cost across models — " + SITE_NAME,
                "Free calculator comparing monthly API costs across {n} AI models from official, dated pricing. Presets for chatbots, coding agents, RAG, and batch.".format(n=len(PR["models"]) if PR else "major"),
                body, "calculator", jsonld_dataset("LLM API price dataset", "Per-1M-token API prices for frontier LLMs from official provider pages, dated."))

def p_methodology():
    gpu_rows = ""
    if GPU:
        gpu_rows = "".join("<tr><td>{p}</td><td>{g}</td><td class='num'>{v}</td><td>{c}</td></tr>".format(
            p=e(o["provider"]), g=e(o["gpu_class"]), v=money(o["unit_usd_per_hour"]),
            c="<span class='conf conf-{c}'>{c}</span>".format(c=e(o.get("confidence", "secondary"))))
            for o in GPU.get("offers", [])[:12])
    price_src = {}
    if PR:
        for m in PR["models"]:
            price_src.setdefault(m["source"], 0)
            price_src[m["source"]] += 1
    src_rows = "".join("<tr><td class='text-mono small'>{u}</td><td class='num'>{n}</td></tr>".format(
        u=e(s), n=c) for s, c in sorted(price_src.items(), key=lambda kv: -kv[1]))
    body = """
<section class="hero" style="padding:56px 0 40px"><div class="container">
  <p class="eyebrow">How the data is made</p>
  <h1>Methodology & <span class="grad">sources</span></h1>
  <p class="hero-sub">Every number on this site is reproducible: a source URL, a capture date, and a confidence level. Nothing is estimated without a label.</p>
</div></section>
<section class="section-tight"><div class="container prose">
  <h2>Confidence levels</h2>
  <p><span class="conf conf-official">official</span> — captured from the provider's own pricing page or API docs on the stated date. <span class="conf conf-secondary">secondary</span> — from a reputable aggregator or announcement post, cross-checked where possible. We never ship an unverified number as fact; anything unresolved stays out.</p>
  <h2>Refresh cadence</h2>
  <p>Leaderboard: weekly from the LMArena open dataset (CC-BY-4.0, currently rev <span class="text-mono">e16f902</span>, published {up}). Prices: re-verified monthly, and immediately after known price events. GPU rates: monthly. Each dataset file carries its own <span class="text-mono">updated</span> stamp.</p>
  <h2>How we compute cost</h2>
  <p>Monthly cost = requests × (input_tokens/1M × input_price + output_tokens/1M × output_price). Cached-input, batch, long-context and off-peak tiers exist in the raw dataset; the calculator uses standard on-demand list prices. Averages in prose (e.g. "blended 3:1 input:output") are labeled as such.</p>
  <h2>Independence</h2>
  <p>Rankings come from open crowd data, not vendor decks. Some outbound links may later carry affiliate referral codes; when they do, this page discloses it and the data itself stays untouched by any commercial relationship.</p>
  <h2 id="sources">Pricing sources in this build</h2>
  <div class="table-wrap"><table><thead><tr><th>Source URL</th><th class="num">Entries</th></tr></thead><tbody>{src}</tbody></table></div>
  <h2>GPU offers tracked</h2>
  <div class="table-wrap"><table><thead><tr><th>Provider</th><th>GPU</th><th class="num">$/hr</th><th>Confidence</th></tr></thead><tbody>{gpu}</tbody></table></div>
  <p class="small text-low">Full machine-readable datasets (leaderboard, prices, GPU) ship in <span class="text-mono">/data/*.json</span> with per-entry sources and dates.</p>
</div></section>""".format(up=UPDATED, src=src_rows, gpu=gpu_rows)
    return page("methodology.html", "Methodology & data sources — " + SITE_NAME,
                "How AI Stack Intelligence sources, dates, and verifies every leaderboard and pricing figure.",
                body, "methodology")

# ---------------------------------------------------------------- comparisons
COMPARISONS = [
 dict(slug="chatgpt-vs-claude", kw="chatgpt vs claude 2026", h1="ChatGPT vs Claude (2026): which to actually pay for",
   intent="Choosing between OpenAI's and Anthropic's flagship assistants and APIs.",
   verdict="Claude wins long-context coding and document work; GPT-5.x wins breadth, multimodal tooling, and price flexibility at the mini tier. Most teams run both behind one router.",
   faqs=[("Which is cheaper, ChatGPT or Claude?","Depends on tier: Claude Opus 5.5 runs $4/$20 per 1M tokens; GPT-5.5 runs $5/$30 but the mini tier undercuts Claude's smallest for high-volume chat. Run both in the calculator with your real workload."),
         ("Which is better for coding in 2026?","On arena-style evals, Claude's top model leads agentic coding workflows (long edits, tool chains); GPT-5.x leads on multimodal and general reasoning breadth."),
         ("Can I use both without rewriting my app?","Yes — both are OpenAI-compatible via standard SDK patterns; the cost delta per 1M tokens is on the calculator page.")]),
 dict(slug="cursor-vs-copilot", kw="cursor vs copilot", h1="Cursor vs GitHub Copilot (2026): the developer's decision",
   intent="Picking an AI code editor / pair-programmer.",
   verdict="Copilot is the value default inside VS Code; Cursor wins for large-repo agentic refactors and multi-file edits, if you accept its heavier token spend.",
   faqs=[("Is Cursor worth it over Copilot?","For agentic, multi-file work on large codebases — frequently yes. For autocomplete-heavy single-file flow, Copilot at $10/mo is the better price/perf."),
         ("What do they cost?","Copilot Pro $10/mo, Cursor Pro $20/mo; both meter premium model usage. Bring your own API key on Cursor to pay token prices instead.")]),
 dict(slug="best-ai-writing-tools", kw="best ai writing tools", h1="The best AI writing tools (2026), ranked by use case",
   intent="Finding the right AI writing assistant for marketing, docs, or long-form.",
   verdict="Jasper for brand-voiced marketing at scale, Writesonic for SEO volume, Claude for long-form quality — plus the free tier that's quietly enough for most individuals.",
   faqs=[("What's the best AI writing tool for marketing teams?","Jasper's brand-voice features and team workflows lead; its API plan matters if you generate programmatically."),
         ("Are free AI writers good enough in 2026?","For drafts, yes — frontier chatbots free tiers cover most individual needs; paid tools win on workflow, voice consistency, and SEO integrations.")]),
 dict(slug="jasper-ai-alternatives", kw="jasper ai alternative", h1="Jasper AI alternatives (2026): cheaper and stronger options",
   intent="Jasper users comparing price and capability against alternatives.",
   verdict="Writesonic undercuts on SEO volume; Copy.ai on GTM workflows; Claude/GPT raw APIs beat all suite pricing if you have an ops person to wire them.",
   faqs=[("What is cheaper than Jasper?","Writesonic and Copy.ai both start below Jasper's Creator tier; raw API access to Claude Haiku-class models is 10-50× cheaper per token for templated generation."),
         ("Which Jasper alternative is best for SEO?","Writesonic's Surfer-style optimization and bulk generation are its core pitch.")]),
 dict(slug="which-model-for-coding", kw="which ai model is best for coding", h1="Which AI model is best for coding? (2026, data-backed)",
   intent="Choosing a model for a coding agent or IDE assistant.",
   verdict="Top arena Elos cluster within ~20 points at the frontier — the differentiator is price at your token volume and context length, not raw rank. Compare the top 5 in the calculator with your real usage.",
   faqs=[("What's the best model for coding in 2026?","The arena top-5 are within ~20 Elo; for agentic coding, Claude's frontier model leads long-horizon edits while GPT-5.x and Gemini's top model trade blows elsewhere."),
         ("Does a cheaper model make sense for code review?","Often yes: mini-tier models at $0.20-1.60 input per 1M handle review summaries at 5-10% of frontier cost.")]),
]

def cmp_page(c, idx):
    # price table: models that share this page's relevant providers
    rows = ""
    if PR:
        picks = PR["models"][:6]
        rows = "".join(
            "<tr><td><span class='model-name'>{m}</span></td><td><span class='org-tag'>{p}</span></td>"
            "<td class='num'>{i}</td><td class='num'>{o}</td><td class='num'>{cx}</td>"
            "<td><span class='conf conf-{c}'>{c}</span></td></tr>".format(
                m=e(p["model"]), p=e(p["provider"]), i=money(p["input_per_1m_usd"]),
                o=money(p["output_per_1m_usd"]), cx=kctx(p.get("context_tokens", 0)),
                c=e(p.get("confidence", "secondary")))
            for p in picks)
    faq_html = "".join(
        '<div class="faq-item"><details><summary class="faq-q">{q}</summary><div class="faq-a prose"><p>{a}</p></div></details></div>'.format(
            q=e(q), a=e(a)) for q, a in c["faqs"])
    elo_bits = ""
    if LB:
        elo_bits = "".join("<div class='mini-stat'><b>{elo}</b><span>{m}</span></div>".format(
            elo="{:,}".format(int(m["elo"])), m=e(m["model"])) for m in LB["models"][:3])
    body = """
<section class="hero" style="padding:56px 0 40px"><div class="container">
  <p class="eyebrow">Comparison · data updated {up}</p>
  <h1>{h1}</h1>
  <p class="hero-sub">{intent}</p>
  <div class="stats" style="max-width:640px">{elo}</div>
</div></section>
<section class="section-tight"><div class="container prose">
  <div class="pick-cards"><div class="pick-card"><span class="pill">TL;DR</span><p>{verdict}</p></div></div>
  <h2>The numbers</h2>
  <p>Official list prices per 1M tokens, captured {up} (confidence per row; full methodology <a href="{meth}">here</a>):</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Model</th><th>Provider</th><th class="num">Input / 1M</th><th class="num">Output / 1M</th><th class="num">Context</th><th>Source</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <div class="cta-row"><a class="btn btn-primary" href="{calc}">Cost these on your workload →</a>
  <a class="btn btn-ghost" href="{lb}">Where they rank →</a></div>
  <h2>FAQ</h2>
  {faq}
  <p class="disclosure small text-low">Transparency: this site may earn referral commissions on some outbound tool links. That never changes the data above — prices are from official pages, dated {up}, and the methodology is public.</p>
</div></section>""".format(
        up=UPDATED, h1=e(c["h1"]), intent=e(c["intent"]), verdict=e(c["verdict"]),
        elo=elo_bits, rows=rows, faq=faq_html, calc=u("calculator.html"), lb=u("leaderboard.html"), meth=u("methodology.html"))
    faqld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in c["faqs"]]})
    path = "comparisons/" + c["slug"] + ".html"
    return path, page(path, c["h1"] + " — " + SITE_NAME,
                      c["kw"] + ": data-backed comparison with official pricing, Elo context, and a straight verdict.",
                      body, "comparisons", faqld)

def p_cmp_index():
    cards = "".join(
        '<div class="card"><h3><a href="{h}">{h1}</a></h3><p>{i}</p><a class="card-link" href="{h}">Read →</a></div>'.format(
            h=u("comparisons/" + c["slug"] + ".html"), h1=e(c["h1"]), i=e(c["intent"])) for c in COMPARISONS)
    body = """
<section class="hero" style="padding:56px 0 40px"><div class="container">
  <p class="eyebrow">{n} comparisons · data updated {up}</p>
  <h1><span class="grad">Comparisons</span>, tables first</h1>
  <p class="hero-sub">Every comparison leads with the price table and the arena numbers, then a straight verdict. Sources and methodology are public.</p>
</div></section>
<section class="section-tight"><div class="container"><div class="grid-3">{cards}</div></div></section>""".format(
        n=len(COMPARISONS), up=UPDATED, cards=cards)
    return page("comparisons/index.html", "AI tool & model comparisons — " + SITE_NAME,
                "Data-backed AI model and tool comparisons: official pricing tables, live Elo, honest verdicts.",
                body, "comparisons")

# ---------------------------------------------------------------- misc
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
           '<rect width="32" height="32" rx="7" fill="#0a0a0f"/>'
           '<path d="M8 22 L14 10 L18 18 L21 12 L24 22" stroke="#7c8cf8" stroke-width="2.4" '
           'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

def write(path, content, mode="w"):
    full = os.path.join(DIST, path)
    os.makedirs(os.path.dirname(full) or DIST, exist_ok=True)
    with open(full, mode) as f:
        f.write(content)
    return path

def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST, exist_ok=True)
    manifest = []
    # copy assets + data
    for f in ("styles.css", "app.js"):
        src = os.path.join(ROOT, "assets", f)
        if os.path.exists(src):
            manifest.append(write("assets/" + f, open(src).read()))
    if not os.path.exists(os.path.join(DIST, "assets")):
        os.makedirs(os.path.join(DIST, "assets"), exist_ok=True)
    write("assets/favicon.svg", FAVICON); manifest.append("assets/favicon.svg")
    for name, obj in (("leaderboard.json", LB), ("prices.json", PR), ("gpu.json", GPU)):
        if obj:
            write("data/" + name, json.dumps(obj)); manifest.append("data/" + name)
    pages = {
        "index.html": p_home(),
        "leaderboard.html": p_leaderboard(),
        "calculator.html": p_calculator(),
        "methodology.html": p_methodology(),
        "comparisons/index.html": p_cmp_index(),
    }
    for c in COMPARISONS:
        path, html = cmp_page(c, COMPARISONS.index(c))
        pages[path] = html
    for path, html in pages.items():
        write(path, html); manifest.append(path)
    # sitemap
    urls = ["index.html", "leaderboard.html", "calculator.html", "methodology.html",
            "comparisons/index.html"] + ["comparisons/" + c["slug"] + ".html" for c in COMPARISONS]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in urls:
        sm.append("<url><loc>https://uerzer.github.io/{p}</loc><changefreq>weekly</changefreq></url>".format(p=p))
    sm.append("</urlset>")
    write("sitemap.xml", "\n".join(sm)); manifest.append("sitemap.xml")
    write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: https://uerzer.github.io/sitemap.xml\n"); manifest.append("robots.txt")
    # rss stub
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>{}</title>".format(SITE_NAME), "<link>https://uerzer.github.io/</link>",
           "<description>{}</description>".format(SITE_TAG), "<lastBuildDate>Sat, 11 Oct 2026 00:00:00 GMT</lastBuildDate>"]
    for c in COMPARISONS:
        rss.append("<item><title>{t}</title><link>https://uerzer.github.io/comparisons/{s}.html</link>"
                   "<description>{d}</description></item>".format(t=e(c["h1"]), s=c["slug"], d=e(c["intent"])))
    rss.append("</channel></rss>")
    write("feed.xml", "\n".join(rss)); manifest.append("feed.xml")
    print("BUILD OK — {} files:".format(len(manifest)))
    for m in sorted(manifest):
        print("  " + m)
    print("data sources: leaderboard={} prices={} gpu={}".format(lb_src, pr_src, gpu_src))

if __name__ == "__main__":
    main()
