"""
중앙 설정 관리. 환경변수 또는 직접 수정.
Pythonista에서는 .env 대신 이 파일을 직접 수정.
"""
import os

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

ECOS_API_KEY = os.environ.get("ECOS_API_KEY", "")
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

BITHUMB_API_URL = "https://api.bithumb.com/public"

DB_PATH = os.environ.get("PREDICT_DB_PATH", "predict.db")

RSS_FEEDS_KR = {
    "hankyung_finance": "https://www.hankyung.com/feed/finance",
    "etoday_economy": "https://rss.etoday.co.kr/eto_economy.xml",
    "mk_economy": "https://www.mk.co.kr/rss/30100041/",
}

RSS_FEEDS_GLOBAL = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "reuters_markets": "https://feeds.reuters.com/reuters/marketsNews",
    "cnbc_economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "cnbc_finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "marketwatch_top": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "wsj_markets": "https://feeds.a]wsj.com/rss/RSSMarketsMain.xml",
    "ft_markets": "https://www.ft.com/markets?format=rss",
    "fed_press": "https://www.federalreserve.gov/feeds/press_all.xml",
}

CACHE_TTL_HOURS = 6
MAX_NEWS_PER_FEED = 20
PREDICTION_HISTORY_WEEKS = 8

DISCLAIMER = (
    "본 정보는 정보 제공 목적이며 투자 권유가 아닙니다. "
    "This is for informational purposes only, not investment advice. "
    "모든 투자 책임은 사용자에게 있습니다."
)
