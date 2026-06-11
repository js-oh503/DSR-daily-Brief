"""
DSR 일일 업계 동향 자동 수집 프로그램 (무료 버전)
강선 로프·섬유 로프 관련 해양·오프쇼어·크레인·광산 뉴스를 수집해 HTML 보고서를 생성합니다.
Claude API 없이 동작합니다.
"""

import sys
import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path
import webbrowser
import re

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
    "🛢️ 오프쇼어·에너지": [
        "offshore", "FPSO", "semi-submersible", "drillship", "jack-up",
        "deepwater", "subsea", "umbilical", "riser",
        "oil rig", "platform", "floating production",
        "offshore wind", "wind turbine installation",
    ],
    "⛏️ 광산·산업": [
        "mining", "mine hoist", "shaft", "dragline",
        "conveyor belt", "aerial ropeway", "tramway",
        "elevator", "escalator", "bridge cable", "suspension bridge",
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

                comp = is_competitor(title, summary)
                articles.append({
                    "source":      feed_info["name"],
                    "title":       title,
                    "summary":     summary,
                    "link":        link,
                    "published":   published.strftime("%Y-%m-%d %H:%M UTC") if published else "시각 불명",
                    "category":    get_competitor_category(title, summary) if comp else get_category(title, summary),
                    "is_competitor": comp,
                })
                count += 1

            print(f"OK {count}건")
        except Exception as e:
            print(f"FAIL 오류: {e}")

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
# HTML 보고서 생성
# ──────────────────────────────────────────────
def make_cards(items: list[dict]) -> str:
    html = ""
    for a in items:
        html += f"""
        <div class="card">
          <div class="card-meta">{a['source']} &nbsp;|&nbsp; {a['published']}</div>
          <a class="card-title" href="{a['link']}" target="_blank">{a['title']}</a>
          <div class="card-body">{a['summary']}</div>
        </div>"""
    return html


def make_sections(grouped: dict) -> str:
    html = ""
    for cat in sorted(grouped.keys()):
        items = grouped[cat]
        html += f"""
      <div class="section-title">{cat} <span class="count">{len(items)}</span></div>
      {make_cards(items)}"""
    return html or '<p style="color:#888;text-align:center;padding:40px">수집된 기사가 없습니다.</p>'


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

    # 탭 배지
    dsr_badge  = f'DSR 업계 동향 <span class="tab-count">{len(dsr_articles)}</span>'
    comp_badge = f'경쟁사 동향 <span class="tab-count">{len(comp_articles)}</span>'

    # 섹션 HTML
    dsr_sections  = make_sections(dsr_grouped)
    comp_sections = make_sections(comp_grouped)

    # 전체 배지 (탭바 아래)
    def badges(grouped):
        return "".join(f'<span class="badge">{cat} {len(v)}건</span>' for cat, v in sorted(grouped.items()))

    dsr_badges  = badges(dsr_grouped)  or '<span style="color:#aaa">수집된 기사 없음</span>'
    comp_badges = badges(comp_grouped) or '<span style="color:#aaa">수집된 기사 없음</span>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DSR 일일 업계 동향 – {datetime.now().strftime('%Y년 %m월 %d일')}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background: #f0f2f5; color: #222; }}
    header {{ background: linear-gradient(135deg,#003366,#0055a5); color: #fff; padding: 24px 36px; }}
    header h1 {{ font-size: 1.6rem; letter-spacing: -.5px; }}
    header p  {{ font-size: 0.85rem; opacity: .75; margin-top: 5px; }}
    /* 탭 */
    .tab-bar {{ background: #fff; border-bottom: 2px solid #e0e4ea;
                display: flex; align-items: stretch; padding: 0 24px; gap: 0; }}
    .tab {{ padding: 14px 28px; font-size: 0.95rem; font-weight: 600; cursor: pointer;
            border-bottom: 3px solid transparent; margin-bottom: -2px; color: #888;
            display: flex; align-items: center; gap: 8px; transition: color .15s; user-select: none; }}
    .tab:hover {{ color: #0055a5; }}
    .tab.active {{ color: #0055a5; border-bottom-color: #0055a5; }}
    .tab.comp.active {{ color: #c0392b; border-bottom-color: #c0392b; }}
    .tab-count {{ font-size: 0.75rem; background: #e8f0fe; color: #0055a5;
                  border-radius: 10px; padding: 1px 8px; }}
    .tab.comp .tab-count {{ background: #fde8e8; color: #c0392b; }}
    .tab-translate {{ margin-left: auto; display: flex; align-items: center; gap: 10px; }}
    /* 배지 바 */
    .badge-bar {{ padding: 10px 28px; background: #f8f9fb; border-bottom: 1px solid #e8eaf0;
                  display: flex; flex-wrap: wrap; gap: 7px; min-height: 42px; }}
    .badge {{ background: #e8f0fe; color: #0055a5; border-radius: 16px; padding: 3px 12px;
              font-size: 0.78rem; font-weight: 600; }}
    .badge.comp {{ background: #fde8e8; color: #c0392b; }}
    /* 번역 */
    .translate-btn {{ background: #0055a5; color: #fff; border: none; border-radius: 8px;
                      padding: 7px 18px; font-size: 0.85rem; cursor: pointer; font-family: inherit; }}
    .translate-btn:hover {{ background: #003f7f; }}
    .translate-btn:disabled {{ background: #aaa; cursor: not-allowed; }}
    .progress {{ display: none; font-size: 0.8rem; color: #0055a5; align-items: center; gap: 6px; }}
    .progress.show {{ display: flex; }}
    .spinner {{ width: 13px; height: 13px; border: 2px solid #e0e4ea; border-top-color: #0055a5;
                border-radius: 50%; animation: spin .7s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    /* 오버레이 */
    #overlay {{ position: fixed; inset: 0; background: #f0f2f5;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      z-index: 9999; gap: 18px; }}
    #overlay .ov-spinner {{ width: 48px; height: 48px; border: 4px solid #d0d8e8;
      border-top-color: #0055a5; border-radius: 50%; animation: spin .8s linear infinite; }}
    #overlay p {{ font-size: 1rem; color: #0055a5; font-weight: 600; }}
    #overlay small {{ font-size: 0.82rem; color: #888; }}
    /* 콘텐츠 탭 패널 */
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .container {{ max-width: 980px; margin: 24px auto; padding: 0 16px; }}
    .section-title {{ font-size: 1.05rem; font-weight: 700; color: #003366;
                      border-left: 4px solid #0055a5; padding-left: 12px;
                      margin: 28px 0 10px; display: flex; align-items: center; gap: 8px; }}
    .section-title.comp {{ border-left-color: #c0392b; color: #7b1e1e; }}
    .count {{ background: #0055a5; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: 0.75rem; }}
    .count.comp {{ background: #c0392b; }}
    .card {{ background: #fff; border-radius: 10px; padding: 15px 20px; margin-bottom: 10px;
             box-shadow: 0 1px 5px rgba(0,0,0,.07); transition: box-shadow .15s; }}
    .card:hover {{ box-shadow: 0 4px 12px rgba(0,83,165,.10); }}
    .card.comp:hover {{ box-shadow: 0 4px 12px rgba(192,57,43,.10); }}
    .card-meta  {{ font-size: 0.75rem; color: #999; margin-bottom: 5px; }}
    .card-title {{ display: block; font-size: 0.97rem; font-weight: 600; color: #0055a5;
                   text-decoration: none; margin-bottom: 5px; line-height: 1.45; }}
    .card.comp .card-title {{ color: #c0392b; }}
    .card-title:hover {{ text-decoration: underline; }}
    .card-body  {{ font-size: 0.86rem; color: #555; line-height: 1.65; }}
    .ko-text    {{ color: #1a1a1a; }}
    footer {{ text-align: center; padding: 24px; font-size: 0.75rem; color: #bbb; }}
  </style>
</head>
<body>
  <div id="overlay">
    <div class="ov-spinner"></div>
    <p>한국어로 번역 중입니다...</p>
    <small id="ov-progress">잠시만 기다려 주세요</small>
  </div>

  <header>
    <h1>DSR 일일 업계 동향 보고서</h1>
    <p>Wire Rope · Fiber Rope &nbsp;|&nbsp; 생성: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')} &nbsp;|&nbsp; 전체 {len(articles)}건 (업계 {len(dsr_articles)} · 경쟁사 {len(comp_articles)})</p>
  </header>

  <!-- 탭 바 -->
  <div class="tab-bar">
    <div class="tab active" id="tab-dsr" onclick="switchTab('dsr')">
      업계 동향 <span class="tab-count">{len(dsr_articles)}</span>
    </div>
    <div class="tab comp" id="tab-comp" onclick="switchTab('comp')">
      경쟁사 동향 <span class="tab-count">{len(comp_articles)}</span>
    </div>
    <div class="tab-translate">
      <span class="progress show" id="progress"><span class="spinner"></span><span id="progressText">번역 중...</span></span>
      <button class="translate-btn" id="translateBtn" onclick="translateAll()" style="display:none">번역 완료</button>
    </div>
  </div>

  <!-- 업계 탭 -->
  <div class="tab-panel active" id="panel-dsr">
    <div class="badge-bar">{dsr_badges}</div>
    <div class="container">{dsr_sections}</div>
  </div>

  <!-- 경쟁사 탭 -->
  <div class="tab-panel" id="panel-comp">
    <div class="badge-bar">{comp_badges}</div>
    <div class="container">{comp_sections}</div>
  </div>

  <footer>DSR 업계 동향 수집기 &nbsp;|&nbsp; 출처: Offshore Energy · Hellenic Shipping News · Maritime Executive · Rigzone · Port Technology · Mining.com</footer>

  <script>
  const STORAGE_KEY = 'dsr_ko_{datetime.now().strftime("%Y%m%d")}';

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

  function applyTranslations(cache) {{
    document.querySelectorAll('.card-title').forEach(el => {{
      const orig = el.getAttribute('data-orig') || el.innerText;
      el.setAttribute('data-orig', orig);
      if (cache[orig]) {{
        const textNode = [...el.childNodes].find(n => n.nodeType === Node.TEXT_NODE);
        if (textNode) textNode.textContent = cache[orig];
        el.classList.add('ko-text');
      }}
    }});
    document.querySelectorAll('.card-body').forEach(el => {{
      const orig = el.getAttribute('data-orig') || el.innerText;
      el.setAttribute('data-orig', orig);
      if (cache[orig]) {{
        el.textContent = cache[orig];
        el.classList.add('ko-text');
      }}
    }});
  }}

  function switchTab(name) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.getElementById('panel-' + name).classList.add('active');
  }}

  function hideOverlay() {{
    const ov = document.getElementById('overlay');
    if (ov) {{ ov.style.opacity = '0'; ov.style.transition = 'opacity .4s'; setTimeout(() => ov.remove(), 400); }}
  }}

  // 페이지 로드 시: 저장된 번역 복원 또는 자동 번역 시작
  window.addEventListener('DOMContentLoaded', () => {{
    try {{
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {{
        const cache = JSON.parse(saved);
        applyTranslations(cache);
        // 캐시 항목이 실제로 적용됐는지 확인 (키 불일치 시 재번역)
        const translated = document.querySelectorAll('.ko-text').length;
        if (translated === 0) {{
          localStorage.removeItem(STORAGE_KEY);
          translateAll();
        }} else {{
          hideOverlay();
          document.getElementById('progress').classList.remove('show');
          document.getElementById('translateBtn').style.display = 'flex';
          document.getElementById('translateBtn').disabled = true;
          document.getElementById('translateBtn').textContent = '번역 완료';
        }}
      }} else {{
        translateAll();
      }}
    }} catch(e) {{
      translateAll();
    }}
  }});

  async function translateAll() {{
    const btn = document.getElementById('translateBtn');
    const progress = document.getElementById('progress');
    const progressText = document.getElementById('progressText');
    btn.disabled = true;
    btn.textContent = '번역 완료';
    progress.classList.add('show');

    const titles = document.querySelectorAll('.card-title');
    const bodies = document.querySelectorAll('.card-body');
    const total  = titles.length + bodies.length;
    let done = 0;
    const cache = {{}};

    async function doItem(el, isLink) {{
      const original = el.getAttribute('data-orig') || el.innerText;
      el.setAttribute('data-orig', original);
      const translated = await translateText(original);
      cache[original] = translated;
      if (isLink) {{
        const textNode = [...el.childNodes].find(n => n.nodeType === Node.TEXT_NODE);
        if (textNode) textNode.textContent = translated;
        else el.insertBefore(document.createTextNode(translated), el.firstChild);
      }} else {{
        el.textContent = translated;
      }}
      el.classList.add('ko-text');
      done++;
      const msg = `${{done}} / ${{total}} 번역 완료`;
      progressText.textContent = `번역 중... (${{done}}/${{total}})`;
      const ovp = document.getElementById('ov-progress');
      if (ovp) ovp.textContent = msg;
      await new Promise(r => setTimeout(r, 80));
    }}

    for (const el of titles) await doItem(el, true);
    for (const el of bodies) await doItem(el, false);

    // 번역 결과를 localStorage에 저장 (#2)
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(cache)); }} catch(e) {{}}

    hideOverlay();
    progress.classList.remove('show');
    progressText.textContent = '번역 중...';
    btn.style.display = 'flex';
    btn.disabled = true;
    btn.textContent = '번역 완료';
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
