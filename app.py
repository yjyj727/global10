"""
미디어 비교 분석 대시보드
같은 키워드를 두 미디어가 어떻게 다르게 보도하는지 실시간으로 비교 분석
"""

import html as _html
import re
import io
import datetime
from collections import Counter

import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
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
    page_title="미디어 비교 분석 대시보드",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 상수 정의
# ─────────────────────────────────────────────
MEDIA_DOMAINS = {
    "BBC":             "bbc.com",
    "Al Jazeera":      "aljazeera.com",
    "Reuters":         "reuters.com",
    "CNN":             "cnn.com",
    "The Guardian":    "theguardian.com",
    "NY Times":        "nytimes.com",
    "Washington Post": "washingtonpost.com",
    "Fox News":        "foxnews.com",
    "Deutsche Welle":  "dw.com",
    "France 24":       "france24.com",
}

# 감성 한국어 라벨 매핑
SENTIMENT_KO = {
    "Positive": "긍정",
    "Negative": "부정",
    "Neutral":  "중립",
}

# 감성 필터 매핑
FILTER_MAP = {
    "전체":   None,
    "긍정":   "Positive",
    "부정":   "Negative",
    "중립":   "Neutral",
}

# 감성 이모지
SENTIMENT_EMOJI = {
    "Positive": "😊",
    "Negative": "😟",
    "Neutral":  "😐",
}

# 감성 색상
SENTIMENT_COLOR = {
    "Positive": "#22c55e",
    "Negative": "#ef4444",
    "Neutral":  "#9ca3af",
}

# ─────────────────────────────────────────────
# 불용어 정의
# ─────────────────────────────────────────────
BASE_STOPWORDS = {
    # 영어 문법어
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
    # HTML 태그명
    "html","head","body","div","span","table","tbody","thead",
    "tfoot","tr","td","th","ul","ol","li","nav","header","footer",
    "main","section","article","aside","form","input","button",
    "label","select","option","img","script","style","link","meta",
    "iframe","embed","object","param","video","audio","source",
    "canvas","svg","path","rect","circle","text","tspan","pre",
    "code","blockquote","figure","figcaption","strong","small",
    "mark","abbr","cite","time","data","src","alt",
    # HTML 속성명
    "href","rel","type","name","class","target","width","height",
    "align","valign","border","cellpadding","cellspacing",
    "colspan","rowspan","bgcolor","style","onclick","onload",
    # CSS 속성·값
    "color","font","size","face","bold","italic","normal","none",
    "block","inline","flex","grid","auto","solid","hidden",
    "visible","scroll","pointer","cursor","margin","padding",
    "display","position","absolute","relative","background",
    "transparent","inherit","important",
    # HTML 엔티티 잔재
    "nbsp","amp","quot","apos","lt","gt","lte","gte",
    "ndash","mdash","laquo","raquo","ldquo","rdquo",
    "hellip","rsquo","lsquo","bull","middot","copy",
    "reg","trade","euro","pound","yen","cent",
    # RSS·URL 노이즈
    "rss","xml","feed","atom","google","news","articles","article",
    "read","more","full","story","click","here",
    "com","www","http","https","utm","via","per","net","org",
    # 뉴스 공통 반복 단어
    "report","reported","reporting","reports","according",
    "told","added","noted","stated","announced","officials",
    "government","people","world","including",
}


def get_stopwords(keyword: str, media_names: list = None) -> set:
    """키워드와 미디어명을 불용어에 추가해서 반환"""
    extra = set(keyword.lower().split())
    media_tokens = set()
    if media_names:
        for name in media_names:
            media_tokens.update(re.findall(r"[a-zA-Z]+", name.lower()))
            domain = MEDIA_DOMAINS.get(name, "")
            media_tokens.update(re.findall(r"[a-zA-Z]+", domain.lower()))
    return BASE_STOPWORDS | extra | media_tokens


# ─────────────────────────────────────────────
# description 정제 함수
# ─────────────────────────────────────────────
def clean_description(desc_t) -> str:
    """RSS description 필드의 HTML/엔티티 제거 5단계 파이프라인"""
    raw = str(desc_t)
    raw = re.sub(r"<[^>]+>", " ", raw)           # 1) 태그+속성값 제거
    raw = _html.unescape(raw)                      # 2) 엔티티 디코딩
    raw = re.sub(r"&[a-zA-Z]{2,10};", " ", raw)   # 3) 잔여 엔티티 제거
    raw = re.sub(r"https?://\S+", " ", raw)        # 4) URL 제거
    raw = re.sub(r"\s+", " ", raw).strip()         # 5) 공백 정리
    return raw[:400]


# ─────────────────────────────────────────────
# 텍스트 빈도 추출 함수
# ─────────────────────────────────────────────
def extract_word_freq(texts: list, stopwords: set) -> Counter:
    """HTML 제거 후 단어 빈도 카운터 반환"""
    all_words = []
    for text in texts:
        t = str(text)
        t = re.sub(r"<[^>]+>", " ", t)            # HTML 태그+속성값 제거
        t = _html.unescape(t)                       # 엔티티 디코딩
        t = re.sub(r"&[a-zA-Z]{2,10};", " ", t)   # 잔여 엔티티 제거
        t = re.sub(r"https?://\S+", " ", t)         # URL 제거
        t = re.sub(r"www\.\S+", " ", t)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", t.lower())
        all_words.extend([w for w in words if w not in stopwords])
    return Counter(all_words)


# ─────────────────────────────────────────────
# 감성 분석 함수
# ─────────────────────────────────────────────
def analyze_sentiment(text: str) -> tuple:
    """TextBlob으로 감성 분석 → (라벨, 점수)"""
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
# RSS 수집 함수 (캐시 30분)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_articles(keyword: str, media: str, days_filter: int = 30) -> pd.DataFrame:
    """Google News RSS에서 기사 수집 후 DataFrame 반환"""
    domain = MEDIA_DOMAINS.get(media, "")
    encoded_kw = quote(keyword)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded_kw}+site:{domain}&hl=en&gl=US&ceid=US:en"
    )
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml-xml")
        items = soup.find_all("item")

        rows = []
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_filter)

        for item in items:
            # 제목
            title_tag = item.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 날짜
            pub_tag = item.find("pubDate")
            pub_raw = pub_tag.get_text(strip=True) if pub_tag else ""
            try:
                pub_dt = dateutil_parser.parse(pub_raw)
                # timezone-naive 변환
                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.replace(tzinfo=None)
            except Exception:
                pub_dt = datetime.datetime.now()

            # 날짜 필터 적용
            if pub_dt < cutoff_date:
                continue

            # 요약 (description 정제)
            desc_tag = item.find("description")
            desc = clean_description(desc_tag) if desc_tag else ""

            # 출처
            source_tag = item.find("source")
            source = source_tag.get_text(strip=True) if source_tag else media

            # 감성 분석
            sentiment_label, polarity = analyze_sentiment(title + " " + desc)

            rows.append({
                "title":     title,
                "date":      pub_dt,
                "description": desc,
                "source":    source,
                "sentiment": sentiment_label,
                "polarity":  round(polarity, 4),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("date", ascending=False).reset_index(drop=True)
        return df

    except Exception as e:
        st.warning(f"⚠️ {media} 기사 수집 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# 워드클라우드 생성 함수
# ─────────────────────────────────────────────
def make_wordcloud(freq: Counter, colormap: str) -> plt.Figure:
    """빈도 Counter로 워드클라우드 Figure 생성"""
    if not freq:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center", fontsize=16)
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
if "last_keyword" not in st.session_state:
    st.session_state.last_keyword = ""
if "last_m1" not in st.session_state:
    st.session_state.last_m1 = "BBC"
if "last_m2" not in st.session_state:
    st.session_state.last_m2 = "Al Jazeera"
if "triggered" not in st.session_state:
    st.session_state.triggered = False


# ─────────────────────────────────────────────
# 커스텀 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}
.main-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 1rem;
    color: #64748b;
    margin-bottom: 1.5rem;
}
.metric-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}
.sentiment-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}
.badge-positive { background: #dcfce7; color: #15803d; }
.badge-negative { background: #fee2e2; color: #b91c1c; }
.badge-neutral  { background: #f1f5f9; color: #475569; }
.article-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.7rem;
    border-left: 4px solid #3b82f6;
}
.history-item {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 0.4rem 0.8rem;
    margin-bottom: 0.3rem;
    font-size: 0.85rem;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">📰 같은 사건, 두 미디어는 어떻게 다르게 보도할까?</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">검색어를 입력하고 두 미디어를 선택하면 보도 방식의 차이를 분석해드립니다.</div>', unsafe_allow_html=True)
st.divider()


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🕐 최근 검색 기록")
    if st.session_state.search_history:
        for hist in reversed(st.session_state.search_history[-5:]):
            if st.button(f"🔍 {hist['keyword']} ({hist['m1']} vs {hist['m2']})",
                         key=f"hist_{hist['keyword']}_{hist['m1']}_{hist['m2']}",
                         use_container_width=True):
                st.session_state.last_keyword = hist["keyword"]
                st.session_state.last_m1 = hist["m1"]
                st.session_state.last_m2 = hist["m2"]
                st.session_state.triggered = True
                st.rerun()
    else:
        st.caption("아직 검색 기록이 없습니다.")

    st.divider()
    st.header("📅 날짜 필터")
    days_filter = st.slider("최근 N일 기사 포함", min_value=7, max_value=90, value=30, step=7)

    st.divider()
    st.header("🔢 최소 기사 수")
    min_articles = st.slider("분석 최소 기사 수 기준", min_value=1, max_value=20, value=3)

    st.divider()
    st.header("📌 앱 소개")
    st.markdown("""
- **데이터 출처**: Google News RSS
- **감성 분석**: TextBlob
- **제작**: Streamlit
- **캐시 갱신**: 30분마다
    """)


# ─────────────────────────────────────────────
# 검색 영역
# ─────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

media_list = list(MEDIA_DOMAINS.keys())

with col1:
    keyword_input = st.text_input(
        "🔍 검색어",
        value=st.session_state.last_keyword,
        placeholder="예: Gaza, AI regulation, climate",
        key="keyword_widget",
    )

with col2:
    m1_idx = media_list.index(st.session_state.last_m1) if st.session_state.last_m1 in media_list else 0
    m1_input = st.selectbox("📺 미디어 1", media_list, index=m1_idx, key="m1_widget")

with col3:
    m2_idx = media_list.index(st.session_state.last_m2) if st.session_state.last_m2 in media_list else 1
    m2_input = st.selectbox("📺 미디어 2", media_list, index=m2_idx, key="m2_widget")

with col4:
    st.markdown("<br>", unsafe_allow_html=True)
    search_btn = st.button("🔍 비교 분석", use_container_width=True, type="primary")

# 버튼 클릭 또는 히스토리 재실행 처리
if search_btn:
    st.session_state.triggered = True
    st.session_state.last_keyword = keyword_input
    st.session_state.last_m1 = m1_input
    st.session_state.last_m2 = m2_input

# 현재 검색 상태 읽기
KEYWORD = st.session_state.last_keyword.strip()
M1 = st.session_state.last_m1
M2 = st.session_state.last_m2


# ─────────────────────────────────────────────
# 입력 검증
# ─────────────────────────────────────────────
if not st.session_state.triggered or not KEYWORD:
    st.info("👆 검색어를 입력하고 미디어 2개를 선택해주세요.")
    st.stop()

if M1 == M2:
    st.warning("⚠️ 서로 다른 미디어 2개를 선택해주세요.")
    st.stop()


# ─────────────────────────────────────────────
# 검색 기록 업데이트
# ─────────────────────────────────────────────
new_entry = {"keyword": KEYWORD, "m1": M1, "m2": M2}
if new_entry not in st.session_state.search_history:
    st.session_state.search_history.append(new_entry)
    if len(st.session_state.search_history) > 10:
        st.session_state.search_history = st.session_state.search_history[-10:]


# ─────────────────────────────────────────────
# 기사 수집
# ─────────────────────────────────────────────
with st.spinner(f"📡 {M1} 기사를 가져오는 중입니다..."):
    df1 = fetch_articles(KEYWORD, M1, days_filter)

with st.spinner(f"📡 {M2} 기사를 가져오는 중입니다..."):
    df2 = fetch_articles(KEYWORD, M2, days_filter)

# 기사 0개 경고
if df1.empty:
    st.warning(f"⚠️ '{KEYWORD}'에 대한 {M1} 기사를 찾을 수 없습니다. 다른 검색어를 시도해보세요.")
if df2.empty:
    st.warning(f"⚠️ '{KEYWORD}'에 대한 {M2} 기사를 찾을 수 없습니다. 다른 검색어를 시도해보세요.")
if df1.empty and df2.empty:
    st.stop()

# 최소 기사 수 경고
if not df1.empty and len(df1) < min_articles:
    st.warning(f"ℹ️ {M1}에서 {len(df1)}개의 기사만 수집되었습니다 (설정 최소: {min_articles}개).")
if not df2.empty and len(df2) < min_articles:
    st.warning(f"ℹ️ {M2}에서 {len(df2)}개의 기사만 수집되었습니다 (설정 최소: {min_articles}개).")


# ─────────────────────────────────────────────
# 기본 통계 계산
# ─────────────────────────────────────────────
def sentiment_stats(df: pd.DataFrame):
    """감성 통계 반환"""
    if df.empty:
        return 0.0, "Neutral", {"Positive": 0, "Negative": 0, "Neutral": 0}
    avg_pol = df["polarity"].mean()
    if avg_pol > 0.05:
        label = "Positive"
    elif avg_pol < -0.05:
        label = "Negative"
    else:
        label = "Neutral"
    counts = df["sentiment"].value_counts().to_dict()
    for k in ["Positive", "Negative", "Neutral"]:
        counts.setdefault(k, 0)
    return round(avg_pol, 3), label, counts

avg1, lbl1, cnt1 = sentiment_stats(df1)
avg2, lbl2, cnt2 = sentiment_stats(df2)
sentiment_diff = round(abs(avg1 - avg2), 3)

# 불용어 생성
sw = get_stopwords(KEYWORD, media_names=[M1, M2])

# 텍스트 빈도
texts1 = (df1["title"] + " " + df1["description"]).tolist() if not df1.empty else []
texts2 = (df2["title"] + " " + df2["description"]).tolist() if not df2.empty else []
freq1 = extract_word_freq(texts1, sw)
freq2 = extract_word_freq(texts2, sw)


# ─────────────────────────────────────────────
# 상단 메트릭 카드
# ─────────────────────────────────────────────
st.markdown("---")
mc1, mc2, mc3, mc4, mc5 = st.columns(5)

badge_class1 = f"badge-{lbl1.lower()}"
badge_class2 = f"badge-{lbl2.lower()}"

with mc1:
    st.metric(f"📰 {M1} 기사 수", len(df1))
with mc2:
    st.metric(f"📰 {M2} 기사 수", len(df2))
with mc3:
    ko1 = SENTIMENT_KO[lbl1]
    st.metric(f"😊 {M1} 감성", f"{ko1} ({avg1:+.3f})")
with mc4:
    ko2 = SENTIMENT_KO[lbl2]
    st.metric(f"😊 {M2} 감성", f"{ko2} ({avg2:+.3f})")
with mc5:
    st.metric("📊 감성 점수 차이", f"{sentiment_diff:.3f}")

st.markdown("---")


# ─────────────────────────────────────────────
# 5개 탭
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "☁️ 워드클라우드",
    "🔤 차별화 단어",
    "😊 감성 비교",
    "📰 헤드라인 비교",
    "📊 요약 리포트",
])


# ═══════════════════════════════════════════
# 탭1: 워드클라우드
# ═══════════════════════════════════════════
with tab1:
    wc_col1, wc_col2 = st.columns(2)

    with wc_col1:
        st.subheader(f"☁️ {M1} 워드클라우드")
        fig_wc1 = make_wordcloud(freq1, "Blues")
        st.pyplot(fig_wc1, use_container_width=True)
        plt.close(fig_wc1)

    with wc_col2:
        st.subheader(f"☁️ {M2} 워드클라우드")
        fig_wc2 = make_wordcloud(freq2, "Oranges")
        st.pyplot(fig_wc2, use_container_width=True)
        plt.close(fig_wc2)

    st.caption("두 미디어에서 자주 등장한 단어를 크기로 표현합니다. 클수록 많이 사용된 단어입니다.")

    # 상위 15개 단어 비교 그룹 바 차트
    st.subheader("📊 상위 15개 단어 비교")

    top15_1 = dict(freq1.most_common(15))
    top15_2 = dict(freq2.most_common(15))
    all_words_15 = list(dict.fromkeys(list(top15_1.keys()) + list(top15_2.keys())))[:15]

    bar_df = pd.DataFrame({
        "단어": all_words_15 * 2,
        "빈도": [top15_1.get(w, 0) for w in all_words_15] + [top15_2.get(w, 0) for w in all_words_15],
        "미디어": [M1] * len(all_words_15) + [M2] * len(all_words_15),
    })

    fig_bar = px.bar(
        bar_df, x="단어", y="빈도", color="미디어",
        barmode="group",
        labels={"단어": "단어", "빈도": "빈도", "미디어": "미디어"},
        title=f"상위 15개 단어 빈도 비교: {M1} vs {M2}",
        color_discrete_sequence=["#3b82f6", "#f97316"],
    )
    fig_bar.update_layout(plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_bar, use_container_width=True)
    st.caption("두 미디어의 상위 15개 단어를 빈도 기준으로 나란히 비교합니다. 높은 막대일수록 해당 미디어에서 자주 사용된 단어입니다.")


# ═══════════════════════════════════════════
# 탭2: 차별화 단어
# ═══════════════════════════════════════════
with tab2:
    set1 = set(freq1.keys())
    set2 = set(freq2.keys())
    only1 = {w: freq1[w] for w in set1 - set2}
    only2 = {w: freq2[w] for w in set2 - set1}
    common = {w: (freq1[w] + freq2[w]) for w in set1 & set2}

    top_only1 = sorted(only1.items(), key=lambda x: -x[1])[:10]
    top_only2 = sorted(only2.items(), key=lambda x: -x[1])[:10]
    top_common = sorted(common.items(), key=lambda x: -x[1])[:10]

    uc1, uc2, uc3 = st.columns(3)

    with uc1:
        st.markdown(f"### 🔵 {M1} 고유 단어 Top 10")
        if top_only1:
            df_u1 = pd.DataFrame(top_only1, columns=["단어", "빈도"])
            fig_u1 = px.bar(df_u1, x="빈도", y="단어", orientation="h",
                            color_discrete_sequence=["#3b82f6"],
                            labels={"빈도": "빈도", "단어": "단어"})
            fig_u1.update_layout(yaxis=dict(autorange="reversed"),
                                  plot_bgcolor="white", paper_bgcolor="white",
                                  showlegend=False, height=350)
            st.plotly_chart(fig_u1, use_container_width=True)
        else:
            st.info("고유 단어가 없습니다.")

    with uc2:
        st.markdown("### 🟣 공통 단어 Top 10")
        if top_common:
            df_c = pd.DataFrame(top_common, columns=["단어", "합산 빈도"])
            fig_c = px.bar(df_c, x="합산 빈도", y="단어", orientation="h",
                           color_discrete_sequence=["#8b5cf6"],
                           labels={"합산 빈도": "합산 빈도", "단어": "단어"})
            fig_c.update_layout(yaxis=dict(autorange="reversed"),
                                  plot_bgcolor="white", paper_bgcolor="white",
                                  showlegend=False, height=350)
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("공통 단어가 없습니다.")

    with uc3:
        st.markdown(f"### 🟠 {M2} 고유 단어 Top 10")
        if top_only2:
            df_u2 = pd.DataFrame(top_only2, columns=["단어", "빈도"])
            fig_u2 = px.bar(df_u2, x="빈도", y="단어", orientation="h",
                            color_discrete_sequence=["#f97316"],
                            labels={"빈도": "빈도", "단어": "단어"})
            fig_u2.update_layout(yaxis=dict(autorange="reversed"),
                                  plot_bgcolor="white", paper_bgcolor="white",
                                  showlegend=False, height=350)
            st.plotly_chart(fig_u2, use_container_width=True)
        else:
            st.info("고유 단어가 없습니다.")

    st.caption("각 미디어만 사용한 단어(고유 단어)와 두 미디어 모두 사용한 단어(공통 단어)를 빈도 순으로 표시합니다.")

    # 자동 인사이트 문구
    if top_only1 and top_only2:
        w1a = top_only1[0][0] if len(top_only1) > 0 else "-"
        w1b = top_only1[1][0] if len(top_only1) > 1 else "-"
        w2a = top_only2[0][0] if len(top_only2) > 0 else "-"
        w2b = top_only2[1][0] if len(top_only2) > 1 else "-"
        st.info(
            f"💡 **인사이트**: {M1}는 '{w1a}', '{w1b}' 같은 단어를 주로 사용하는 반면, "
            f"{M2}는 '{w2a}', '{w2b}'에 더 집중하는 경향이 있습니다. "
            f"이는 두 미디어가 '{KEYWORD}' 주제를 서로 다른 측면에서 조명하고 있음을 시사합니다."
        )


# ═══════════════════════════════════════════
# 탭3: 감성 비교
# ═══════════════════════════════════════════
with tab3:
    donut1, donut2 = st.columns(2)

    def make_donut(counts: dict, title: str) -> go.Figure:
        """감성 도넛 차트 생성"""
        labels_ko = [SENTIMENT_KO[k] for k in ["Positive", "Negative", "Neutral"]]
        values = [counts["Positive"], counts["Negative"], counts["Neutral"]]
        colors = [SENTIMENT_COLOR["Positive"], SENTIMENT_COLOR["Negative"], SENTIMENT_COLOR["Neutral"]]
        fig = go.Figure(data=[go.Pie(
            labels=labels_ko, values=values,
            hole=0.55,
            marker_colors=colors,
        )])
        fig.update_layout(
            title_text=title, title_x=0.5,
            showlegend=True,
            plot_bgcolor="white", paper_bgcolor="white",
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        )
        return fig

    with donut1:
        fig_d1 = make_donut(cnt1, f"{M1} 감성 분포")
        st.plotly_chart(fig_d1, use_container_width=True)

    with donut2:
        fig_d2 = make_donut(cnt2, f"{M2} 감성 분포")
        st.plotly_chart(fig_d2, use_container_width=True)

    st.caption("도넛 차트는 각 미디어 기사의 긍정·부정·중립 비율을 보여줍니다.")

    # 감성 비율 그룹 바 차트
    st.subheader(f"감성 분포 비교: {M1} vs {M2}")

    total1 = max(sum(cnt1.values()), 1)
    total2 = max(sum(cnt2.values()), 1)
    sent_labels = ["긍정", "부정", "중립"]
    eng_labels  = ["Positive", "Negative", "Neutral"]

    bar_sent_df = pd.DataFrame({
        "감성": sent_labels * 2,
        "비율 (%)": [
            round(cnt1[k] / total1 * 100, 1) for k in eng_labels
        ] + [
            round(cnt2[k] / total2 * 100, 1) for k in eng_labels
        ],
        "미디어": [M1] * 3 + [M2] * 3,
    })

    fig_sent_bar = px.bar(
        bar_sent_df, x="감성", y="비율 (%)", color="미디어",
        barmode="group",
        labels={"감성": "감성", "비율 (%)": "비율 (%)", "미디어": "미디어"},
        title=f"감성 분포 비교: {M1} vs {M2}",
        color_discrete_sequence=["#3b82f6", "#f97316"],
    )
    fig_sent_bar.update_layout(plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_sent_bar, use_container_width=True)
    st.caption("두 미디어의 긍정·부정·중립 기사 비율을 백분율로 비교합니다.")

    # 날짜별 감성 추이 라인 차트
    st.subheader("날짜별 감성 점수 변화")

    def daily_sentiment(df: pd.DataFrame, label: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        tmp = df.copy()
        tmp["날짜"] = pd.to_datetime(tmp["date"]).dt.date
        daily = tmp.groupby("날짜")["polarity"].mean().reset_index()
        daily.columns = ["날짜", "평균 감성 점수"]
        daily["미디어"] = label
        return daily

    daily1 = daily_sentiment(df1, M1)
    daily2 = daily_sentiment(df2, M2)
    daily_all = pd.concat([daily1, daily2], ignore_index=True)

    if not daily_all.empty:
        fig_line = px.line(
            daily_all, x="날짜", y="평균 감성 점수", color="미디어",
            labels={"날짜": "날짜", "평균 감성 점수": "평균 감성 점수", "미디어": "미디어"},
            title="날짜별 감성 점수 변화",
            color_discrete_sequence=["#3b82f6", "#f97316"],
        )
        # 중립선 점선 추가
        fig_line.add_hline(y=0, line_dash="dot", line_color="gray",
                           annotation_text="중립선", annotation_position="right")
        fig_line.update_layout(plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_line, use_container_width=True)
        st.caption("날짜별 평균 감성 점수 추이입니다. 점선(중립선) 위는 긍정적, 아래는 부정적 보도 경향을 나타냅니다.")

    # 가장 긍정적/부정적 기사 Top 3
    st.subheader("✨ 가장 긍정적인 기사 Top 3")
    pos_col1, pos_col2 = st.columns(2)

    def top_articles(df: pd.DataFrame, ascending: bool, n: int = 3) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        return df.nsmallest(n, "polarity") if ascending else df.nlargest(n, "polarity")

    with pos_col1:
        st.markdown(f"**{M1}**")
        top_pos1 = top_articles(df1, ascending=False)
        if not top_pos1.empty:
            disp = top_pos1[["title", "date", "sentiment", "polarity"]].copy()
            disp["감성"] = disp["sentiment"].map(SENTIMENT_KO)
            disp["날짜"] = pd.to_datetime(disp["date"]).dt.strftime("%Y년 %m월 %d일")
            disp = disp[["title", "날짜", "감성", "polarity"]]
            disp.columns = ["제목", "날짜", "감성", "점수"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with pos_col2:
        st.markdown(f"**{M2}**")
        top_pos2 = top_articles(df2, ascending=False)
        if not top_pos2.empty:
            disp = top_pos2[["title", "date", "sentiment", "polarity"]].copy()
            disp["감성"] = disp["sentiment"].map(SENTIMENT_KO)
            disp["날짜"] = pd.to_datetime(disp["date"]).dt.strftime("%Y년 %m월 %d일")
            disp = disp[["title", "날짜", "감성", "polarity"]]
            disp.columns = ["제목", "날짜", "감성", "점수"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

    st.subheader("⚠️ 가장 부정적인 기사 Top 3")
    neg_col1, neg_col2 = st.columns(2)

    with neg_col1:
        st.markdown(f"**{M1}**")
        top_neg1 = top_articles(df1, ascending=True)
        if not top_neg1.empty:
            disp = top_neg1[["title", "date", "sentiment", "polarity"]].copy()
            disp["감성"] = disp["sentiment"].map(SENTIMENT_KO)
            disp["날짜"] = pd.to_datetime(disp["date"]).dt.strftime("%Y년 %m월 %d일")
            disp = disp[["title", "날짜", "감성", "polarity"]]
            disp.columns = ["제목", "날짜", "감성", "점수"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with neg_col2:
        st.markdown(f"**{M2}**")
        top_neg2 = top_articles(df2, ascending=True)
        if not top_neg2.empty:
            disp = top_neg2[["title", "date", "sentiment", "polarity"]].copy()
            disp["감성"] = disp["sentiment"].map(SENTIMENT_KO)
            disp["날짜"] = pd.to_datetime(disp["date"]).dt.strftime("%Y년 %m월 %d일")
            disp = disp[["title", "날짜", "감성", "점수"]
            ].copy() if False else disp[["title", "날짜", "감성", "polarity"]].copy()
            disp.columns = ["제목", "날짜", "감성", "점수"]
            st.dataframe(disp, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════
# 탭4: 헤드라인 비교
# ═══════════════════════════════════════════
with tab4:
    st.subheader("📰 헤드라인 비교")

    filter_val = st.selectbox("감성 필터", list(FILTER_MAP.keys()), key="sentiment_filter")
    filter_eng = FILTER_MAP[filter_val]

    hl_col1, hl_col2 = st.columns(2)

    def render_headlines(df: pd.DataFrame, filter_eng: str, media_name: str):
        """기사 카드 형식으로 표시"""
        if df.empty:
            st.info("기사가 없습니다.")
            return

        display = df.copy()
        if filter_eng:
            display = display[display["sentiment"] == filter_eng]

        display = display.head(20)

        if display.empty:
            st.info(f"'{filter_val}' 감성의 기사가 없습니다.")
            return

        for _, row in display.iterrows():
            emoji = SENTIMENT_EMOJI.get(row["sentiment"], "😐")
            badge_class = f"badge-{row['sentiment'].lower()}"
            ko_sent = SENTIMENT_KO.get(row["sentiment"], "중립")
            try:
                date_str = pd.to_datetime(row["date"]).strftime("%Y년 %m월 %d일")
            except Exception:
                date_str = "날짜 미상"

            st.markdown(f"""
<div class="article-card">
    <strong>{row['title']}</strong><br>
    <small style="color:#64748b;">📅 {date_str} &nbsp;|&nbsp; 
    <span class="sentiment-badge {badge_class}">{emoji} {ko_sent}</span>
    &nbsp;|&nbsp; 점수: {row['polarity']:+.3f}</small>
    <p style="margin-top:0.5rem;font-size:0.88rem;color:#374151;">{row['description'][:200]}...</p>
</div>
""", unsafe_allow_html=True)

    with hl_col1:
        st.markdown(f"#### {M1}")
        render_headlines(df1, filter_eng, M1)

    with hl_col2:
        st.markdown(f"#### {M2}")
        render_headlines(df2, filter_eng, M2)

    st.caption("최신 순으로 상위 20개 기사를 표시합니다. 감성 필터를 사용해 원하는 감성의 기사만 볼 수 있습니다.")


# ═══════════════════════════════════════════
# 탭5: 요약 리포트
# ═══════════════════════════════════════════
with tab5:
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    today_str_en = datetime.datetime.now().strftime("%Y-%m-%d")

    top1_word = freq1.most_common(1)[0][0] if freq1 else "N/A"
    top2_word = freq2.most_common(1)[0][0] if freq2 else "N/A"

    # 어느 미디어가 더 극단적?
    if abs(avg1) > abs(avg2):
        more_extreme = M1
        more_extreme_dir = SENTIMENT_KO[lbl1]
    else:
        more_extreme = M2
        more_extreme_dir = SENTIMENT_KO[lbl2]

    summary_ko = f"""
📋 [분석 요약]
검색어: "{KEYWORD}" | 분석 일시: {today_str}

{M1}은(는) 총 {len(df1)}개의 기사를 수집했으며, 평균 감성 점수는 {avg1:+.3f}({SENTIMENT_KO[lbl1]})입니다.
{M2}은(는) 총 {len(df2)}개의 기사를 수집했으며, 평균 감성 점수는 {avg2:+.3f}({SENTIMENT_KO[lbl2]})입니다.

{M1}이(가) 가장 많이 사용한 단어는 '{top1_word}'이며,
{M2}은(는) '{top2_word}'를 특징적으로 사용했습니다.

전반적으로 {more_extreme}이(가) 이 주제를 더 {more_extreme_dir}으로 보도하는 경향이 있습니다.
두 미디어의 감성 점수 차이는 {sentiment_diff:.3f}입니다.
    """.strip()

    st.subheader("📋 분석 요약 (자동 생성)")
    st.markdown(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:1.2rem;">'
        f'<pre style="white-space:pre-wrap;font-family:Noto Sans KR,sans-serif;font-size:0.95rem;">'
        f'{summary_ko}</pre></div>',
        unsafe_allow_html=True,
    )

    # 영어 다운로드 리포트 생성
    top3_words1 = ", ".join([w for w, _ in freq1.most_common(3)])
    top3_words2 = ", ".join([w for w, _ in freq2.most_common(3)])

    report_en = f"""
MEDIA COMPARISON ANALYSIS REPORT
==================================
Keyword: "{KEYWORD}"
Analysis Date: {today_str_en}
Days Covered: Last {days_filter} days

--- {M1} ---
Articles Collected : {len(df1)}
Avg Sentiment Score: {avg1:+.4f} ({lbl1})
Sentiment Distribution:
  Positive : {cnt1['Positive']} ({round(cnt1['Positive']/max(len(df1),1)*100,1)}%)
  Negative : {cnt1['Negative']} ({round(cnt1['Negative']/max(len(df1),1)*100,1)}%)
  Neutral  : {cnt1['Neutral']}  ({round(cnt1['Neutral']/max(len(df1),1)*100,1)}%)
Top 3 Keywords: {top3_words1}

--- {M2} ---
Articles Collected : {len(df2)}
Avg Sentiment Score: {avg2:+.4f} ({lbl2})
Sentiment Distribution:
  Positive : {cnt2['Positive']} ({round(cnt2['Positive']/max(len(df2),1)*100,1)}%)
  Negative : {cnt2['Negative']} ({round(cnt2['Negative']/max(len(df2),1)*100,1)}%)
  Neutral  : {cnt2['Neutral']}  ({round(cnt2['Neutral']/max(len(df2),1)*100,1)}%)
Top 3 Keywords: {top3_words2}

--- COMPARISON ---
Sentiment Score Difference: {sentiment_diff:.4f}
Overall Tendency:
  {more_extreme} tends to report this topic more {lbl1 if more_extreme==M1 else lbl2}.

--- DATA SOURCE ---
Source: Google News RSS
Sentiment Analysis: TextBlob
Tool: Streamlit Media Comparison Dashboard
    """.strip()

    st.download_button(
        label="📥 리포트 .txt로 다운로드",
        data=report_en,
        file_name=f"media_report_{KEYWORD.replace(' ','_')}_{today_str_en}.txt",
        mime="text/plain",
    )

    # 비교 요약 테이블
    st.subheader("📊 비교 요약 테이블")

    compare_table = pd.DataFrame({
        "항목": ["수집 기사 수", "평균 감성 점수", "긍정 비율", "부정 비율",
                 "주요 단어 1위", "주요 단어 2위", "주요 단어 3위"],
        M1: [
            len(df1),
            f"{avg1:+.3f} ({SENTIMENT_KO[lbl1]})",
            f"{round(cnt1['Positive']/max(len(df1),1)*100,1)}%",
            f"{round(cnt1['Negative']/max(len(df1),1)*100,1)}%",
        ] + [w for w, _ in freq1.most_common(3)],
        M2: [
            len(df2),
            f"{avg2:+.3f} ({SENTIMENT_KO[lbl2]})",
            f"{round(cnt2['Positive']/max(len(df2),1)*100,1)}%",
            f"{round(cnt2['Negative']/max(len(df2),1)*100,1)}%",
        ] + [w for w, _ in freq2.most_common(3)],
    })

    st.dataframe(compare_table, use_container_width=True, hide_index=True)
    st.caption("두 미디어의 주요 지표를 한눈에 비교할 수 있는 요약 테이블입니다.")
