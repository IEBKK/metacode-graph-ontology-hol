"""뉴스 RSS 수집기 — 한국 + 미국/국제 영문 뉴스"""
import requests
from datetime import datetime
from market_prediction.config import RSS_FEEDS_KR, RSS_FEEDS_GLOBAL, MAX_NEWS_PER_FEED
from market_prediction.utils.db import get_db

try:
    import feedparser
except ImportError:
    feedparser = None


def _parse_feed_manual(url):
    """feedparser 없을 때 최소 XML 파싱 폴백"""
    import xml.etree.ElementTree as ET
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
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


def _fetch_from_feeds(feeds, region):
    all_items = []
    for name, url in feeds.items():
        try:
            if feedparser:
                feed = feedparser.parse(url)
                entries = feed.entries[:MAX_NEWS_PER_FEED]
                for e in entries:
                    all_items.append({
                        "source": name,
                        "region": region,
                        "title": e.title,
                        "summary": e.get("summary", "")[:500],
                        "published": e.get("published", ""),
                        "link": e.link,
                    })
            else:
                entries = _parse_feed_manual(url)[:MAX_NEWS_PER_FEED]
                for e in entries:
                    e["source"] = name
                    e["region"] = region
                    all_items.append(e)
        except Exception as exc:
            print(f"[뉴스] {name} 수집 실패: {exc}")
    return all_items


def fetch_news_kr(feeds=None):
    return _fetch_from_feeds(feeds or RSS_FEEDS_KR, "KR")


def fetch_news_global(feeds=None):
    return _fetch_from_feeds(feeds or RSS_FEEDS_GLOBAL, "GLOBAL")


def fetch_all_news():
    kr = fetch_news_kr()
    gl = fetch_news_global()
    print(f"[뉴스] 한국 {len(kr)}건, 글로벌 {len(gl)}건 수집")
    return kr + gl


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


def get_recent_headlines(hours=24, region=None, db_path=None):
    with get_db(db_path) as conn:
        if region:
            rows = conn.execute(
                "SELECT source, title, published FROM news "
                "WHERE source IN (SELECT source FROM news WHERE source LIKE ?) "
                "ORDER BY fetched_at DESC LIMIT 60",
                (f"%{region.lower()}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT source, title, published FROM news "
                "ORDER BY fetched_at DESC LIMIT 100"
            ).fetchall()
    return [dict(r) for r in rows]


def get_headlines_by_source_type(db_path=None):
    """한국/글로벌 뉴스를 분류해서 반환"""
    from market_prediction.config import RSS_FEEDS_KR, RSS_FEEDS_GLOBAL
    kr_sources = set(RSS_FEEDS_KR.keys())
    gl_sources = set(RSS_FEEDS_GLOBAL.keys())

    all_headlines = get_recent_headlines(db_path=db_path)
    kr_news = [h for h in all_headlines if h["source"] in kr_sources]
    gl_news = [h for h in all_headlines if h["source"] in gl_sources]
    return {"kr": kr_news, "global": gl_news}


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()
    news = fetch_all_news()
    n = save_news(news)
    print(f"{n}개 뉴스 저장 완료 (전체 {len(news)}개 수집)")
