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
is_monday  = now.weekday() == 0

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

# ── Step 3: Generate tools reference ─────────────────────
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
        "- ecosystem layers: Core Models, APIs / Platform, Dev Tools, Assistants / Apps, Research Tools, Creative / Media, Edge / On-device, Voice / Speech, Agent Frameworks\n"
        "- ecosystem vendors: Google, OpenAI, Anthropic, Meta, Microsoft — use dash if no strong offering\n"
        "- popularity: integer 0-100 composite of API adoption, developer mindshare, end-user traffic\n"
        "- open_models: include Meta, Google, Mistral, DeepSeek, Alibaba/Qwen, Microsoft and other active players\n"
        "- best_tools work types: Chat, Coding, RAG, Agents, Search, Image, Video, Speech, Edge, Fine-tuning, Multimodal\n"
        "- max 2-3 items per cell, stable widely used tools only\n"
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

# ── Step 4: Generate changelog from diff ─────────────────
def generate_changelog(current, previous, previous_date):
    client = anthropic.Anthropic()

    prompt = (
        f"You are an AI product advisor. Today is {date_human}.\n\n"
        f"Compare these two weekly AI tools snapshots and identify what changed.\n\n"
        f"PREVIOUS SNAPSHOT ({previous_date}):\n"
        f"{json.dumps(previous, indent=2)}\n\n"
        f"CURRENT SNAPSHOT ({date_slug}):\n"
        f"{json.dumps(current, indent=2)}\n\n"
        f"Generate a changelog as strict JSON:\n"
        '{\n'
        '  "summary": "",\n'
        '  "changes": [\n'
        '    {\n'
        '      "type": "added|removed|updated|popularity",\n'
        '      "section": "ecosystem|open_models|best_tools",\n'
        '      "item": "",\n'
        '      "detail": "",\n'
        '      "signal": "up|down|new|removed|changed"\n'
        '    }\n'
        '  ],\n'
        '  "trend_observation": ""\n'
        '}\n\n'
        "Rules:\n"
        "- summary: 1-2 sentence overview of the week's shifts\n"
        "- changes: list every meaningful change, skip trivial wording differences\n"
        "- popularity changes: only flag if difference is 3 or more points\n"
        "- type popularity: use for score changes, updated: for content changes\n"
        "- item: short label e.g. 'OpenAI — Dev Tools' or 'DeepSeek V3'\n"
        "- detail: concise description of what changed\n"
        "- signal: up/down for popularity, new/removed for additions/deletions, changed for content\n"
        "- trend_observation: one sharp insight about the pattern of changes this week\n"
        "- If no meaningful changes, return empty changes array and note in summary\n"
        "- Keep detail field under 15 words per change\n"
        "- Keep summary under 30 words\n"
        "- Keep trend_observation under 20 words\n"
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

# ── Step 5: Load previous tools snapshot ─────────────────
def load_previous_tools():
    docs = Path(__file__).parent.parent / "docs"
    snapshots = sorted(docs.glob("tools-*.json"), reverse=True)
    if not snapshots:
        return None, None
    latest = snapshots[0]
    date = latest.stem.replace("tools-", "")
    try:
        data = json.loads(latest.read_text())
        return data, date
    except Exception:
        return None, None

# ── Step 6: Render HTML ──────────────────────────────────
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

def render_changelog(changelog, all_changelogs):
    base = Path(__file__).parent.parent
    template_src = (base / "templates/changelog.html").read_text()
    tmpl = Template(template_src)
    return tmpl.render(
        changelog=changelog,
        all_changelogs=all_changelogs,
        date_human=date_human,
        time_human=time_human,
        date_slug=date_slug,
    )

# ── Step 7: Save files ───────────────────────────────────
def save_files(brief_html, tools_html=None, tools_data=None,
               changelog_html=None, changelog_data=None):
    docs = Path(__file__).parent.parent / "docs"
    docs.mkdir(exist_ok=True)

    # Daily brief
    (docs / f"{date_slug}.html").write_text(brief_html)
    (docs / "latest.html").write_text(brief_html)
    print(f"Saved docs/{date_slug}.html")

    # Monday — tools + changelog
    if tools_html and tools_data:
        (docs / "tools.html").write_text(tools_html)
        (docs / f"tools-{date_slug}.json").write_text(
            json.dumps(tools_data, indent=2)
        )
        print(f"Saved docs/tools.html + docs/tools-{date_slug}.json")

    if changelog_html:
        (docs / "changelog.html").write_text(changelog_html)
        # Append to changelog history JSON
        history_file = docs / "changelog-history.json"
        if history_file.exists():
            history = json.loads(history_file.read_text())
        else:
            history = []
        history.insert(0, {"date": date_slug, "date_human": date_human, **changelog_data})
        history_file.write_text(json.dumps(history, indent=2))
        print("Saved docs/changelog.html + changelog-history.json")

    # Rebuild index
    issues = sorted(docs.glob("2*.html"), reverse=True)
    base = Path(__file__).parent.parent
    index_template = (base / "templates/index.html").read_text()
    links = []
    for f in issues:
        try:
            label = datetime.strptime(
                f.stem, "%Y-%m-%d"
            ).strftime("%A, %-d %B %Y")
        except ValueError:
            label = f.stem
        links.append(
            '<li><a href="' + f.name + '">' + label + '</a></li>'
        )
    index_html = index_template.replace("{{ links }}", "\n".join(links))
    (docs / "index.html").write_text(index_html)

# ── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting brief for {date_human}...")
    print(f"Monday run (tools + changelog): {is_monday}")

    # Daily brief
    headlines = fetch_headlines()
    print(f"Got {len(headlines)} headlines")
    data = generate_brief(headlines)
    print("Brief generated")
    brief_html = render_brief(data)

    # Monday — tools + changelog
    tools_html = tools_data = changelog_html = changelog_data = None

    if is_monday:
        print("Monday — generating tools reference...")
        tools_data = generate_tools()
        print("Tools generated")
        tools_html = render_tools(tools_data)

        print("Loading previous snapshot for diff...")
        previous_data, previous_date = load_previous_tools()

        docs = Path(__file__).parent.parent / "docs"
        history_file = docs / "changelog-history.json"
        all_changelogs = []
        if history_file.exists():
            all_changelogs = json.loads(history_file.read_text())

        if previous_data:
            print(f"Comparing with snapshot from {previous_date}...")
            changelog_data = generate_changelog(
                tools_data, previous_data, previous_date
            )
            print("Changelog generated")
        else:
            print("No previous snapshot — generating first-run changelog page...")
            changelog_data = {
                "summary": "This is the first snapshot of the AI tools landscape. Check back next Monday for the first weekly diff.",
                "changes": [],
                "trend_observation": "Baseline established. Trends will appear from next Monday onwards."
            }

        changelog_html = render_changelog(changelog_data, all_changelogs)

    save_files(brief_html, tools_html, tools_data, changelog_html, changelog_data)
    print("Done.")
