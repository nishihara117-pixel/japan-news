#!/usr/bin/env python3
import os
import json
import time
import datetime
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError
import anthropic

RSS_FEEDS = [
    {"name": "BBC News - Asia", "url": "http://feeds.bbci.co.uk/news/world/asia/rss.xml", "logo": "BBC"},
    {"name": "BBC News - World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "logo": "BBC"},
    {"name": "CNN - World", "url": "http://rss.cnn.com/rss/edition_world.rss", "logo": "CNN"},
    {"name": "CNN - Asia", "url": "http://rss.cnn.com/rss/edition_asia.rss", "logo": "CNN"},
]

JAPAN_KEYWORDS = [
    "japan", "japanese", "tokyo", "osaka", "kyoto", "hiroshima",
    "nagasaki", "fukushima", "shinzo", "abe", "kishida", "fumio",
    "nikkei", "yen", "samurai", "anime", "sumo", "yokohama",
    "okinawa", "hokkaido", "mount fuji", "fuji", "sapporo",
    "nagoya", "kobe", "tsunami", "earthquake", "jpn",
]

MAX_ARTICLES = 12
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def fetch_rss(feed):
    try:
        req = Request(feed["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
    except Exception as e:
        print(f"RSS fetch error {feed['name']}: {e}")
        return []
    items = []
    for item in tree.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        text = (title + " " + desc).lower()
        if any(kw in text for kw in JAPAN_KEYWORDS):
            items.append({"title": title, "desc": desc, "link": link, "logo": feed["logo"]})
    return items

def translate(article):
    prompt = f"""以下の英語ニュースを日本語に翻訳・要約してください。

タイトル: {article['title']}
内容: {article['desc']}

以下のJSON形式のみで返してください:
{{"title_ja": "日本語タイトル", "summary_ja": "3文程度の日本語要約"}}"""
    for i in range(3):
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"Translate error (attempt {i+1}): {e}")
            time.sleep(2)
    return {"title_ja": article["title"], "summary_ja": article["desc"]}

def generate_html(articles, generated_at):
    cards = ""
    for a in articles:
        cards += f"""
<div class="card">
  <span class="logo {a['logo']}">{a['logo']}</span>
  <h2><a href="{a['link']}" target="_blank">{a.get('title_ja', a['title'])}</a></h2>
  <p>{a.get('summary_ja', a['desc'])}</p>
</div>"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🗾 日本関連ニュース</title>
<style>
body{{font-family:sans-serif;background:#0f1117;color:#e8eaf0;margin:0;padding:20px}}
h1{{text-align:center;color:#fff;margin-bottom:4px}}
.updated{{text-align:center;color:#666;font-size:13px;margin-bottom:24px}}
.card{{background:#1e2130;border-radius:10px;padding:20px;margin-bottom:16px;border-left:4px solid #4a9eff}}
.card h2{{margin:8px 0;font-size:17px}}
.card h2 a{{color:#7eb8ff;text-decoration:none}}
.card p{{color:#aab;font-size:14px;margin:6px 0 0}}
.logo{{font-size:11px;font-weight:bold;padding:2px 8px;border-radius:4px;color:#fff}}
.BBC{{background:#b40000}}
.CNN{{background:#cc0000}}
</style>
</head>
<body>
<h1>🗾 日本関連ニュース</h1>
<p class="updated">更新: {generated_at}</p>
{cards}
</body>
</html>"""

def main():
    all_items = []
    for feed in RSS_FEEDS:
        items = fetch_rss(feed)
        print(f"{feed['name']}: {len(items)} articles")
        all_items.extend(items)

    seen = set()
    unique = []
    for item in all_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    unique = unique[:MAX_ARTICLES]
    print(f"Translating {len(unique)} articles...")

    for article in unique:
        result = translate(article)
        article.update(result)
        time.sleep(1)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    generated_at = now.strftime("%Y年%m月%d日 %H:%M JST")

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(generate_html(unique, generated_at))

    meta = {"generated_at": generated_at, "article_count": len(unique), "articles": unique}
    with open("docs/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Done! {len(unique)} articles saved.")

if __name__ == "__main__":
    main()
