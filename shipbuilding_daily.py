"""
조선업 일일 동향 자동 수집 프로그램 (무료 버전)
RSS 피드에서 최근 24시간 조선/해운 뉴스를 수집해 HTML 보고서를 생성합니다.
Claude API 없이 동작합니다.
"""

import sys
import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path
import webbrowser
import re

# ──────────────────────────────────────────────
# 뉴스 RSS 피드 목록 (모두 무료)
# ──────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Hellenic Shipping News",  "url": "https://www.hellenicshippingnews.com/feed/"},
    {"name": "Maritime Executive",      "url": "https://maritime-executive.com/rss"},
    {"name": "Seatrade Maritime",       "url": "https://www.seatrade-maritime.com/taxonomy/term/all/feed"},
    {"name": "Offshore Energy",         "url": "https://www.offshore-energy.biz/feed/"},
    {"name": "ShipInsight",             "url": "https://shipinsight.com/feed"},
    {"name": "Naval Architects",        "url": "https://www.rina.org.uk/rss/news.xml"},
]

# ──────────────────────────────────────────────
# 카테고리별 키워드
# ──────────────────────────────────────────────
CATEGORIES = {
    "🚢 신조 수주": [
        "newbuild", "new build", "order", "contract", "shipbuilding",
        "shipyard", "vessel order", "ship order",
    ],
    "⚓ 주요 조선사": [
        "Hyundai Heavy", "Samsung Heavy", "Daewoo", "HD KSOE", "DSME",
        "Hanwha Ocean", "Yangzijiang", "CSSC", "CSIC", "Mitsubishi",
        "Imabari", "HHI", "SHI",
    ],
    "🌱 친환경/기술": [
        "LNG", "ammonia", "methanol", "green shipping", "decarbonization",
        "carbon neutral", "emission", "IMO", "autonomous", "digital",
        "hydrogen", "VLCC", "LPG",
    ],
    "🏭 해운/물류": [
        "container ship", "bulk carrier", "tanker", "ro-ro", "ferry",
        "cruise", "freight", "charter", "fleet", "carrier",
    ],
    "📈 시장/금융": [
        "market", "price", "index", "Baltic", "BDI", "revenue",
        "profit", "earnings", "investment", "acquisition", "merger",
    ],
}

ALL_KEYWORDS = [kw for kws in CATEGORIES.values() for kw in kws]


def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in ALL_KEYWORDS)


def get_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, kws in CATEGORIES.items():
        if any(kw.lower() in text for kw in kws):
            return cat
    return "📰 기타"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ──────────────────────────────────────────────
# RSS 수집
# ──────────────────────────────────────────────
def fetch_articles(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for feed_info in RSS_FEEDS:
        print(f"  수집 중: {feed_info['name']} ...", end=" ", flush=True)
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
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

                articles.append({
                    "source":    feed_info["name"],
                    "title":     title,
                    "summary":   summary,
                    "link":      link,
                    "published": published.strftime("%Y-%m-%d %H:%M UTC") if published else "시각 불명",
                    "category":  get_category(title, summary),
                })
                count += 1

            print(f"OK {count}건")
        except Exception as e:
            print(f"FAIL 오류: {e}")

    # 중복 제목 제거
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique


# ──────────────────────────────────────────────
# HTML 보고서 생성
# ──────────────────────────────────────────────
def build_html(articles: list[dict], output_dir: Path) -> Path:
    today_str = datetime.now().strftime("%Y%m%d")
    filename  = output_dir / f"조선업동향_{today_str}.html"

    # 카테고리별 그룹핑
    grouped: dict[str, list] = {}
    for a in articles:
        grouped.setdefault(a["category"], []).append(a)

    # 통계 요약 배지
    stats_html = ""
    for cat, items in sorted(grouped.items()):
        stats_html += f'<span class="badge">{cat} {len(items)}건</span>'

    # 카테고리별 섹션
    sections_html = ""
    for cat in sorted(grouped.keys()):
        items = grouped[cat]
        cards = ""
        for a in items:
            cards += f"""
          <div class="card">
            <div class="card-meta">{a['source']} &nbsp;|&nbsp; {a['published']}</div>
            <a class="card-title" href="{a['link']}" target="_blank">{a['title']}</a>
            <div class="card-body">{a['summary']}</div>
          </div>"""
        sections_html += f"""
      <div class="section-title">{cat} <span class="count">{len(items)}</span></div>
      {cards}"""

    if not articles:
        sections_html = '<p style="color:#888;text-align:center;padding:40px">수집된 기사가 없습니다. 잠시 후 다시 시도해주세요.</p>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>조선업 일일 동향 – {datetime.now().strftime('%Y년 %m월 %d일')}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background: #f0f2f5; color: #222; }}
    header {{ background: linear-gradient(135deg,#003366,#0055a5); color: #fff; padding: 28px 36px; }}
    header h1 {{ font-size: 1.7rem; letter-spacing: -.5px; }}
    header p  {{ font-size: 0.88rem; opacity: .75; margin-top: 6px; }}
    .toolbar {{ padding: 14px 36px; background: #fff; border-bottom: 1px solid #e0e4ea;
                display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .badge {{ background: #e8f0fe; color: #0055a5; border-radius: 20px; padding: 4px 14px; font-size: 0.82rem; font-weight: 600; }}
    .translate-btn {{ margin-left: auto; background: #0055a5; color: #fff; border: none;
                      border-radius: 8px; padding: 8px 20px; font-size: 0.9rem; cursor: pointer;
                      font-family: inherit; display: flex; align-items: center; gap: 6px; }}
    .translate-btn:hover {{ background: #003f7f; }}
    .translate-btn:disabled {{ background: #aaa; cursor: not-allowed; }}
    .progress {{ display: none; font-size: 0.82rem; color: #0055a5; align-items: center; gap: 6px; }}
    .progress.show {{ display: flex; }}
    .spinner {{ width: 14px; height: 14px; border: 2px solid #e0e4ea; border-top-color: #0055a5;
                border-radius: 50%; animation: spin .7s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .container {{ max-width: 980px; margin: 28px auto; padding: 0 16px; }}
    .section-title {{ font-size: 1.1rem; font-weight: 700; color: #003366;
                      border-left: 4px solid #0055a5; padding-left: 12px;
                      margin: 32px 0 12px; display: flex; align-items: center; gap: 8px; }}
    .count {{ background: #0055a5; color: #fff; border-radius: 12px; padding: 1px 9px; font-size: 0.78rem; }}
    .card {{ background: #fff; border-radius: 10px; padding: 16px 20px; margin-bottom: 10px;
             box-shadow: 0 1px 5px rgba(0,0,0,.07); transition: box-shadow .15s; }}
    .card:hover {{ box-shadow: 0 4px 12px rgba(0,83,165,.12); }}
    .card-meta  {{ font-size: 0.76rem; color: #999; margin-bottom: 6px; }}
    .card-title {{ display: block; font-size: 1rem; font-weight: 600; color: #0055a5;
                   text-decoration: none; margin-bottom: 6px; line-height: 1.4; }}
    .card-title:hover {{ text-decoration: underline; }}
    .card-body  {{ font-size: 0.87rem; color: #555; line-height: 1.65; }}
    .ko-text    {{ color: #1a1a1a; }}
    footer {{ text-align: center; padding: 28px; font-size: 0.78rem; color: #bbb; }}
  </style>
</head>
<body>
  <header>
    <h1>조선업 일일 동향 보고서</h1>
    <p>기준: 최근 24시간 &nbsp;|&nbsp; 생성: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')} &nbsp;|&nbsp; 수집 기사: {len(articles)}건</p>
  </header>

  <div class="toolbar">
    {stats_html if stats_html else '<span style="color:#aaa">수집된 기사 없음</span>'}
    <button class="translate-btn" id="translateBtn" onclick="translateAll()">
      한국어로 번역하기
    </button>
    <span class="progress" id="progress"><span class="spinner"></span> <span id="progressText">번역 중...</span></span>
  </div>

  <div class="container">
    {sections_html}
  </div>

  <footer>shipbuilding_daily.py &nbsp;|&nbsp; 수집 출처: Hellenic Shipping News · Maritime Executive · Seatrade Maritime · Offshore Energy · ShipInsight</footer>

  <script>
  async function translateText(text) {{
    if (!text || !text.trim()) return text;
    const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q=' + encodeURIComponent(text);
    try {{
      const res = await fetch(url);
      const data = await res.json();
      return data[0].map(s => s[0]).join('');
    }} catch(e) {{
      return text;
    }}
  }}

  async function translateAll() {{
    const btn = document.getElementById('translateBtn');
    const progress = document.getElementById('progress');
    const progressText = document.getElementById('progressText');
    btn.disabled = true;
    btn.textContent = '번역 완료';
    progress.classList.add('show');

    const titles  = document.querySelectorAll('.card-title');
    const bodies  = document.querySelectorAll('.card-body');
    const total   = titles.length + bodies.length;
    let done = 0;

    async function doItem(el) {{
      const original = el.getAttribute('data-orig') || el.textContent;
      el.setAttribute('data-orig', original);
      const translated = await translateText(original);
      el.textContent = translated;
      el.classList.add('ko-text');
      done++;
      progressText.textContent = `번역 중... (${{done}}/${{total}})`;
      await new Promise(r => setTimeout(r, 80));
    }}

    for (const el of titles) await doItem(el);
    for (const el of bodies) await doItem(el);

    progress.classList.remove('show');
    progressText.textContent = '번역 중...';
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

    print("\n[2단계] HTML 보고서 생성 중...")
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    report_path = build_html(articles, output_dir)
    print(f"  → 저장: {report_path}")

    print("\n브라우저에서 보고서를 엽니다...")
    webbrowser.open(report_path.as_uri())
    print("\n[완료]")
    print("=" * 55)


if __name__ == "__main__":
    main()
