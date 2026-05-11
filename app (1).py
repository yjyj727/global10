"""
🌍 국가별 범죄 비교 분석 대시보드
뉴스 보도(Google News RSS) + 범죄 통계 수치(내장 데이터)를 결합해
두 나라의 범죄 현황을 다각도로 비교 분석합니다.
"""

import html as _html
import re
import io
import datetime
from collections import Counter

import requests
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
from textblob import TextBlob
from wordcloud import WordCloud
from dateutil import parser as dateutil_parser
from urllib.parse import quote

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="🌍 국가별 범죄 비교 분석",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 내장 범죄 통계 데이터 (Numbeo 2023-2024 기반)
# 출처: Numbeo Crime Index, UNODC, World Population Review
# ─────────────────────────────────────────────
CRIME_STATS = {
    "브라질": {
        "crime_index": 67.4,
        "safety_index": 32.6,
        "homicide_rate": 22.4,   # 인구 10만 명당
        "robbery_rate": 432.0,
        "drug_offenses": 215.0,
        "assault_rate": 310.0,
        "corruption_index": 38,  # 투명성지수(높을수록 청렴)
        "prison_population": 381, # 인구 10만 명당 수감자
        "police_per_100k": 198,
        "region": "남미",
    },
    "멕시코": {
        "crime_index": 70.2,
        "safety_index": 29.8,
        "homicide_rate": 27.8,
        "robbery_rate": 385.0,
        "drug_offenses": 300.0,
        "assault_rate": 260.0,
        "corruption_index": 31,
        "prison_population": 169,
        "police_per_100k": 122,
        "region": "북미",
    },
    "남아프리카공화국": {
        "crime_index": 76.9,
        "safety_index": 23.1,
        "homicide_rate": 41.9,
        "robbery_rate": 520.0,
        "drug_offenses": 180.0,
        "assault_rate": 490.0,
        "corruption_index": 41,
        "prison_population": 292,
        "police_per_100k": 233,
        "region": "아프리카",
    },
    "베네수엘라": {
        "crime_index": 83.1,
        "safety_index": 16.9,
        "homicide_rate": 36.7,
        "robbery_rate": 610.0,
        "drug_offenses": 195.0,
        "assault_rate": 380.0,
        "corruption_index": 13,
        "prison_population": 188,
        "police_per_100k": 148,
        "region": "남미",
    },
    "온두라스": {
        "crime_index": 73.5,
        "safety_index": 26.5,
        "homicide_rate": 35.8,
        "robbery_rate": 490.0,
        "drug_offenses": 280.0,
        "assault_rate": 295.0,
        "corruption_index": 23,
        "prison_population": 245,
        "police_per_100k": 137,
        "region": "중미",
    },
    "자메이카": {
        "crime_index": 72.2,
        "safety_index": 27.8,
        "homicide_rate": 44.9,
        "robbery_rate": 300.0,
        "drug_offenses": 190.0,
        "assault_rate": 320.0,
        "corruption_index": 44,
        "prison_population": 178,
        "police_per_100k": 192,
        "region": "카리브해",
    },
    "파푸아뉴기니": {
        "crime_index": 68.3,
        "safety_index": 31.7,
        "homicide_rate": 10.5,
        "robbery_rate": 310.0,
        "drug_offenses": 95.0,
        "assault_rate": 420.0,
        "corruption_index": 24,
        "prison_population": 110,
        "police_per_100k": 62,
        "region": "오세아니아",
    },
    "나이지리아": {
        "crime_index": 65.8,
        "safety_index": 34.2,
        "homicide_rate": 9.8,
        "robbery_rate": 270.0,
        "drug_offenses": 145.0,
        "assault_rate": 230.0,
        "corruption_index": 24,
        "prison_population": 43,
        "police_per_100k": 35,
        "region": "아프리카",
    },
    "콜롬비아": {
        "crime_index": 62.5,
        "safety_index": 37.5,
        "homicide_rate": 27.7,
        "robbery_rate": 350.0,
        "drug_offenses": 390.0,
        "assault_rate": 200.0,
        "corruption_index": 39,
        "prison_population": 244,
        "police_per_100k": 171,
        "region": "남미",
    },
    "아이티": {
        "crime_index": 78.4,
        "safety_index": 21.6,
        "homicide_rate": 10.2,
        "robbery_rate": 450.0,
        "drug_offenses": 120.0,
        "assault_rate": 310.0,
        "corruption_index": 17,
        "prison_population": 98,
        "police_per_100k": 10,
        "region": "카리브해",
    },
    "미국": {
        "crime_index": 47.8,
        "safety_index": 52.2,
        "homicide_rate": 6.8,
        "robbery_rate": 73.9,
        "drug_offenses": 537.0,
        "assault_rate": 282.7,
        "corruption_index": 69,
        "prison_population": 639,
        "police_per_100k": 232,
        "region": "북미",
    },
    "러시아": {
        "crime_index": 50.2,
        "safety_index": 49.8,
        "homicide_rate": 7.3,
        "robbery_rate": 58.0,
        "drug_offenses": 120.0,
        "assault_rate": 180.0,
        "corruption_index": 26,
        "prison_population": 356,
        "police_per_100k": 332,
        "region": "유럽/아시아",
    },
    "인도": {
        "crime_index": 44.2,
        "safety_index": 55.8,
        "homicide_rate": 2.3,
        "robbery_rate": 1.5,
        "drug_offenses": 32.0,
        "assault_rate": 14.0,
        "corruption_index": 39,
        "prison_population": 36,
        "police_per_100k": 137,
        "region": "아시아",
    },
    "중국": {
        "crime_index": 31.4,
        "safety_index": 68.6,
        "homicide_rate": 0.5,
        "robbery_rate": 1.2,
        "drug_offenses": 48.0,
        "assault_rate": 11.0,
        "corruption_index": 42,
        "prison_population": 121,
        "police_per_100k": 120,
        "region": "아시아",
    },
    "독일": {
        "crime_index": 36.4,
        "safety_index": 63.6,
        "homicide_rate": 0.9,
        "robbery_rate": 43.7,
        "drug_offenses": 295.0,
        "assault_rate": 138.0,
        "corruption_index": 78,
        "prison_population": 77,
        "police_per_100k": 299,
        "region": "유럽",
    },
    "일본": {
        "crime_index": 22.5,
        "safety_index": 77.5,
        "homicide_rate": 0.3,
        "robbery_rate": 2.4,
        "drug_offenses": 22.0,
        "assault_rate": 21.0,
        "corruption_index": 73,
        "prison_population": 41,
        "police_per_100k": 197,
        "region": "아시아",
    },
    "한국": {
        "crime_index": 27.1,
        "safety_index": 72.9,
        "homicide_rate": 0.6,
        "robbery_rate": 3.1,
        "drug_offenses": 35.0,
        "assault_rate": 45.0,
        "corruption_index": 63,
        "prison_population": 107,
        "police_per_100k": 212,
        "region": "아시아",
    },
    "핀란드": {
        "crime_index": 26.8,
        "safety_index": 73.2,
        "homicide_rate": 1.4,
        "robbery_rate": 22.0,
        "drug_offenses": 215.0,
        "assault_rate": 170.0,
        "corruption_index": 87,
        "prison_population": 51,
        "police_per_100k": 146,
        "region": "유럽",
    },
    "싱가포르": {
        "crime_index": 18.0,
        "safety_index": 82.0,
        "homicide_rate": 0.2,
        "robbery_rate": 1.6,
        "drug_offenses": 10.0,
        "assault_rate": 8.0,
        "corruption_index": 83,
        "prison_population": 236,
        "police_per_100k": 282,
        "region": "아시아",
    },
    "엘살바도르": {
        "crime_index": 61.5,
        "safety_index": 38.5,
        "homicide_rate": 17.6,
        "robbery_rate": 420.0,
        "drug_offenses": 260.0,
        "assault_rate": 280.0,
        "corruption_index": 31,
        "prison_population": 1086,
        "police_per_100k": 308,
        "region": "중미",
    },
}

# 뉴스 검색용 국가명 영어 매핑
COUNTRY_EN = {
    "브라질": "Brazil crime",
    "멕시코": "Mexico crime",
    "남아프리카공화국": "South Africa crime",
    "베네수엘라": "Venezuela crime",
    "온두라스": "Honduras crime",
    "자메이카": "Jamaica crime",
    "파푸아뉴기니": "Papua New Guinea crime",
    "나이지리아": "Nigeria crime",
    "콜롬비아": "Colombia crime",
    "아이티": "Haiti crime",
    "미국": "United States crime",
    "러시아": "Russia crime",
    "인도": "India crime",
    "중국": "China crime",
    "독일": "Germany crime",
    "일본": "Japan crime",
    "한국": "South Korea crime",
    "핀란드": "Finland crime",
    "싱가포르": "Singapore crime",
    "엘살바도르": "El Salvador crime",
}

# 범죄 유형 한국어 라벨
CRIME_TYPE_KO = {
    "crime_index":       "범죄 지수",
    "safety_index":      "안전 지수",
    "homicide_rate":     "살인율 (10만 명당)",
    "robbery_rate":      "강도율 (10만 명당)",
    "drug_offenses":     "마약 범죄 (10만 명당)",
    "assault_rate":      "폭행률 (10만 명당)",
    "corruption_index":  "청렴도 지수",
    "prison_population": "수감자 수 (10만 명당)",
    "police_per_100k":   "경찰관 수 (10만 명당)",
}

# 감성 한국어 라벨
SENTIMENT_KO = {"Positive": "긍정", "Negative": "부정", "Neutral": "중립"}
SENTIMENT_EMOJI = {"Positive": "😊", "Negative": "😟", "Neutral": "😐"}
SENTIMENT_COLOR = {"Positive": "#22c55e", "Negative": "#ef4444", "Neutral": "#94a3b8"}

# ─────────────────────────────────────────────
# 불용어 정의
# ─────────────────────────────────────────────
BASE_STOPWORDS = {
    "the","a","an","is","in","of","to","and","for","that","this","it",
    "as","at","on","with","by","are","was","be","been","has","have",
    "had","do","does","did","will","would","could","should","from",
    "or","but","not","its","he","she","they","we","you","i","his",
    "her","their","more","also","up","out","about","after","into",
    "over","s","new","says","said","one","two","three","us","who",
    "what","how","when","where","than","so","if","all","no","say",
    "just","can","get","got","being","our","which","there","were",
    "then","your","my","any","may","each","between","through",
    "these","those","such","even","back","well","now","still",
    "last","while","too","very","only","much","many","most",
    "html","head","body","div","span","href","color","font","src","alt",
    "nbsp","amp","quot","apos","lt","gt","ndash","mdash","hellip",
    "rsquo","lsquo","bull","copy","reg","trade",
    "rss","xml","feed","atom","google","news","articles","article",
    "read","more","full","story","click","here",
    "com","www","http","https","utm","via","per","net","org",
    "report","reported","reporting","reports","according",
    "told","added","noted","stated","announced","officials",
    "government","people","world","including",
    "crime","crimes","criminal","criminals",  # 범죄 관련 공통 단어
}

def get_stopwords(country_names: list) -> set:
    """국가명과 영문 검색어를 불용어에 추가"""
    extra = set()
    for name in country_names:
        extra.update(re.findall(r"[a-zA-Z]+", name.lower()))
        en = COUNTRY_EN.get(name, "")
        extra.update(re.findall(r"[a-zA-Z]+", en.lower()))
    return BASE_STOPWORDS | extra


# ─────────────────────────────────────────────
# description 정제 (5단계 파이프라인)
# ─────────────────────────────────────────────
def clean_description(desc_t) -> str:
    raw = str(desc_t)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = _html.unescape(raw)
    raw = re.sub(r"&[a-zA-Z]{2,10};", " ", raw)
    raw = re.sub(r"https?://\S+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:400]


# ─────────────────────────────────────────────
# 텍스트 빈도 추출
# ─────────────────────────────────────────────
def extract_word_freq(texts: list, stopwords: set) -> Counter:
    all_words = []
    for text in texts:
        t = str(text)
        t = re.sub(r"<[^>]+>", " ", t)
        t = _html.unescape(t)
        t = re.sub(r"&[a-zA-Z]{2,10};", " ", t)
        t = re.sub(r"https?://\S+", " ", t)
        t = re.sub(r"www\.\S+", " ", t)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", t.lower())
        all_words.extend([w for w in words if w not in stopwords])
    return Counter(all_words)


# ─────────────────────────────────────────────
# 감성 분석
# ─────────────────────────────────────────────
def analyze_sentiment(text: str) -> tuple:
    try:
        polarity = TextBlob(text).sentiment.polarity
        if polarity > 0.05:
            return "Positive", polarity
        elif polarity < -0.05:
            return "Negative", polarity
        else:
            return "Neutral", polarity
    except Exception:
        return "Neutral", 0.0


# ─────────────────────────────────────────────
# RSS 기사 수집 (30분 캐시)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_articles(country: str, days_filter: int = 30) -> pd.DataFrame:
    """국가명으로 Google News RSS에서 범죄 관련 기사 수집"""
    search_query = COUNTRY_EN.get(country, f"{country} crime")
    encoded_q = quote(search_query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded_q}&hl=en&gl=US&ceid=US:en"
    )
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml-xml")
        items = soup.find_all("item")

        rows = []
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_filter)

        for item in items:
            title_tag = item.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            pub_tag = item.find("pubDate")
            pub_raw = pub_tag.get_text(strip=True) if pub_tag else ""
            try:
                pub_dt = dateutil_parser.parse(pub_raw)
                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.replace(tzinfo=None)
            except Exception:
                pub_dt = datetime.datetime.now()

            if pub_dt < cutoff_date:
                continue

            desc_tag = item.find("description")
            desc = clean_description(desc_tag) if desc_tag else ""

            source_tag = item.find("source")
            source = source_tag.get_text(strip=True) if source_tag else "Unknown"

            sentiment_label, polarity = analyze_sentiment(title + " " + desc)

            rows.append({
                "title":       title,
                "date":        pub_dt,
                "description": desc,
                "source":      source,
                "sentiment":   sentiment_label,
                "polarity":    round(polarity, 4),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("date", ascending=False).reset_index(drop=True)
        return df

    except Exception as e:
        st.warning(f"⚠️ {country} 기사 수집 중 오류: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# 워드클라우드 생성
# ─────────────────────────────────────────────
def make_wordcloud(freq: Counter, colormap: str) -> plt.Figure:
    if not freq:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center", fontsize=14)
        ax.axis("off")
        return fig
    wc = WordCloud(
        width=700, height=350,
        background_color="white",
        colormap=colormap,
        max_words=60,
        prefer_horizontal=0.8,
        collocations=False,
    ).generate_from_frequencies(dict(freq))
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
if "search_history" not in st.session_state:
    st.session_state.search_history = []
if "triggered" not in st.session_state:
    st.session_state.triggered = False
if "last_c1" not in st.session_state:
    st.session_state.last_c1 = "브라질"
if "last_c2" not in st.session_state:
    st.session_state.last_c2 = "일본"


# ─────────────────────────────────────────────
# 커스텀 CSS — 다크 범죄 테마 (딥 네이비 + 앰버 액센트)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Noto+Sans+KR:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
    background-color: #0f1117;
}

/* 메인 배경 */
.stApp {
    background: linear-gradient(135deg, #0f1117 0%, #1a1f2e 100%);
}

/* 제목 */
.main-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3rem;
    letter-spacing: 4px;
    color: #f59e0b;
    text-shadow: 0 0 30px rgba(245,158,11,0.4);
    margin-bottom: 0;
    line-height: 1.1;
}
.sub-title {
    font-size: 0.95rem;
    color: #94a3b8;
    margin-top: 0.3rem;
    margin-bottom: 1.5rem;
    letter-spacing: 1px;
}

/* 통계 카드 */
.stat-card {
    background: linear-gradient(135deg, #1e2535, #252d40);
    border: 1px solid #334155;
    border-left: 3px solid #f59e0b;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
}
.stat-label {
    font-size: 0.78rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #f1f5f9;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 1px;
}
.stat-unit {
    font-size: 0.72rem;
    color: #64748b;
}

/* 위험도 뱃지 */
.badge-high   { background:#fee2e2; color:#b91c1c; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600; }
.badge-mid    { background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600; }
.badge-low    { background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600; }

/* 기사 카드 */
.article-card {
    background: #1e2535;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    border-left: 3px solid #f59e0b;
}

/* 섹션 헤더 */
.section-header {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.4rem;
    color: #f59e0b;
    letter-spacing: 2px;
    margin-bottom: 0.5rem;
}

/* 인사이트 박스 */
.insight-box {
    background: linear-gradient(135deg, #1e2535, #252d40);
    border: 1px solid #f59e0b44;
    border-radius: 10px;
    padding: 1.2rem;
    margin: 1rem 0;
    color: #e2e8f0;
    font-size: 0.95rem;
    line-height: 1.7;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">🔍 국가별 범죄 비교 분석</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">통계 수치 + 실시간 뉴스 보도를 결합한 두 나라 범죄 현황 심층 분석</div>', unsafe_allow_html=True)
st.divider()


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")

    country_list = list(CRIME_STATS.keys())

    c1_idx = country_list.index(st.session_state.last_c1) if st.session_state.last_c1 in country_list else 0
    c2_idx = country_list.index(st.session_state.last_c2) if st.session_state.last_c2 in country_list else 6

    C1 = st.selectbox("🌍 국가 1 선택", country_list, index=c1_idx, key="c1_select")
    C2 = st.selectbox("🌍 국가 2 선택", country_list, index=c2_idx, key="c2_select")

    days_filter = st.slider("📅 최근 N일 뉴스 포함", 7, 90, 30, 7)
    compare_btn = st.button("🔍 비교 분석 시작", use_container_width=True, type="primary")

    if compare_btn:
        if C1 == C2:
            st.warning("서로 다른 국가를 선택해주세요.")
        else:
            st.session_state.last_c1 = C1
            st.session_state.last_c2 = C2
            st.session_state.triggered = True
            st.rerun()

    st.divider()
    st.markdown("### 🕐 최근 비교 기록")
    if st.session_state.search_history:
        for h in reversed(st.session_state.search_history[-5:]):
            if st.button(f"🔁 {h['c1']} vs {h['c2']}", key=f"h_{h['c1']}_{h['c2']}", use_container_width=True):
                st.session_state.last_c1 = h["c1"]
                st.session_state.last_c2 = h["c2"]
                st.session_state.triggered = True
                st.rerun()
    else:
        st.caption("아직 비교 기록이 없습니다.")

    st.divider()
    st.markdown("### 📌 데이터 출처")
    st.markdown("""
- **범죄 통계**: Numbeo, UNODC, World Population Review (2023-2024)
- **뉴스 데이터**: Google News RSS
- **감성 분석**: TextBlob
- **캐시 갱신**: 30분마다
    """)


# ─────────────────────────────────────────────
# 입력 검증
# ─────────────────────────────────────────────
C1 = st.session_state.last_c1
C2 = st.session_state.last_c2

if not st.session_state.triggered:
    st.info("👈 왼쪽 사이드바에서 국가 2개를 선택하고 '비교 분석 시작' 버튼을 눌러주세요.")
    # 미리보기용 글로벌 지도 표시
    globe_data = []
    for country, stats in CRIME_STATS.items():
        globe_data.append({
            "국가": country,
            "범죄 지수": stats["crime_index"],
            "살인율": stats["homicide_rate"],
        })
    globe_df = pd.DataFrame(globe_data)

    st.markdown("### 🗺️ 분석 가능 국가 범죄 지수 미리보기")
    fig_preview = px.bar(
        globe_df.sort_values("범죄 지수", ascending=False),
        x="국가", y="범죄 지수",
        color="범죄 지수",
        color_continuous_scale="RdYlGn_r",
        labels={"국가": "국가", "범죄 지수": "범죄 지수 (높을수록 위험)"},
        title="분석 가능 국가별 범죄 지수 (Numbeo 2023-2024)",
    )
    fig_preview.update_layout(
        plot_bgcolor="#1e2535",
        paper_bgcolor="#1e2535",
        font_color="#e2e8f0",
        coloraxis_showscale=False,
    )
    fig_preview.update_xaxes(tickfont=dict(size=11))
    st.plotly_chart(fig_preview, use_container_width=True)
    st.stop()

if C1 == C2:
    st.warning("⚠️ 서로 다른 국가 2개를 선택해주세요.")
    st.stop()

# 히스토리 업데이트
entry = {"c1": C1, "c2": C2}
if entry not in st.session_state.search_history:
    st.session_state.search_history.append(entry)


# ─────────────────────────────────────────────
# 통계 데이터 로드
# ─────────────────────────────────────────────
stats1 = CRIME_STATS[C1]
stats2 = CRIME_STATS[C2]


# ─────────────────────────────────────────────
# 뉴스 기사 수집
# ─────────────────────────────────────────────
with st.spinner(f"📡 {C1} 범죄 뉴스를 가져오는 중..."):
    df1 = fetch_articles(C1, days_filter)
with st.spinner(f"📡 {C2} 범죄 뉴스를 가져오는 중..."):
    df2 = fetch_articles(C2, days_filter)

if df1.empty:
    st.warning(f"⚠️ {C1} 관련 뉴스를 찾을 수 없습니다.")
if df2.empty:
    st.warning(f"⚠️ {C2} 관련 뉴스를 찾을 수 없습니다.")

# 감성 통계
def sentiment_stats(df):
    if df.empty:
        return 0.0, "Neutral", {"Positive": 0, "Negative": 0, "Neutral": 0}
    avg = df["polarity"].mean()
    lbl = "Positive" if avg > 0.05 else ("Negative" if avg < -0.05 else "Neutral")
    counts = df["sentiment"].value_counts().to_dict()
    for k in ["Positive","Negative","Neutral"]:
        counts.setdefault(k, 0)
    return round(avg, 3), lbl, counts

avg1, lbl1, cnt1 = sentiment_stats(df1)
avg2, lbl2, cnt2 = sentiment_stats(df2)

# 불용어 & 빈도
sw = get_stopwords([C1, C2])
texts1 = (df1["title"] + " " + df1["description"]).tolist() if not df1.empty else []
texts2 = (df2["title"] + " " + df2["description"]).tolist() if not df2.empty else []
freq1 = extract_word_freq(texts1, sw)
freq2 = extract_word_freq(texts2, sw)


# ─────────────────────────────────────────────
# 위험도 뱃지 함수
# ─────────────────────────────────────────────
def risk_badge(crime_index: float) -> str:
    if crime_index >= 60:
        return '<span class="badge-high">🔴 위험</span>'
    elif crime_index >= 40:
        return '<span class="badge-mid">🟡 주의</span>'
    else:
        return '<span class="badge-low">🟢 안전</span>'


# ─────────────────────────────────────────────
# 상단 비교 헤더 카드
# ─────────────────────────────────────────────
h_col1, h_mid, h_col2 = st.columns([5, 1, 5])

with h_col1:
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#1e2535,#252d40);border:1px solid #334155;border-radius:14px;padding:1.5rem;text-align:center;">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#60a5fa;letter-spacing:3px;">{C1}</div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:2px;">{stats1['region']}</div>
    <div style="margin-top:0.7rem;">{risk_badge(stats1['crime_index'])}</div>
    <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#f59e0b;margin-top:0.5rem;">{stats1['crime_index']}</div>
    <div style="color:#94a3b8;font-size:0.8rem;">범죄 지수</div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:0.5rem;">📰 뉴스 {len(df1)}건 수집</div>
</div>
""", unsafe_allow_html=True)

with h_mid:
    st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#475569;padding-top:2rem;">VS</div>
""", unsafe_allow_html=True)

with h_col2:
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#1e2535,#252d40);border:1px solid #334155;border-radius:14px;padding:1.5rem;text-align:center;">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#f97316;letter-spacing:3px;">{C2}</div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:2px;">{stats2['region']}</div>
    <div style="margin-top:0.7rem;">{risk_badge(stats2['crime_index'])}</div>
    <div style="font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:#f59e0b;margin-top:0.5rem;">{stats2['crime_index']}</div>
    <div style="color:#94a3b8;font-size:0.8rem;">범죄 지수</div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:0.5rem;">📰 뉴스 {len(df2)}건 수집</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 6개 탭
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 통계 비교",
    "☁️ 뉴스 워드클라우드",
    "😊 뉴스 감성 분석",
    "📰 헤드라인",
    "🗺️ 레이더 차트",
    "📋 종합 리포트",
])


# ══════════════════════════════════════════════
# 탭1: 통계 비교
# ══════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">📊 범죄 통계 상세 비교</div>', unsafe_allow_html=True)

    # 주요 지표 테이블
    stat_keys = [
        "crime_index","safety_index","homicide_rate","robbery_rate",
        "drug_offenses","assault_rate","corruption_index",
        "prison_population","police_per_100k",
    ]

    # 막대 비교 차트
    bar_data = []
    for k in stat_keys:
        bar_data.append({"지표": CRIME_TYPE_KO[k], "값": stats1[k], "국가": C1})
        bar_data.append({"지표": CRIME_TYPE_KO[k], "값": stats2[k], "국가": C2})
    bar_df = pd.DataFrame(bar_data)

    # 지표별 개별 차트 (정규화 없이 각각 표시)
    st.markdown("#### 🔢 핵심 지표별 수치 비교")

    # 살인율 / 강도율 / 범죄지수 3가지를 강조 메트릭으로
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        delta_h = round(stats1["homicide_rate"] - stats2["homicide_rate"], 1)
        st.metric(f"🔫 살인율 ({C1})", f"{stats1['homicide_rate']}", f"{delta_h:+.1f} vs {C2}")
    with m2:
        delta_r = round(stats1["robbery_rate"] - stats2["robbery_rate"], 1)
        st.metric(f"💰 강도율 ({C1})", f"{stats1['robbery_rate']}", f"{delta_r:+.1f} vs {C2}")
    with m3:
        delta_c = round(stats1["crime_index"] - stats2["crime_index"], 1)
        st.metric(f"📈 범죄지수 ({C1})", f"{stats1['crime_index']}", f"{delta_c:+.1f} vs {C2}")
    with m4:
        delta_s = round(stats1["safety_index"] - stats2["safety_index"], 1)
        st.metric(f"🛡️ 안전지수 ({C1})", f"{stats1['safety_index']}", f"{delta_s:+.1f} vs {C2}")

    st.markdown("<br>", unsafe_allow_html=True)

    # 그룹 막대 차트 (전체 지표)
    fig_grouped = px.bar(
        bar_df, x="지표", y="값", color="국가",
        barmode="group",
        color_discrete_sequence=["#60a5fa", "#f97316"],
        labels={"지표": "범죄 지표", "값": "수치", "국가": "국가"},
        title=f"전체 범죄 지표 비교: {C1} vs {C2}",
    )
    fig_grouped.update_layout(
        plot_bgcolor="#1e2535", paper_bgcolor="#1e2535",
        font_color="#e2e8f0",
        xaxis_tickangle=-25,
        legend=dict(bgcolor="#252d40", bordercolor="#334155"),
    )
    st.plotly_chart(fig_grouped, use_container_width=True)
    st.caption("Numbeo, UNODC 2023-2024 데이터 기준. 지표마다 단위가 다르므로 같은 지표 내에서만 비교하세요.")

    # 상세 비교 테이블
    st.markdown("#### 📋 상세 수치 비교표")
    table_rows = []
    for k in stat_keys:
        v1, v2 = stats1[k], stats2[k]
        diff = round(v1 - v2, 1)
        # 어느 쪽이 더 위험한지 (안전지수·청렴도는 높을수록 좋음)
        good_high = k in ["safety_index", "corruption_index", "police_per_100k"]
        if good_high:
            winner = C1 if v1 > v2 else C2
        else:
            winner = C1 if v1 < v2 else C2
        table_rows.append({
            "지표": CRIME_TYPE_KO[k],
            C1: v1,
            C2: v2,
            "차이": f"{diff:+.1f}",
            "더 안전한 국가": winner,
        })
    detail_df = pd.DataFrame(table_rows)
    st.dataframe(detail_df, use_container_width=True, hide_index=True)
    st.caption("'더 안전한 국가'는 해당 지표에서 상대적으로 안전한 쪽을 의미합니다 (살인율 등은 낮을수록, 안전지수는 높을수록 좋음).")


# ══════════════════════════════════════════════
# 탭2: 뉴스 워드클라우드
# ══════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">☁️ 범죄 뉴스 워드클라우드</div>', unsafe_allow_html=True)
    st.caption(f"최근 {days_filter}일 Google News 기사에서 가장 많이 언급된 단어를 시각화합니다.")

    wc1_col, wc2_col = st.columns(2)
    with wc1_col:
        st.markdown(f"##### 🔵 {C1}")
        fig_wc1 = make_wordcloud(freq1, "Blues")
        st.pyplot(fig_wc1, use_container_width=True)
        plt.close(fig_wc1)

    with wc2_col:
        st.markdown(f"##### 🟠 {C2}")
        fig_wc2 = make_wordcloud(freq2, "Oranges")
        st.pyplot(fig_wc2, use_container_width=True)
        plt.close(fig_wc2)

    st.caption("클수록 더 자주 등장한 단어입니다. 검색어·국가명·일반 불용어는 제거되었습니다.")

    # 상위 15단어 비교 바 차트
    st.markdown("#### 📊 상위 15개 단어 빈도 비교")
    top15_1 = dict(freq1.most_common(15))
    top15_2 = dict(freq2.most_common(15))
    all_w = list(dict.fromkeys(list(top15_1.keys()) + list(top15_2.keys())))[:15]

    freq_df = pd.DataFrame({
        "단어": all_w * 2,
        "빈도": [top15_1.get(w,0) for w in all_w] + [top15_2.get(w,0) for w in all_w],
        "국가": [C1]*len(all_w) + [C2]*len(all_w),
    })
    fig_freq = px.bar(
        freq_df, x="단어", y="빈도", color="국가", barmode="group",
        color_discrete_sequence=["#60a5fa","#f97316"],
        labels={"단어":"단어","빈도":"빈도","국가":"국가"},
        title=f"뉴스 상위 단어 빈도: {C1} vs {C2}",
    )
    fig_freq.update_layout(plot_bgcolor="#1e2535", paper_bgcolor="#1e2535", font_color="#e2e8f0")
    st.plotly_chart(fig_freq, use_container_width=True)
    st.caption("두 나라의 범죄 뉴스에서 등장하는 핵심 단어를 비교합니다.")

    # 고유 단어 분석
    st.markdown("#### 🔤 차별화 단어 (한쪽에만 등장)")
    set1 = set(freq1.keys()); set2 = set(freq2.keys())
    only1 = sorted([(w, freq1[w]) for w in set1-set2], key=lambda x:-x[1])[:10]
    only2 = sorted([(w, freq2[w]) for w in set2-set1], key=lambda x:-x[1])[:10]

    ow1, ow2 = st.columns(2)
    with ow1:
        st.markdown(f"**🔵 {C1} 고유 단어 Top 10**")
        if only1:
            df_o1 = pd.DataFrame(only1, columns=["단어","빈도"])
            fig_o1 = px.bar(df_o1, x="빈도", y="단어", orientation="h",
                            color_discrete_sequence=["#60a5fa"])
            fig_o1.update_layout(yaxis=dict(autorange="reversed"),
                                  plot_bgcolor="#1e2535", paper_bgcolor="#1e2535",
                                  font_color="#e2e8f0", showlegend=False, height=320)
            st.plotly_chart(fig_o1, use_container_width=True)
        else:
            st.info("고유 단어가 없습니다.")

    with ow2:
        st.markdown(f"**🟠 {C2} 고유 단어 Top 10**")
        if only2:
            df_o2 = pd.DataFrame(only2, columns=["단어","빈도"])
            fig_o2 = px.bar(df_o2, x="빈도", y="단어", orientation="h",
                            color_discrete_sequence=["#f97316"])
            fig_o2.update_layout(yaxis=dict(autorange="reversed"),
                                  plot_bgcolor="#1e2535", paper_bgcolor="#1e2535",
                                  font_color="#e2e8f0", showlegend=False, height=320)
            st.plotly_chart(fig_o2, use_container_width=True)
        else:
            st.info("고유 단어가 없습니다.")

    # 자동 인사이트
    if only1 and only2:
        w1a = only1[0][0]; w1b = only1[1][0] if len(only1)>1 else "-"
        w2a = only2[0][0]; w2b = only2[1][0] if len(only2)>1 else "-"
        st.markdown(f"""
<div class="insight-box">
💡 <strong>언론 보도 인사이트</strong><br>
{C1} 관련 뉴스는 <strong>'{w1a}'</strong>, <strong>'{w1b}'</strong> 같은 단어를 중심으로 보도되는 반면,
{C2} 관련 뉴스는 <strong>'{w2a}'</strong>, <strong>'{w2b}'</strong>에 더 집중하는 경향이 있습니다.
이는 두 나라의 범죄 문제가 서로 다른 유형과 맥락에서 국제 언론에 노출되고 있음을 시사합니다.
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# 탭3: 뉴스 감성 분석
# ══════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">😊 범죄 뉴스 감성 분석</div>', unsafe_allow_html=True)
    st.caption("국제 언론이 각 국가의 범죄 이슈를 얼마나 부정적·긍정적으로 보도하는지 분석합니다.")

    # 도넛 차트 나란히
    d1, d2 = st.columns(2)

    def dark_donut(counts, title):
        labels_ko = [SENTIMENT_KO[k] for k in ["Positive","Negative","Neutral"]]
        vals = [counts["Positive"], counts["Negative"], counts["Neutral"]]
        colors = ["#22c55e","#ef4444","#94a3b8"]
        fig = go.Figure(data=[go.Pie(
            labels=labels_ko, values=vals, hole=0.6,
            marker_colors=colors,
        )])
        fig.update_layout(
            title_text=title, title_x=0.5, title_font_color="#e2e8f0",
            plot_bgcolor="#1e2535", paper_bgcolor="#1e2535",
            font_color="#e2e8f0", height=300,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5,
                        bgcolor="#252d40"),
        )
        return fig

    with d1:
        st.plotly_chart(dark_donut(cnt1, f"{C1} 감성 분포"), use_container_width=True)
    with d2:
        st.plotly_chart(dark_donut(cnt2, f"{C2} 감성 분포"), use_container_width=True)

    st.caption("도넛 차트는 수집된 기사의 긍정·부정·중립 비율을 나타냅니다.")

    # 감성 비율 그룹 바
    total1 = max(sum(cnt1.values()), 1)
    total2 = max(sum(cnt2.values()), 1)
    sent_rows = []
    for k_en, k_ko in [("Positive","긍정"),("Negative","부정"),("Neutral","중립")]:
        sent_rows.append({"감성": k_ko, "비율 (%)": round(cnt1[k_en]/total1*100,1), "국가": C1})
        sent_rows.append({"감성": k_ko, "비율 (%)": round(cnt2[k_en]/total2*100,1), "국가": C2})

    fig_sb = px.bar(
        pd.DataFrame(sent_rows), x="감성", y="비율 (%)", color="국가",
        barmode="group", color_discrete_sequence=["#60a5fa","#f97316"],
        title=f"감성 분포 비교: {C1} vs {C2}",
    )
    fig_sb.update_layout(plot_bgcolor="#1e2535", paper_bgcolor="#1e2535", font_color="#e2e8f0")
    st.plotly_chart(fig_sb, use_container_width=True)
    st.caption("부정 비율이 높을수록 국제 언론이 해당 국가의 범죄 문제를 심각하게 보도한다는 의미입니다.")

    # 날짜별 감성 추이
    st.markdown("#### 📈 날짜별 평균 감성 점수 변화")

    def daily_sent(df, label):
        if df.empty: return pd.DataFrame()
        tmp = df.copy()
        tmp["날짜"] = pd.to_datetime(tmp["date"]).dt.date
        d = tmp.groupby("날짜")["polarity"].mean().reset_index()
        d.columns = ["날짜","평균 감성 점수"]
        d["국가"] = label
        return d

    daily_all = pd.concat([daily_sent(df1, C1), daily_sent(df2, C2)], ignore_index=True)
    if not daily_all.empty:
        fig_line = px.line(
            daily_all, x="날짜", y="평균 감성 점수", color="국가",
            color_discrete_sequence=["#60a5fa","#f97316"],
            title="날짜별 범죄 뉴스 감성 점수 변화",
        )
        fig_line.add_hline(y=0, line_dash="dot", line_color="#64748b",
                           annotation_text="중립선", annotation_font_color="#94a3b8")
        fig_line.update_layout(plot_bgcolor="#1e2535", paper_bgcolor="#1e2535", font_color="#e2e8f0")
        st.plotly_chart(fig_line, use_container_width=True)
        st.caption("0선 아래(부정)에 머물수록 해당 기간 범죄 관련 보도가 더 부정적이었음을 의미합니다.")

    # 가장 부정적 기사 Top 3
    st.markdown("#### ⚠️ 가장 부정적으로 보도된 기사 Top 3")
    neg1_col, neg2_col = st.columns(2)

    def show_top_neg(df, col, country):
        with col:
            st.markdown(f"**{country}**")
            if df.empty:
                st.info("기사 없음")
                return
            top = df.nsmallest(3, "polarity")
            for _, row in top.iterrows():
                try:
                    d_str = pd.to_datetime(row["date"]).strftime("%Y년 %m월 %d일")
                except:
                    d_str = "날짜 미상"
                emoji = SENTIMENT_EMOJI[row["sentiment"]]
                ko = SENTIMENT_KO[row["sentiment"]]
                st.markdown(f"""
<div class="article-card">
    <strong style="color:#f1f5f9;">{row['title'][:80]}...</strong><br>
    <small style="color:#64748b;">📅 {d_str} &nbsp; {emoji} {ko} &nbsp; 점수: {row['polarity']:+.3f}</small>
    <p style="margin-top:0.4rem;font-size:0.85rem;color:#94a3b8;">{row['description'][:150]}...</p>
</div>
""", unsafe_allow_html=True)

    show_top_neg(df1, neg1_col, C1)
    show_top_neg(df2, neg2_col, C2)


# ══════════════════════════════════════════════
# 탭4: 헤드라인 비교
# ══════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">📰 범죄 뉴스 헤드라인 비교</div>', unsafe_allow_html=True)

    filter_val = st.selectbox("감성 필터", ["전체","긍정","부정","중립"], key="hl_filter")
    filter_map = {"전체": None, "긍정": "Positive", "부정": "Negative", "중립": "Neutral"}
    filter_eng = filter_map[filter_val]

    hl1, hl2 = st.columns(2)

    def render_hl(df, country, col):
        with col:
            st.markdown(f"#### 🌍 {country}")
            if df.empty:
                st.info("기사가 없습니다.")
                return
            d = df.copy()
            if filter_eng:
                d = d[d["sentiment"] == filter_eng]
            d = d.head(20)
            if d.empty:
                st.info(f"'{filter_val}' 감성 기사가 없습니다.")
                return
            for _, row in d.iterrows():
                emoji = SENTIMENT_EMOJI.get(row["sentiment"], "😐")
                ko_s = SENTIMENT_KO.get(row["sentiment"], "중립")
                try:
                    ds = pd.to_datetime(row["date"]).strftime("%Y년 %m월 %d일")
                except:
                    ds = "날짜 미상"
                st.markdown(f"""
<div class="article-card">
    <strong style="color:#f1f5f9;">{row['title']}</strong><br>
    <small style="color:#64748b;">📅 {ds} &nbsp;|&nbsp; {emoji} {ko_s} ({row['polarity']:+.3f})</small>
    <p style="margin-top:0.4rem;font-size:0.85rem;color:#94a3b8;">{row['description'][:180]}...</p>
</div>
""", unsafe_allow_html=True)

    render_hl(df1, C1, hl1)
    render_hl(df2, C2, hl2)
    st.caption("최신 순 상위 20개 기사입니다. 기사 원문(영어)을 그대로 표시합니다.")


# ══════════════════════════════════════════════
# 탭5: 레이더 차트 (다차원 범죄 프로파일)
# ══════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">🗺️ 범죄 프로파일 레이더 차트</div>', unsafe_allow_html=True)
    st.caption("여러 지표를 0-100으로 정규화해 두 나라의 범죄 프로파일을 한눈에 비교합니다.")

    # 정규화: 각 지표를 0~100 스케일로
    radar_keys = ["crime_index","homicide_rate","robbery_rate","drug_offenses","assault_rate"]
    radar_labels = ["범죄 지수","살인율","강도율","마약 범죄","폭행률"]

    # 전체 국가 중 최댓값으로 정규화
    max_vals = {k: max(CRIME_STATS[c][k] for c in CRIME_STATS) for k in radar_keys}

    def normalize(country, key):
        return round(CRIME_STATS[country][key] / max_vals[key] * 100, 1)

    vals1 = [normalize(C1, k) for k in radar_keys]
    vals2 = [normalize(C2, k) for k in radar_keys]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=vals1 + [vals1[0]],
        theta=radar_labels + [radar_labels[0]],
        fill="toself",
        name=C1,
        line_color="#60a5fa",
        fillcolor="rgba(96,165,250,0.2)",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=vals2 + [vals2[0]],
        theta=radar_labels + [radar_labels[0]],
        fill="toself",
        name=C2,
        line_color="#f97316",
        fillcolor="rgba(249,115,22,0.2)",
    ))
    fig_radar.update_layout(
        polar=dict(
            bgcolor="#1e2535",
            radialaxis=dict(visible=True, range=[0,100], color="#64748b",
                            gridcolor="#334155", tickfont=dict(color="#94a3b8")),
            angularaxis=dict(color="#94a3b8", gridcolor="#334155"),
        ),
        showlegend=True,
        legend=dict(bgcolor="#252d40", bordercolor="#334155", font_color="#e2e8f0"),
        paper_bgcolor="#1e2535",
        font_color="#e2e8f0",
        title=f"범죄 프로파일 비교: {C1} vs {C2}",
        title_font_color="#e2e8f0",
        height=500,
    )
    st.plotly_chart(fig_radar, use_container_width=True)
    st.caption("각 수치는 분석 대상 20개국 중 최댓값을 100으로 정규화한 상대적 위험도입니다.")

    # 안전도 게이지
    st.markdown("#### 🛡️ 안전 지수 게이지")
    g1, g2 = st.columns(2)

    def safety_gauge(country, safety_val):
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=safety_val,
            title={"text": f"{country} 안전 지수", "font": {"color":"#e2e8f0"}},
            number={"font": {"color":"#f59e0b", "size":40}},
            gauge={
                "axis": {"range":[0,100], "tickcolor":"#94a3b8"},
                "bar": {"color": "#22c55e" if safety_val >= 60 else ("#f59e0b" if safety_val >= 40 else "#ef4444")},
                "bgcolor": "#1e2535",
                "bordercolor": "#334155",
                "steps": [
                    {"range":[0,40], "color":"#2d1515"},
                    {"range":[40,70], "color":"#2d2515"},
                    {"range":[70,100], "color":"#152d1e"},
                ],
                "threshold": {"line":{"color":"#f59e0b","width":3}, "thickness":0.75, "value":50},
            }
        ))
        fig.update_layout(paper_bgcolor="#1e2535", font_color="#e2e8f0", height=280)
        return fig

    with g1:
        st.plotly_chart(safety_gauge(C1, stats1["safety_index"]), use_container_width=True)
    with g2:
        st.plotly_chart(safety_gauge(C2, stats2["safety_index"]), use_container_width=True)
    st.caption("안전 지수가 70 이상이면 녹색(안전), 40~70은 노란색(주의), 40 미만은 빨간색(위험)으로 표시됩니다.")


# ══════════════════════════════════════════════
# 탭6: 종합 리포트
# ══════════════════════════════════════════════
with tab6:
    st.markdown('<div class="section-header">📋 종합 분석 리포트</div>', unsafe_allow_html=True)

    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    today_en  = datetime.datetime.now().strftime("%Y-%m-%d")

    # 종합 위험도 판단
    safer = C2 if stats1["crime_index"] > stats2["crime_index"] else C1
    more_dangerous = C1 if safer == C2 else C2
    diff_ci = abs(stats1["crime_index"] - stats2["crime_index"])

    # 뉴스 감성 비교
    more_neg_news = C1 if avg1 < avg2 else C2

    top1_word = freq1.most_common(1)[0][0] if freq1 else "N/A"
    top2_word = freq2.most_common(1)[0][0] if freq2 else "N/A"

    summary_ko = f"""
📋 종합 분석 리포트
분석 일시: {today_str} | 기간: 최근 {days_filter}일

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[통계 수치 비교]

🌍 {C1} ({stats1['region']})
  - 범죄 지수: {stats1['crime_index']} / 안전 지수: {stats1['safety_index']}
  - 살인율: {stats1['homicide_rate']}명 / 강도율: {stats1['robbery_rate']}건 (인구 10만 명당)
  - 마약 범죄: {stats1['drug_offenses']}건 / 폭행률: {stats1['assault_rate']}건
  - 청렴도 지수: {stats1['corruption_index']} / 수감자: {stats1['prison_population']}명

🌍 {C2} ({stats2['region']})
  - 범죄 지수: {stats2['crime_index']} / 안전 지수: {stats2['safety_index']}
  - 살인율: {stats2['homicide_rate']}명 / 강도율: {stats2['robbery_rate']}건 (인구 10만 명당)
  - 마약 범죄: {stats2['drug_offenses']}건 / 폭행률: {stats2['assault_rate']}건
  - 청렴도 지수: {stats2['corruption_index']} / 수감자: {stats2['prison_population']}명

[통계 결론]
{more_dangerous}이(가) 범죄 지수 기준 {diff_ci:.1f}점 더 높아 상대적으로 위험합니다.
{safer}이(가) 전반적으로 더 안전한 국가로 분류됩니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[뉴스 보도 분석]

{C1}: 기사 {len(df1)}건 수집 / 평균 감성 점수 {avg1:+.3f} ({SENTIMENT_KO[lbl1]})
  주요 등장 단어: {', '.join([w for w,_ in freq1.most_common(5)])}

{C2}: 기사 {len(df2)}건 수집 / 평균 감성 점수 {avg2:+.3f} ({SENTIMENT_KO[lbl2]})
  주요 등장 단어: {', '.join([w for w,_ in freq2.most_common(5)])}

[뉴스 결론]
국제 언론은 {more_neg_news} 관련 범죄 뉴스를 더 부정적으로 보도하는 경향이 있습니다.
    """.strip()

    st.markdown(f"""
<div style="background:#1e2535;border:1px solid #334155;border-radius:12px;padding:1.5rem;">
<pre style="white-space:pre-wrap;font-family:'Noto Sans KR',sans-serif;font-size:0.9rem;color:#e2e8f0;line-height:1.8;">{summary_ko}</pre>
</div>
""", unsafe_allow_html=True)

    # 영어 다운로드 리포트
    report_en = f"""
COUNTRY CRIME COMPARISON REPORT
================================
Date: {today_en} | Period: Last {days_filter} days

--- {C1} ({stats1['region']}) ---
Crime Index    : {stats1['crime_index']}
Safety Index   : {stats1['safety_index']}
Homicide Rate  : {stats1['homicide_rate']} per 100k
Robbery Rate   : {stats1['robbery_rate']} per 100k
Drug Offenses  : {stats1['drug_offenses']} per 100k
Assault Rate   : {stats1['assault_rate']} per 100k
Corruption Idx : {stats1['corruption_index']}
Prison Pop.    : {stats1['prison_population']} per 100k
Police per 100k: {stats1['police_per_100k']}
News Collected : {len(df1)} articles
Avg Sentiment  : {avg1:+.4f} ({lbl1})
Top Words      : {', '.join([w for w,_ in freq1.most_common(5)])}

--- {C2} ({stats2['region']}) ---
Crime Index    : {stats2['crime_index']}
Safety Index   : {stats2['safety_index']}
Homicide Rate  : {stats2['homicide_rate']} per 100k
Robbery Rate   : {stats2['robbery_rate']} per 100k
Drug Offenses  : {stats2['drug_offenses']} per 100k
Assault Rate   : {stats2['assault_rate']} per 100k
Corruption Idx : {stats2['corruption_index']}
Prison Pop.    : {stats2['prison_population']} per 100k
Police per 100k: {stats2['police_per_100k']}
News Collected : {len(df2)} articles
Avg Sentiment  : {avg2:+.4f} ({lbl2})
Top Words      : {', '.join([w for w,_ in freq2.most_common(5)])}

--- CONCLUSION ---
More Dangerous (by Crime Index): {more_dangerous} (diff: {diff_ci:.1f})
More Negatively Covered (News) : {more_neg_news}
Safer Country                  : {safer}

Data Sources: Numbeo 2023-2024, UNODC, World Population Review, Google News RSS
Sentiment Analysis: TextBlob
    """.strip()

    st.download_button(
        label="📥 리포트 .txt로 다운로드",
        data=report_en,
        file_name=f"crime_report_{C1}_vs_{C2}_{today_en}.txt",
        mime="text/plain",
    )

    # 비교 요약 테이블
    st.markdown("#### 📊 핵심 지표 비교 요약")
    summary_table = pd.DataFrame({
        "항목": [
            "범죄 지수", "안전 지수", "살인율 (10만명당)", "강도율 (10만명당)",
            "수집 뉴스 기사 수", "평균 감성 점수", "부정 기사 비율", "주요 뉴스 키워드"
        ],
        C1: [
            stats1["crime_index"], stats1["safety_index"],
            stats1["homicide_rate"], stats1["robbery_rate"],
            len(df1), f"{avg1:+.3f} ({SENTIMENT_KO[lbl1]})",
            f"{round(cnt1['Negative']/max(sum(cnt1.values()),1)*100,1)}%",
            ", ".join([w for w,_ in freq1.most_common(3)]),
        ],
        C2: [
            stats2["crime_index"], stats2["safety_index"],
            stats2["homicide_rate"], stats2["robbery_rate"],
            len(df2), f"{avg2:+.3f} ({SENTIMENT_KO[lbl2]})",
            f"{round(cnt2['Negative']/max(sum(cnt2.values()),1)*100,1)}%",
            ", ".join([w for w,_ in freq2.most_common(3)]),
        ],
    })
    st.dataframe(summary_table, use_container_width=True, hide_index=True)
    st.caption("통계 수치(Numbeo·UNODC)와 실시간 뉴스 데이터(Google News RSS)를 결합한 종합 비교표입니다.")
