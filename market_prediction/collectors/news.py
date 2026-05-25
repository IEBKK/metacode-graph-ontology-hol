"""뉴스 RSS 수집기 — Pythonista 호환 (feedparser + requests)"""
import requests
from datetime import datetime
from market_prediction.config import RSS_FEEDS, MAX_NEWS_PER_FEED
from market_prediction.utils.db import get_db

try:
    import feedparser
except ImportError:
    feedparser = None


def _parse_feed_manual(url):
    """feedparser 없을 때 최소 XML 파싱 폴백"""
    import xml.etree.ElementTree as ET
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    items = []
    for item in root.iter("item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        desc = item.findtext("description", "")
        pub = item.findtext("pubDate", "")
        items.append({
            "title": title,
            "summary": desc[:500],
            "link": link,
            "published": pub,
        })
    return items


def fetch_news(feeds=None):
    feeds = feeds or RSS_FEEDS
    all_items = []

    for name, url in feeds.items():
        try:
            if feedparser:
                feed = feedparser.parse(url)
                entries = feed.entries[:MAX_NEWS_PER_FEED]
                for e in entries:
                    all_items.append({
                        "source": name,
                        "title": e.title,
                        "summary": e.get("summary", "")[:500],
                        "published": e.get("published", ""),
                        "link": e.link,
                    })
            else:
                entries = _parse_feed_manual(url)[:MAX_NEWS_PER_FEED]
                for e in entries:
                    e["source"] = name
                    all_items.append(e)
        except Exception as exc:
            print(f"[뉴스] {name} 수집 실패: {exc}")

    return all_items


def save_news(items, db_path=None):
    now = datetime.now().isoformat()
    saved = 0
    with get_db(db_path) as conn:
        for item in items:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO news "
                    "(source,title,summary,published,link,fetched_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (item["source"], item["title"], item["summary"],
                     item["published"], item["link"], now),
                )
                saved += 1
            except Exception as exc:
                print(f"[뉴스 저장] {exc}")
    return saved


def get_recent_headlines(hours=24, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT source, title, published FROM news "
            "ORDER BY fetched_at DESC LIMIT 60"
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()
    news = fetch_news()
    n = save_news(news)
    print(f"{n}개 뉴스 저장 완료 (전체 {len(news)}개 수집)")
