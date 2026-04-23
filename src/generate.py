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

    prompt = f"""You are an AI product advisor helping software engineers build AI products.
Today is {date_human}.

Based on these recent AI headlines from the last 24 hours:

{headlines_text}

Generate an AI Builder Brief as strict JSON with these exact keys:
{{
  "key_updates": [
    {{
      "vendor": "",
      "change": "",
      "category": "",
      "impact": "",
      "decision": "Use Now|Watch|Ignore",
      "why": ""
    }}
  ],
  "top_picks": [
    {{
      "tool": "",
      "category": "",
      "why_it_stands_out": "",
      "when_to_use": ""
    }}
  ],
  "try_this": [
    {{
      "experiment": "",
      "goal": "",
      "effort": "Low|Medium",
      "expected_outcome": ""
    }}
  ],
  "tool_map": [
    {{
      "type": "Added|Updated|Deprecated",
      "item": "",
      "change": "",
      "notes": ""
    }}
  ],
  "insight_headline": "",
  "insight_body": ""
}}

Rules:
- key_updates: 5-8 rows, high signal only, ignore hype
- top_picks: max 3 rows
- try_this: max 2 rows
- tool_map: only include if real tool changes exist today
- insight: one sharp pattern observation across today's news
- Be concise and opinionated, avoid generic statements
- Return ONLY valid JSON, no other text, no markdown fences"""

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
    links = "\n".join([
        f'<li><a href="{f.name}">'
        f'{datetime.strptime(f.stem, "%Y-%m-%d").strftime("%A, %-d %B %Y")}'
        f'</a></li>'
        for f in issues
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The State of AI — ainews.mavenotics.com</title>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700;9..144,900&family=JetBrains
