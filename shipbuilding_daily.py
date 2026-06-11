"""
DSR 일일 업계 동향 자동 수집 프로그램 (무료 버전)
강선 로프·섬유 로프 관련 해양·오프쇼어·크레인·광산 뉴스를 수집해 HTML 보고서를 생성합니다.
Claude API 없이 동작합니다.
"""

import sys
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path
import webbrowser
import re

# ──────────────────────────────────────────────
# 로깅 설정 — 콘솔(INFO) + 파일(DEBUG) 동시 출력
# ──────────────────────────────────────────────
LOG_PATH = Path(__file__).parent / "logs" / f"dsr_{datetime.now().strftime('%Y%m%d')}.log"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8-sig"), # 파일: DEBUG 이상 전부 (BOM 포함, 메모장 호환)
        logging.StreamHandler(sys.stdout),                  # 콘솔: INFO 이상만
    ],
)
# 콘솔 핸들러만 INFO로 제한
logging.getLogger().handlers[1].setLevel(logging.INFO)

log = logging.getLogger("dsr")

# ──────────────────────────────────────────────
# 한국어 번역 (Python 서버사이드, 무료)
# ──────────────────────────────────────────────
def translate_ko(text: str) -> str:
    """영문 텍스트를 한국어로 번역. 실패 시 원문 반환."""
    if not text or not text.strip():
        return text
    if re.search(r"[가-힣]", text):   # 이미 한글 포함 → 생략
        return text
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               "?client=gtx&sl=en&tl=ko&dt=t&q=" + urllib.parse.quote(text))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as res:
            data = json.loads(res.read())
            return "".join(seg[0] for seg in data[0] if seg[0])
    except urllib.error.URLError as e:
        log.warning("번역 네트워크 오류 (원문 유지): %s | 텍스트: %.40s", e.reason, text)
        return text
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        log.warning("번역 응답 파싱 오류 (원문 유지): %s | 텍스트: %.40s", e, text)
        return text
    except Exception as e:
        log.warning("번역 알 수 없는 오류 (원문 유지): %s | 텍스트: %.40s", e, text)
        return text


def translate_articles(articles: list[dict]) -> list[dict]:
    """수집된 기사의 제목·요약을 한국어로 번역."""
    total   = len(articles)
    failed  = 0
    for i, a in enumerate(articles, 1):
        print(f"  번역 중 ({i}/{total}): {a['title'][:40]}...", end="\r", flush=True)
        orig_title   = a["title"]
        orig_summary = a["summary"]
        a["title"]   = translate_ko(a["title"])
        a["summary"] = translate_ko(a["summary"])
        if a["title"] == orig_title:        # 번역 안 된 경우
            failed += 1
            log.debug("번역 실패 (원문 유지): %s", orig_title[:60])
    print(" " * 70, end="\r")
    if failed:
        log.warning("번역 실패 %d건 / 전체 %d건 — 해당 기사는 원문으로 저장됨", failed, total)
    else:
        log.info("번역 완료 %d건", total)
    return articles

# ──────────────────────────────────────────────
# 뉴스 RSS 피드 목록 (모두 무료) — DSR 사업 영역 최적화
# ──────────────────────────────────────────────
RSS_FEEDS = [
    # 해양·오프쇼어 (주요 수요처)
    {"name": "Offshore Energy",         "url": "https://www.offshore-energy.biz/feed/"},
    {"name": "Hellenic Shipping News",  "url": "https://www.hellenicshippingnews.com/feed/"},
    {"name": "Maritime Executive",      "url": "https://maritime-executive.com/rss"},
    {"name": "Seatrade Maritime",       "url": "https://www.seatrade-maritime.com/taxonomy/term/all/feed"},
    # 오프쇼어·에너지 산업
    {"name": "Rigzone",                 "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx"},
    {"name": "Upstream Online",         "url": "https://www.upstreamonline.com/rss"},
    # 해상풍력 전문
    {"name": "4C Offshore",             "url": "https://www.4coffshore.com/rss/news.xml"},
    {"name": "Recharge News",           "url": "https://www.rechargenews.com/rss"},
    {"name": "Wind Energy Update",      "url": "https://www.windenergyupdate.com/rss.xml"},
    # 조선·해운 (국내외 조선소 동향)
    {"name": "Korea Shipping Gazette",  "url": "https://www.ksg.co.kr/rss/rss.xml"},
    {"name": "ShipandBunker",           "url": "https://shipandbunker.com/news/rss"},
    {"name": "TradeWinds",              "url": "https://www.tradewindsnews.com/rss"},
    # 항만·크레인 (하역 장비 수요처)
    {"name": "Port Technology",         "url": "https://www.porttechnology.org/feed/"},
    # 광산·중공업 (산업용 와이어로프 수요처)
    {"name": "Mining.com",              "url": "https://www.mining.com/feed/"},
    {"name": "International Mining",    "url": "https://im-mining.com/feed/"},
]

# ──────────────────────────────────────────────
# DSR 핵심 카테고리별 키워드
# ──────────────────────────────────────────────
CATEGORIES = {
    "🏷️ DSR 자사 제품": [
        # 섬유로프 브랜드
        "SuperMax", "Super Max",
        # 강선로프 브랜드
        "PowerMax", "Power Max", "Power Rope", "SAS rope", "Powerflex",
        # 경강선 제품
        "OT Wire", "IT Wire", "Sprex", "Hirex",
        # 법인명
        "DSR Wire", "DSR Corp", "DSR Vina", "DSR제강", "DSR주식회사",
    ],
    "🪢 와이어로프·강선": [
        "wire rope", "steel wire rope", "wire strand", "wire cable",
        "hoist rope", "crane rope", "guy wire", "guy rope",
        "mining rope", "elevator rope", "lift rope",
        "WireCo", "Bridon", "Bekaert", "Casar", "Usha Martin",
        "wire rod", "high carbon wire", "spring wire", "piano wire",
    ],
    "🧵 섬유로프·합성로프": [
        "fiber rope", "fibre rope", "synthetic rope", "HMPE", "UHMWPE",
        "Dyneema", "Spectra", "polyester rope", "nylon rope", "polypropylene rope",
        "aramid rope", "Kevlar rope", "high-performance rope",
        "Lankhorst", "Samson Rope", "Cortland", "Yale Cordage",
    ],
    "⚓ 계류·앵커링": [
        "mooring rope", "mooring line", "mooring system", "mooring chain",
        "anchor handling", "anchor line", "anchor rope",
        "FPSO mooring", "buoy mooring", "dynamic positioning",
        "towing rope", "tow line", "towline",
    ],
    "🏗️ 크레인·리프팅": [
        "crane wire", "lifting rope", "sling", "rigging",
        "offshore crane", "subsea lifting", "heavy lift",
        "hoist", "winch", "capstan", "drawworks",
        "load line", "running rigging", "standing rigging",
    ],
    "🚢 조선·조선소": [
        # 국내 조선소
        "현대중공업", "삼성중공업", "한화오션", "대우조선해양",
        "HD현대", "현대미포조선", "현대삼호중공업",
        "STX조선", "한진중공업", "케이조선", "HJ중공업",
        # 글로벌 조선소
        "shipbuilding", "shipyard", "drydock", "dry dock",
        "newbuild", "new build", "vessel order", "ship order",
        "keel laying", "launch ceremony", "delivery",
        # 선종 (와이어로프 수요와 연결)
        "bulk carrier", "container ship", "LNG carrier",
        "tanker", "VLCC", "cruise ship", "car carrier", "PCTC",
        "naval vessel", "offshore support vessel", "OSV",
        # 조선 기자재
        "marine equipment", "ship equipment", "outfitting",
        "mooring equipment", "deck equipment", "winch system",
    ],
    "🌬️ 해상풍력": [
        "offshore wind", "offshore wind farm", "offshore wind turbine",
        "floating wind", "floating offshore wind", "FOWT",
        "wind turbine installation", "wind turbine cable", "wind turbine mooring",
        "wind farm mooring", "inter-array cable", "export cable",
        "monopile", "jacket foundation", "wind installation vessel",
        "dynamic cable", "wind energy", "offshore wind project",
        "wind park", "OWF", "HVDC offshore",
    ],
    "🛢️ 오프쇼어·에너지": [
        "offshore", "FPSO", "semi-submersible", "drillship", "jack-up",
        "deepwater", "subsea", "umbilical", "riser",
        "oil rig", "platform", "floating production",
    ],
    "⛏️ 광산·산업": [
        "mining", "mine hoist", "shaft", "dragline",
        "conveyor belt", "bridge cable", "suspension bridge",
        "elevator", "escalator",
        # 로프웨이
        "ropeway", "aerial ropeway", "tramway", "gondola lift",
        "cable car", "chairlift", "funicular", "aerial tramway",
        "material ropeway", "ore ropeway", "ski lift",
    ],
    "📊 시장·원자재": [
        "steel wire market", "rope market", "wire rod", "high carbon steel",
        "raw material", "steel price", "scrap price",
        "polyester price", "HMPE price", "fiber market",
    ],
    "📋 규정·인증": [
        "ISO 2408", "EN 12385", "API", "DNV", "Lloyd", "ABS",
        "certification", "type approval", "inspection",
        "breaking load", "minimum breaking", "safety factor",
        "OSHA", "lifting standard", "rope standard",
    ],
}

ALL_KEYWORDS = [kw for kws in CATEGORIES.values() for kw in kws]

# ──────────────────────────────────────────────
# 경쟁사 키워드 (별도 탭으로 분리 표시)
# ──────────────────────────────────────────────
COMPETITOR_KEYWORDS = [
    # 고려제강 / Kiswire
    "Kiswire", "고려제강", "Koryo Wire",
    # 글로벌 직접 경쟁사
    "Bridon-Bekaert", "Bridon", "Bekaert",
    "WireCo", "WireCo World",
    "Usha Martin",
    "Tokyo Rope", "Tokyo Seiko",
    "Teufelberger",
    "Pfeifer", "Drako",
    "Lankhorst", "Lankhorst Euronete",
    "Samson Rope", "Samson Corporation",
    "Cortland Cable", "Cortland Limited",
    "Fasten Group", "Langshan",
    "Juli Sling", "Juli Group",
    "Casar", "Gustav Wolf",
    "Redaelli", "Trefileurope",
]

COMPETITOR_CATEGORIES = {
    "🏢 고려제강·Kiswire": ["Kiswire", "고려제강", "Koryo Wire"],
    "🌐 글로벌 경쟁사": [
        "Bridon", "Bekaert", "WireCo", "Usha Martin",
        "Tokyo Rope", "Teufelberger", "Pfeifer", "Drako",
        "Lankhorst", "Samson Rope", "Cortland", "Fasten Group",
        "Langshan", "Juli Sling",
    ],
}

# DSR 사업과 무관한 기사 제외 키워드
EXCLUDE_KEYWORDS = [
    "stock market", "stock price", "equity", "IPO", "bond yield",
    "interest rate", "inflation", "GDP", "cryptocurrency",
    "healthcare", "medical", "pharmaceutical",
    "retail", "e-commerce", "consumer goods",
    "election", "politics", "military strike",
    "natural gas price", "crude futures", "oil price forecast",
]


def is_competitor(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in COMPETITOR_KEYWORDS)


def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    if any(kw.lower() in text for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw.lower() in text for kw in ALL_KEYWORDS) or is_competitor(title, summary)


def get_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, kws in CATEGORIES.items():
        if any(kw.lower() in text for kw in kws):
            return cat
    return "📰 기타"


def get_competitor_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, kws in COMPETITOR_CATEGORIES.items():
        if any(kw.lower() in text for kw in kws):
            return cat
    return "🌐 글로벌 경쟁사"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ──────────────────────────────────────────────
# RSS 수집
# ──────────────────────────────────────────────
def fetch_articles(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    feed_ok = feed_fail = 0
    for feed_info in RSS_FEEDS:
        name = feed_info["name"]
        print(f"  수집 중: {name} ...", end=" ", flush=True)
        try:
            feed = feedparser.parse(feed_info["url"], request_headers={"User-Agent": "Mozilla/5.0"})

            # feedparser는 네트워크 오류도 예외 없이 반환 → status/bozo로 확인
            if getattr(feed, "bozo", False) and not feed.entries:
                raise ValueError(feed.bozo_exception)

            count = 0
            for entry in feed.entries:
                try:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                    if published and published < cutoff:
                        continue

                    title   = getattr(entry, "title", "").strip()
                    summary = strip_html(getattr(entry, "summary", ""))[:400]
                    link    = getattr(entry, "link", "")

                    if not title or not is_relevant(title, summary):
                        continue

                    comp = is_competitor(title, summary)
                    articles.append({
                        "source":        name,
                        "title":         title,
                        "summary":       summary,
                        "link":          link,
                        "published":     published.strftime("%Y-%m-%d %H:%M UTC") if published else "시각 불명",
                        "category":      get_competitor_category(title, summary) if comp else get_category(title, summary),
                        "is_competitor": comp,
                    })
                    count += 1
                except Exception as entry_err:
                    log.debug("[%s] 항목 파싱 오류 (건너뜀): %s", name, entry_err)

            print(f"OK {count}건")
            log.debug("[%s] %d건 수집", name, count)
            feed_ok += 1

        except ValueError as e:
            print(f"FAIL (피드 파싱 오류)")
            log.warning("[%s] 피드 파싱 오류: %s", name, e)
            feed_fail += 1
        except Exception as e:
            print(f"FAIL (오류: {type(e).__name__})")
            log.error("[%s] 수집 실패: %s", name, e, exc_info=True)
            feed_fail += 1

    log.info("피드 수집 완료 — 성공 %d / 실패 %d", feed_ok, feed_fail)

    # 완전 일치 + 유사 중복 제거 (#4)
    def title_words(title: str) -> set:
        return {w for w in re.sub(r"[^\w\s]", "", title.lower()).split() if len(w) >= 3}

    unique = []
    for a in articles:
        words = title_words(a["title"])
        is_dup = False
        for kept in unique:
            kept_words = title_words(kept["title"])
            if not words or not kept_words:
                continue
            overlap = len(words & kept_words) / min(len(words), len(kept_words))
            if overlap >= 0.5:
                is_dup = True
                break
        if not is_dup:
            unique.append(a)

    return unique


# ──────────────────────────────────────────────
# DSR 중심 분석 헬퍼
# ──────────────────────────────────────────────
_CAT_SCORE = {
    "DSR 자사": 10, "와이어로프": 5, "섬유로프": 5,
    "계류":     4,  "해상풍력":  4,  "조선":     4,
    "크레인":   3,  "오프쇼어": 3,  "광산":     3,
    "시장":     2,  "규정":     1,
}

def score_article(a: dict) -> int:
    cat = a["category"]
    for k, v in _CAT_SCORE.items():
        if k in cat:
            return v
    return 1


def dsr_relevance(a: dict) -> str:
    cat = a["category"]
    if "DSR 자사" in cat:
        return "자사 제품이 직접 언급된 기사 — 즉시 내용 확인 필요"
    if "와이어로프" in cat:
        return "DSR 주력 제품인 와이어로프·강선 시장과 직접 연관"
    if "섬유로프" in cat:
        return "DSR 섬유로프(SuperMax 등) 제품군 시장·기술 동향과 연관"
    if "조선" in cat:
        return "조선소는 DSR 크레인 와이어로프·계류 로프·리깅 등 선박 건조·의장 단계의 주요 수요처"
    if "해상풍력" in cat:
        return "해상풍력 설치·계류는 DSR 와이어로프·섬유로프(FOWT 계류·앵커)·강선의 핵심 신성장 시장"
    if "계류" in cat:
        return "계류 로프·앵커링 시스템 주요 수요처 동향 — 납품 시장에 영향"
    if "크레인" in cat:
        return "크레인용 와이어로프 수요처 동향 — 산업 수요 예측에 활용"
    if "오프쇼어" in cat:
        return "오프쇼어 산업은 DSR 계류·앵커링·드릴링 로프의 핵심 수요처"
    if "광산" in cat:
        return "광산용 와이어로프(샤프트 로프·드래그라인 등) 수요처 동향"
    if "시장" in cat:
        return "원자재(와이어 로드·폴리에스터) 가격 변동 — DSR 생산 원가에 직접 영향"
    if "규정" in cat:
        return "로프 국제 규정·인증 변경 — 제품 품질 기준·납품 요건에 영향"
    return "와이어로프·섬유로프 업계 동향으로 DSR 사업 전반과 연관"


def action_recommendation(a: dict) -> str:
    cat  = a["category"]
    text = (a["title"] + " " + a["summary"]).lower()
    pos  = any(w in text for w in ["order","contract","award","new project","expand","growth","demand","install","launch","record"])
    neg  = any(w in text for w in ["accident","failure","recall","ban","shortage","delay","cancel","incident"])
    up   = any(w in text for w in ["surge","rise","increase","soar","high","record high"])
    down = any(w in text for w in ["fall","drop","decline","low","decrease","slump"])

    if "DSR 자사" in cat:
        return "🔴 즉시 대응 — 마케팅·영업팀 내용 공유 및 모니터링 강화"
    if "와이어로프" in cat:
        if pos:  return "🟢 기회 — 영업팀에 수요 확대 신호 공유, 신규 수주 검토"
        if neg:  return "🟡 리스크 — 시장 위축 원인 분석, 영업 전략 재검토"
        return "📌 모니터링 — 기술·영업팀 공유, 제품 경쟁력 점검"
    if "섬유로프" in cat:
        if pos:  return "🟢 기회 — 섬유로프 영업팀 리드 확인, 수주 가능성 검토"
        return "📌 모니터링 — 섬유로프 사업부 공유 및 시장 동향 파악"
    if "조선" in cat:
        if pos:  return "🟢 기회 — 신조 수주 확대 → 조선소 크레인 와이어·의장 로프 수요 증가, 영업팀 즉시 공유"
        if neg:  return "🟡 주의 — 조선 경기 위축 신호, 수요 감소 가능성 모니터링"
        return "📌 모니터링 — 국내외 조선소 수주·생산 동향 파악, 영업팀 공유"
    if "해상풍력" in cat:
        if pos:  return "🟢 기회 — FOWT 계류·앵커링·설치선 와이어 납품 기회 검토, 프로젝트 리스트 확인"
        return "📌 모니터링 — 해상풍력 프로젝트 동향 파악, 영업·기획팀 공유"
    if "계류" in cat:
        if pos:  return "🟢 기회 — 프로젝트 수주 가능성 검토, 영업팀 즉시 공유"
        return "📌 모니터링 — 계류 관련 영업팀 공유, 납품 기회 탐색"
    if "크레인" in cat:
        if pos:  return "🟢 기회 — 산업용 와이어로프 납품 기회 영업팀 검토"
        return "📌 모니터링 — 산업 수요 변화 파악, 영업팀 공유"
    if "오프쇼어" in cat:
        if pos:  return "🟢 기회 — 계류·앵커링 제품 수주 기회 적극 검토"
        return "📌 모니터링 — 오프쇼어 수요 변화 추적, 영업팀 공유"
    if "광산" in cat:
        if pos:  return "🟢 기회 — 광산용 로프 공급 기회 검토, 관련 영업팀 공유"
        return "📌 모니터링 — 광산 수요 예측 참고"
    if "시장" in cat:
        if up:   return "🟡 주의 — 원자재 가격 상승 → 구매팀 재고 전략·판가 조정 검토"
        if down: return "📌 참고 — 원가 절감 기회, 경쟁사 덤핑 가능성 모니터링"
        return "📌 참고 — 구매·영업팀 공유 및 전략 수립 참고"
    if "규정" in cat:
        return "🟡 주의 — 품질·인증팀 검토, 제품 인증 계획 업데이트 필요"
    return "📌 참고 — 관련 부서 공유 검토"


# ──────────────────────────────────────────────
# HTML 보고서 생성
# ──────────────────────────────────────────────
def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else url


def _card_html(a: dict, rank: int = 0, is_comp: bool = False) -> str:
    comp_cls   = " comp" if is_comp else ""
    rank_badge = f'<span class="rank-badge">#{rank}</span>' if rank else ""
    rel        = dsr_relevance(a)
    act        = action_recommendation(a)
    domain     = _domain(a["link"])
    comp_insights = f"""
        <div class="insight-row">
          <div class="insight act"><span class="ilabel">대응 방안</span><span class="itext">{act}</span></div>
        </div>""" if not is_comp else ""
    return f"""
    <div class="card{comp_cls}">
      <div class="card-top">
        <div class="card-meta">
          <span class="card-src">{a['source']}</span>
          <span class="card-date">{a['published']}</span>
        </div>
        {rank_badge}
      </div>
      <a class="card-title" href="{a['link']}" target="_blank">{a['title']}</a>
      <div class="card-body">{a['summary']}</div>
      <div class="card-insights">
        <div class="insight-row">
          <div class="insight rel"><span class="ilabel">DSR 연관</span><span class="itext">{rel}</span></div>
        </div>{comp_insights}
      </div>
      <div class="card-source-row">
        <span class="src-label">출처</span>
        <a class="src-link" href="{a['link']}" target="_blank">{domain}</a>
      </div>
    </div>"""


def make_cards(items: list[dict], is_comp: bool = False) -> str:
    html = '<div class="grid">'
    for a in items:
        html += _card_html(a, is_comp=is_comp)
    html += '</div>'
    return html


def make_top5_html(dsr_articles: list[dict]) -> str:
    if not dsr_articles:
        return ""
    top5 = sorted(dsr_articles, key=score_article, reverse=True)[:5]
    cards = "".join(_card_html(a, rank=i+1) for i, a in enumerate(top5))
    return f"""
    <div class="top5-section">
      <div class="top5-header">
        <span class="top5-icon">⭐</span>
        <span class="top5-title">오늘의 DSR 핵심 기사 Top 5</span>
        <span class="top5-sub">관련도 높은 순으로 자동 선별</span>
      </div>
      <div class="grid">{cards}</div>
    </div>"""


# 업계 동향 탭 섹션 표시 순서
SECTION_ORDER = [
    "🚢 조선·조선소",
    "🌬️ 해상풍력",
    "🛢️ 오프쇼어·에너지",
    "⛏️ 광산·산업",
    "📋 규정·인증",
    "⚓ 계류·앵커링",
    "🏗️ 크레인·리프팅",
    "🪢 와이어로프·강선",
    "🧵 섬유로프·합성로프",
    "📊 시장·원자재",
    "🏷️ DSR 자사 제품",
]


def _ordered_cats(grouped: dict, order: list) -> list:
    ordered = [c for c in order if c in grouped]
    rest    = [c for c in sorted(grouped.keys()) if c not in order]
    return ordered + rest


def _sec_id(cat: str) -> str:
    """섹션 앵커 id — 알파벳·숫자·한글만 남김."""
    return "sec-" + re.sub(r"[^\w가-힣]", "", cat)


def make_sections(grouped: dict, is_comp: bool = False) -> str:
    comp_cls = " comp" if is_comp else ""
    html = ""
    cats = _ordered_cats(grouped, SECTION_ORDER) if not is_comp else sorted(grouped.keys())
    for cat in cats:
        items = grouped[cat]
        icon  = cat.split()[0] if cat else ""
        name  = cat[len(icon):].strip() if icon else cat
        sid   = _sec_id(cat)
        html += f"""
      <div class="section-header{comp_cls}" id="{sid}">
        <span class="section-icon">{icon}</span>
        <span class="section-name">{name}</span>
        <span class="section-cnt">{len(items)}</span>
      </div>
      {make_cards(items, is_comp)}"""
    return html or '<div class="empty"><div class="empty-icon">📭</div><div class="empty-text">수집된 기사가 없습니다.</div></div>'


def build_html(articles: list[dict], output_dir: Path) -> Path:
    today_str = datetime.now().strftime("%Y%m%d")
    filename  = output_dir / f"DSR동향_{today_str}.html"

    # DSR 업계 기사 / 경쟁사 기사 분리
    dsr_articles  = [a for a in articles if not a["is_competitor"]]
    comp_articles = [a for a in articles if a["is_competitor"]]

    # 각각 카테고리별 그룹핑
    dsr_grouped: dict[str, list] = {}
    for a in dsr_articles:
        dsr_grouped.setdefault(a["category"], []).append(a)

    comp_grouped: dict[str, list] = {}
    for a in comp_articles:
        comp_grouped.setdefault(a["category"], []).append(a)

    # 섹션 HTML
    dsr_sections  = make_sections(dsr_grouped, is_comp=False)
    comp_sections = make_sections(comp_grouped, is_comp=True)

    # 필터 칩 — SECTION_ORDER 순서 + 클릭 시 해당 섹션으로 스크롤
    def chips(grouped, is_comp=False):
        cls  = " comp" if is_comp else ""
        cats = _ordered_cats(grouped, SECTION_ORDER) if not is_comp else sorted(grouped.keys())
        parts = []
        for cat in cats:
            sid  = _sec_id(cat)
            icon = cat.split()[0] if cat else ""
            name = cat[len(icon):].strip() if icon else cat
            cnt  = len(grouped[cat])
            parts.append(
                f'<span class="chip{cls}" onclick="jumpTo(\'{sid}\')">'
                f'{icon} {name} <strong>{cnt}</strong></span>'
            )
        return "".join(parts)

    dsr_badges  = chips(dsr_grouped)  or '<span style="color:#aaa;font-size:.8rem">수집된 기사 없음</span>'
    comp_badges = chips(comp_grouped, is_comp=True) or '<span style="color:#aaa;font-size:.8rem">수집된 기사 없음</span>'

    top5_html = make_top5_html(dsr_articles)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DSR Daily Brief · {datetime.now().strftime('%Y.%m.%d')}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --blue:      #1565C0;
      --blue-lt:   #E3F0FF;
      --blue-dk:   #0D3F7A;
      --red:       #B71C1C;
      --red-lt:    #FFEBEE;
      --gold:      #F57F17;
      --gold-lt:   #FFF8E1;
      --green:     #2E7D32;
      --green-lt:  #E8F5E9;
      --gray-bg:   #F4F6FA;
      --gray-bdr:  #DDE2EE;
      --gray-text: #6B7280;
      --white:     #FFFFFF;
      --text:      #1A1F2E;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Inter', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
            background: var(--gray-bg); color: var(--text); min-height: 100vh; }}

    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    /* ── 상단 바 ── */
    .topbar {{
      background: linear-gradient(100deg, #0D3F7A 0%, #1565C0 60%, #1976D2 100%);
      padding: 0 40px;
      display: flex; align-items: center; justify-content: space-between;
      height: 64px; position: sticky; top: 0; z-index: 100;
      box-shadow: 0 2px 12px rgba(13,63,122,.35);
    }}
    .topbar-left {{ display: flex; align-items: center; gap: 14px; }}
    .topbar-logo {{ width: 36px; height: 36px; background: rgba(255,255,255,.18);
                    border-radius: 9px; display: flex; align-items: center; justify-content: center;
                    font-weight: 800; font-size: 0.75rem; color: #fff; letter-spacing: 1px;
                    border: 1.5px solid rgba(255,255,255,.3); }}
    .topbar-title {{ color: #fff; font-size: 1.05rem; font-weight: 700; letter-spacing: -.3px; }}
    .topbar-date  {{ color: rgba(255,255,255,.6); font-size: 0.8rem; }}
    .topbar-right {{ display: flex; align-items: center; gap: 10px; }}
    .stat-chip {{ background: rgba(255,255,255,.13); color: rgba(255,255,255,.92);
                  border-radius: 20px; padding: 4px 14px; font-size: 0.78rem; font-weight: 500;
                  border: 1px solid rgba(255,255,255,.18); }}
    .stat-chip b {{ font-weight: 700; }}

    /* ── 탭 네비 ── */
    .tab-nav {{
      background: var(--white); border-bottom: 1px solid var(--gray-bdr);
      display: flex; align-items: stretch; padding: 0 32px;
      position: sticky; top: 64px; z-index: 99;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
    }}
    .tab {{
      padding: 0 24px; height: 50px; font-size: 0.88rem; font-weight: 600;
      cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -1px;
      color: var(--gray-text); display: flex; align-items: center; gap: 8px;
      transition: color .18s, border-color .18s; user-select: none; white-space: nowrap;
    }}
    .tab:hover {{ color: var(--blue); }}
    .tab.active {{ color: var(--blue); border-bottom-color: var(--blue); }}
    .tab.comp:hover {{ color: var(--red); }}
    .tab.comp.active {{ color: var(--red); border-bottom-color: var(--red); }}
    .tab-pill {{ font-size: 0.72rem; font-weight: 700; border-radius: 20px;
                  padding: 2px 9px; background: var(--blue-lt); color: var(--blue); }}
    .tab.comp .tab-pill {{ background: var(--red-lt); color: var(--red); }}

    /* ── 패널 ── */
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}

    /* ── 필터 바 ── */
    .filter-bar {{
      background: var(--white); border-bottom: 1px solid var(--gray-bdr);
      padding: 10px 40px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    }}
    .filter-label {{ font-size: 0.72rem; font-weight: 700; color: var(--gray-text);
                     text-transform: uppercase; letter-spacing: .6px; margin-right: 4px; }}
    .chip {{ font-size: 0.75rem; font-weight: 600; border-radius: 20px;
              padding: 4px 13px; background: var(--blue-lt); color: var(--blue);
              transition: all .18s; cursor: pointer; user-select: none; }}
    .chip:hover {{ background: var(--blue); color: #fff; transform: translateY(-1px);
                   box-shadow: 0 2px 8px rgba(21,101,192,.25); }}
    .chip:active {{ transform: translateY(0); }}
    .chip.comp {{ background: var(--red-lt); color: var(--red); }}
    .chip.comp:hover {{ background: var(--red); color: #fff;
                        box-shadow: 0 2px 8px rgba(183,28,28,.25); }}
    /* 클릭된 섹션 헤더 잠깐 강조 */
    .section-header.highlight {{ animation: hl .8s ease; }}
    @keyframes hl {{
      0%   {{ background: rgba(21,101,192,.12); border-radius: 8px; }}
      100% {{ background: transparent; }}
    }}

    /* ── 페이지 래퍼 ── */
    .page {{ max-width: 1160px; margin: 0 auto; padding: 28px 24px 56px; }}

    /* ── Top 5 섹션 ── */
    .top5-section {{
      background: linear-gradient(135deg, var(--gold-lt) 0%, #FFFDE7 100%);
      border: 1.5px solid #FFE082; border-radius: 16px;
      padding: 20px 24px 24px; margin-bottom: 36px;
    }}
    .top5-header {{
      display: flex; align-items: center; gap: 10px; margin-bottom: 18px;
    }}
    .top5-icon {{ font-size: 1.3rem; }}
    .top5-title {{ font-size: 1rem; font-weight: 700; color: var(--gold); }}
    .top5-sub {{ font-size: 0.75rem; color: #A0522D; margin-left: 6px;
                  background: rgba(245,127,23,.1); padding: 2px 10px; border-radius: 20px; }}
    .rank-badge {{
      font-size: 0.72rem; font-weight: 800; color: var(--gold);
      background: rgba(245,127,23,.12); border: 1px solid rgba(245,127,23,.3);
      border-radius: 20px; padding: 2px 9px; white-space: nowrap;
    }}

    /* ── 섹션 헤더 ── */
    .section-header {{
      display: flex; align-items: center; gap: 10px;
      margin: 36px 0 14px; padding-bottom: 10px;
      border-bottom: 2px solid var(--blue-lt);
    }}
    .section-header.comp {{ border-bottom-color: var(--red-lt); }}
    .section-icon {{ font-size: 1.1rem; }}
    .section-name {{ font-size: 0.95rem; font-weight: 700; color: var(--blue-dk); }}
    .section-header.comp .section-name {{ color: var(--red); }}
    .section-cnt {{ margin-left: auto; font-size: 0.72rem; font-weight: 700;
                     background: var(--blue); color: #fff; border-radius: 20px; padding: 2px 10px; }}
    .section-header.comp .section-cnt {{ background: var(--red); }}

    /* ── 카드 그리드 ── */
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }}

    .card {{
      background: var(--white); border-radius: 12px; padding: 18px 20px 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 8px rgba(0,0,0,.04);
      transition: transform .15s, box-shadow .15s;
      border-top: 3px solid transparent;
      display: flex; flex-direction: column; gap: 0;
    }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 22px rgba(21,101,192,.13);
                   border-top-color: var(--blue); }}
    .card.comp:hover {{ box-shadow: 0 6px 22px rgba(183,28,28,.11); border-top-color: var(--red); }}

    .card-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }}
    .card-meta {{ display: flex; align-items: center; gap: 8px; }}
    .card-src  {{ font-size: 0.68rem; font-weight: 700; color: var(--gray-text);
                  text-transform: uppercase; letter-spacing: .5px; }}
    .card-date {{ font-size: 0.68rem; color: #B0BEC5; }}

    .card-title {{ display: block; font-size: 0.91rem; font-weight: 700; color: var(--blue);
                   text-decoration: none; line-height: 1.55; margin-bottom: 8px; }}
    .card.comp .card-title {{ color: var(--red); }}
    .card-title:hover {{ text-decoration: underline; }}

    .card-body {{ font-size: 0.81rem; color: #546E7A; line-height: 1.7; margin-bottom: 12px;
                  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
                  overflow: hidden; }}
    .ko-text {{ color: var(--text) !important; }}

    /* ── 인사이트 박스 ── */
    .card-insights {{ border-top: 1px solid var(--gray-bdr); padding-top: 10px;
                       display: flex; flex-direction: column; gap: 6px; }}
    .insight-row {{ display: flex; flex-direction: column; gap: 6px; }}
    .insight {{ display: flex; flex-direction: column; gap: 2px; padding: 7px 10px;
                border-radius: 8px; }}
    .insight.rel {{ background: var(--blue-lt); }}
    .insight.act {{ background: var(--green-lt); }}
    .card.comp .insight.rel {{ background: var(--red-lt); }}
    .ilabel {{ font-size: 0.65rem; font-weight: 800; text-transform: uppercase;
               letter-spacing: .6px; color: var(--gray-text); margin-bottom: 1px; }}
    .insight.rel .ilabel {{ color: var(--blue); }}
    .insight.act .ilabel {{ color: var(--green); }}
    .card.comp .insight.rel .ilabel {{ color: var(--red); }}
    .itext {{ font-size: 0.78rem; font-weight: 500; line-height: 1.5; color: var(--text); }}

    /* ── 카드 출처 행 ── */
    .card-source-row {{
      display: flex; align-items: center; gap: 6px;
      margin-top: 8px; padding-top: 8px;
      border-top: 1px dashed var(--gray-bdr);
    }}
    .src-label {{
      font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .5px; color: var(--gray-text);
      background: var(--gray-bg); border-radius: 4px; padding: 1px 6px;
    }}
    .src-link {{
      font-size: 0.72rem; color: var(--gray-text); text-decoration: none;
      word-break: break-all;
    }}
    .src-link:hover {{ color: var(--blue); text-decoration: underline; }}
    .card.comp .src-link:hover {{ color: var(--red); }}

    /* ── 빈 상태 ── */
    .empty {{ text-align: center; padding: 64px 20px; color: var(--gray-text); }}
    .empty-icon {{ font-size: 2.5rem; margin-bottom: 12px; }}
    .empty-text {{ font-size: 0.9rem; }}

    /* ── 푸터 ── */
    footer {{ text-align: center; padding: 20px; font-size: 0.72rem;
              color: #B0BEC5; border-top: 1px solid var(--gray-bdr); background: var(--white); }}
  </style>
</head>
<body>

  <div class="topbar">
    <div class="topbar-left">
      <div class="topbar-logo">DSR</div>
      <span class="topbar-title">Daily Brief</span>
      <span class="topbar-date">&nbsp;{datetime.now().strftime('%Y년 %m월 %d일')}</span>
    </div>
    <div class="topbar-right">
      <div class="stat-chip">전체 <b>{len(articles)}</b>건 &nbsp;|&nbsp; 업계 <b>{len(dsr_articles)}</b> · 경쟁사 <b>{len(comp_articles)}</b></div>
      <div class="stat-chip">🇰🇷 한국어</div>
    </div>
  </div>

  <div class="tab-nav">
    <div class="tab active" id="tab-dsr" onclick="switchTab('dsr')">
      업계 동향 <span class="tab-pill">{len(dsr_articles)}</span>
    </div>
    <div class="tab comp" id="tab-comp" onclick="switchTab('comp')">
      경쟁사 동향 <span class="tab-pill">{len(comp_articles)}</span>
    </div>
  </div>

  <div class="tab-panel active" id="panel-dsr">
    <div class="filter-bar">
      <span class="filter-label">카테고리</span>
      {dsr_badges}
    </div>
    <div class="page">
      {top5_html}
      {dsr_sections}
    </div>
  </div>

  <div class="tab-panel" id="panel-comp">
    <div class="filter-bar">
      <span class="filter-label">경쟁사</span>
      {comp_badges}
    </div>
    <div class="page">{comp_sections}</div>
  </div>

  <footer>DSR Daily Brief &nbsp;·&nbsp; Offshore Energy · Hellenic Shipping News · Maritime Executive · Rigzone · Port Technology · Mining.com &nbsp;·&nbsp; {datetime.now().strftime('%Y.%m.%d %H:%M')} 생성</footer>

  <script>
  function switchTab(name) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.getElementById('panel-' + name).classList.add('active');
  }}

  function jumpTo(id) {{
    const el = document.getElementById(id);
    if (!el) return;
    const offset = 64 + 50 + 44 + 12;
    const top = el.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({{ top: top, behavior: 'smooth' }});
    setTimeout(() => {{
      el.classList.add('highlight');
      setTimeout(() => el.classList.remove('highlight'), 850);
    }}, 400);
  }}
  </script>
</body>
</html>"""

    filename.write_text(html, encoding="utf-8")
    return filename


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  조선업 일일 동향 수집 프로그램 (무료 버전)")
    print(f"  실행: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    print("\n[1단계] RSS 피드 수집 중...")
    articles = fetch_articles(hours=24)
    print(f"\n  → 총 {len(articles)}건 수집 완료")

    print("\n[2단계] 한국어 번역 중...")
    articles = translate_articles(articles)
    print(f"  → 번역 완료")

    print("\n[3단계] HTML 보고서 생성 중...")
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    report_path = build_html(articles, output_dir)
    print(f"  → 저장: {report_path}")
    print("     (모든 기사가 한국어로 저장됨)")

    print("\n브라우저에서 보고서를 엽니다...")
    webbrowser.open(report_path.as_uri())
    log.info("실행 완료 — 보고서: %s", report_path)
    print(f"\n[완료]  로그: {LOG_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("사용자가 실행을 중단했습니다.")
        sys.exit(0)
    except Exception as e:
        log.critical("프로그램 비정상 종료: %s", e, exc_info=True)
        print(f"\n[오류] 프로그램이 비정상 종료됐습니다.")
        print(f"  로그 파일: {LOG_PATH}")
        sys.exit(1)
