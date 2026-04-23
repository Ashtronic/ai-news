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

# ── Step 2: Call Claude ──────────────────────────────────
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

# ── Step 3: Render HTML ──────────────────────────────────
def render_html(data):
    template_src = Path("templates/brief.html").read_text()
    tmpl = Template(template_src)
    return tmpl.render(
        data=data,
        date_human=date_human,
        time_human=time_human,
        date_slug=date_slug,
    )

# ── Step 4: Save to docs/ ────────────────────────────────
def save_files(html):
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / f"{date_slug}.html").write_text(html)
    (docs / "latest.html").write_text(html)
    issues = sorted(docs.glob("2*.html"), reverse=True)
    (docs / "index.html").write_text(build_index(issues))
    print(f"Saved docs/{date_slug}.html")

def build_index(issues):
    links = []
    for f in issues:
        try:
            label = datetime.strptime(f.stem, "%Y-%m-%d").strftime("%A, %-d %B %Y")
        except ValueError:
            label = f.stem
        links.append('<li><a href="' + f.name + '">' + label + '</a></li>')
    links_html = "\n".join(links)

    index = Path("templates/index.html").read_text()
    return index.replace("{{ links }}", links_html)

# ── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting brief for {date_human}...")
    headlines = fetch_headlines()
    print(f"Got {len(headlines)} headlines")
    data = generate_brief(headlines)
    print("Brief generated")
    html = render_html(data)
    save_files(html)
    print("Done.")
