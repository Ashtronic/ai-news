import anthropic
import feedparser
import json
import os
from datetime import datetime
from pathlib import Path
from jinja2 import Template
import pytz

# ── Config ───────────────────────────────────────────────
FEEDS = [
    "https://www.anthropic.com/news.rss",
    "https://openai.com/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://ai.meta.com/blog/feed/",
]

AEST       = pytz.timezone("Australia/Melbourne")
now        = datetime.now(AEST)
date_human = now.strftime("%A, %-d %B %Y")
time_human = now.strftime("%-I:%M %p %Z")
date_slug  = now.strftime("%Y-%m-%d")
is_monday  = True #now.weekday() == 0  # 0 = Monday

# ── Step 1: Fetch RSS ────────────────────────────────────
def fetch_headlines():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                items.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", "")[:400],
                    "source":  feed.feed.get("title", url),
                    "link":    entry.get("link", ""),
                })
        except Exception as e:
            print(f"Feed error {url}: {e}")
    return items

# ── Step 2: Generate daily brief ─────────────────────────
def generate_brief(headlines):
    client = anthropic.Anthropic()

    headlines_text = "\n\n".join([
        f"SOURCE: {h['source']}\nTITLE: {h['title']}\nSUMMARY: {h['summary']}"
        for h in headlines
    ])

    prompt = (
        f"You are an AI product advisor helping software engineers build AI products.\n"
        f"Today is {date_human}.\n\n"
        f"Based on these recent AI headlines from the last 24 hours:\n\n"
        f"{headlines_text}\n\n"
        f"Generate an AI Builder Brief as strict JSON with these exact keys:\n"
        '{\n'
        '  "quote_text": "",\n'
        '  "quote_author": "",\n'
        '  "quote_source": "",\n'
        '  "key_updates": [\n'
        '    {\n'
        '      "vendor": "",\n'
        '      "change": "",\n'
        '      "category": "",\n'
        '      "impact": "",\n'
        '      "decision": "Use Now|Watch|Ignore",\n'
        '      "why": ""\n'
        '    }\n'
        '  ],\n'
        '  "top_picks": [\n'
        '    {\n'
        '      "tool": "",\n'
        '      "category": "",\n'
        '      "why_it_stands_out": "",\n'
        '      "when_to_use": ""\n'
        '    }\n'
        '  ],\n'
        '  "try_this": [\n'
        '    {\n'
        '      "experiment": "",\n'
        '      "goal": "",\n'
        '      "effort": "Low|Medium",\n'
        '      "expected_outcome": ""\n'
        '    }\n'
        '  ],\n'
        '  "tool_map": [\n'
        '    {\n'
        '      "type": "Added|Updated|Deprecated",\n'
        '      "item": "",\n'
        '      "change": "",\n'
        '      "notes": ""\n'
        '    }\n'
        '  ],\n'
        '  "insight_headline": "",\n'
        '  "insight_body": ""\n'
        '}\n\n'
        "Rules:\n"
        "- quote_text: a real historical AI or technology quote, different every day\n"
        "- quote_author: full name of the person\n"
        "- quote_source: publication, speech or book it came from\n"
        "- key_updates: 5-8 rows, high signal only, ignore hype\n"
        "- top_picks: max 3 rows\n"
        "- try_this: max 2 rows\n"
        "- tool_map: only include if real tool changes exist today\n"
        "- insight: one sharp pattern observation across today's news\n"
        "- Be concise and opinionated, avoid generic statements\n"
        "- Return ONLY valid JSON, no other text, no markdown fences"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── Step 3: Generate tools reference (Mondays only) ──────
def generate_tools():
    client = anthropic.Anthropic()

    prompt = (
        f"You are an AI product advisor. Today is {date_human}.\n\n"
        f"Generate a comprehensive AI tools reference as strict JSON with these exact keys:\n"
        '{\n'
        '  "ecosystem": [\n'
        '    {\n'
        '      "layer": "",\n'
        '      "google": "",\n'
        '      "openai": "",\n'
        '      "anthropic": "",\n'
        '      "meta": "",\n'
        '      "microsoft": "",\n'
        '      "popularity": 0\n'
        '    }\n'
        '  ],\n'
        '  "open_models": [\n'
        '    {\n'
        '      "vendor": "",\n'
        '      "models": "",\n'
        '      "license": "",\n'
        '      "practical_use": ""\n'
        '    }\n'
        '  ],\n'
        '  "best_tools": [\n'
        '    {\n'
        '      "work_type": "",\n'
        '      "best_closed": "",\n'
        '      "best_open": "",\n'
        '      "when_to_use": ""\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "Rules:\n"
        "- ecosystem: include these exact layers: Core Models, APIs / Platform, Dev Tools, Assistants / Apps, Research Tools, Creative / Media, Edge / On-device, Voice / Speech, Agent Frameworks\n"
        "- ecosystem vendors: Google, OpenAI, Anthropic, Meta, Microsoft — use dash if no strong offering\n"
        "- popularity: integer 0-100 composite of API adoption, developer mindshare, end-user traffic\n"
        "- open_models: include Meta, Google, Mistral, DeepSeek, Alibaba/Qwen, Microsoft, and other active players\n"
        "- best_tools work types: Chat, Coding, RAG, Agents, Search, Image, Video, Speech, Edge, Fine-tuning, Multimodal\n"
        "- Be concise, max 2-3 items per cell\n"
        "- Only include stable, widely used tools — no experimental releases\n"
        "- Return ONLY valid JSON, no other text, no markdown fences"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── Step 4: Render HTML ──────────────────────────────────
def render_brief(data):
    base = Path(__file__).parent.parent
    template_src = (base / "templates/brief.html").read_text()
    tmpl = Template(template_src)
    return tmpl.render(
        data=data,
        date_human=date_human,
        time_human=time_human,
        date_slug=date_slug,
    )

def render_tools(tools):
    base = Path(__file__).parent.parent
    template_src = (base / "templates/tools.html").read_text()
    tmpl = Template(template_src)
    return tmpl.render(
        tools=tools,
        date_human=date_human,
        time_human=time_human,
    )

# ── Step 5: Save to docs/ ────────────────────────────────
def save_files(brief_html, tools_html=None):
    docs = Path(__file__).parent.parent / "docs"
    docs.mkdir(exist_ok=True)

    # Daily brief
    (docs / f"{date_slug}.html").write_text(brief_html)
    (docs / "latest.html").write_text(brief_html)

    # Tools reference (Monday only)
    if tools_html:
        (docs / "tools.html").write_text(tools_html)
        print("Saved docs/tools.html")

    # Rebuild index
    issues = sorted(docs.glob("2*.html"), reverse=True)
    base = Path(__file__).parent.parent
    index_template = (base / "templates/index.html").read_text()
    links = []
    for f in issues:
        try:
            label = datetime.strptime(f.stem, "%Y-%m-%d").strftime("%A, %-d %B %Y")
        except ValueError:
            label = f.stem
        links.append('<li><a href="' + f.name + '">' + label + '</a></li>')
    index_html = index_template.replace("{{ links }}", "\n".join(links))
    (docs / "index.html").write_text(index_html)

    print(f"Saved docs/{date_slug}.html")

# ── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting brief for {date_human}...")
    print(f"Monday run (tools refresh): {is_monday}")

    # Daily brief
    headlines = fetch_headlines()
    print(f"Got {len(headlines)} headlines")
    data = generate_brief(headlines)
    print("Brief generated")
    brief_html = render_brief(data)

    # Tools reference — Mondays only
    tools_html = None
    if is_monday:
        print("Monday — regenerating tools reference...")
        tools = generate_tools()
        print("Tools generated")
        tools_html = render_tools(tools)

    save_files(brief_html, tools_html)
    print("Done.")
