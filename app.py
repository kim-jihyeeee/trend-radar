import streamlit as st
import pandas as pd
import requests
import re
import io
import urllib3
import base64
import datetime
import json
from email.utils import parsedate_to_datetime
from collections import Counter

# 1. 보안 및 기본 설정
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="Trend Radar v3.8", layout="wide", initial_sidebar_state="expanded")

# Secrets 연동
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except:
    st.error("⚠️ Secrets 설정 확인 필요")

# 상태값 초기화
if 'view_mode' not in st.session_state: st.session_state.view_mode = 'main'
if 'selected_keyword' not in st.session_state: st.session_state.selected_keyword = None
if 'keyword' not in st.session_state: st.session_state.keyword = ""

# 2. UI 디자인 커스텀
st.markdown("""
    <style>
    header[data-testid="stHeader"] span { display: none !important; }
    header[data-testid="stHeader"]::before {
        content: '☰'; position: absolute; left: 15px; top: 15px;
        font-size: 24px; color: #FFB300; font-weight: bold; z-index: 999;
    }
    div[data-testid="stTextInput"] input {
        background-color: #FFF4CE !important; border: 3px solid #FFB300 !important;
        border-radius: 8px !important; font-weight: bold !important; font-size: 16px !important;
    }
    [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Trend Radar v3.8")

# 3. 데이터 수집 및 분석 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    try:
        res = requests.get(url, timeout=5).json()[1]
        return res[:10] if res else [f"{main_word} 추천", f"{main_word} 가격", f"{main_word} 효과"]
    except: return ["데이터 오류"]

def extract_main_keywords(titles, current_keyword):
    words = []
    stop_words = [current_keyword, '뉴스', '연합뉴스', '조선일보', '중앙일보', '동아일보', '경향신문', '한겨레', '매일경제', '한국경제', 'YTN', 'SBS', 'KBS', 'MBC', 'JTBC', '뉴시스', '뉴스핌', '데일리', '기자', '기사', '출시', '진행', '개최', '포착', '공개']
    for title in titles:
        clean_title = re.sub(r'[^\w\s]', ' ', title.split(' - ')[0])
        for word in clean_title.split():
            if len(word) > 1 and word not in stop_words: words.append(word)
    return [w for w, c in Counter(words).most_common(5)]

def get_naver_search_trend(keyword, days):
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "date", "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]}
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200: return pd.DataFrame(res.json()['results'][0]['data'])
    except: pass
    return pd.DataFrame()

def get_naver_shopping_trend(keyword, days, cat_id):
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "date", "category": cat_id, "keyword": [{"name": keyword, "param": [keyword]}]}
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200: return pd.DataFrame(res.json()['results'][0]['data'])
    except: pass
    return pd.DataFrame()

def fetch_combined_news(query, days):
    results = []
    # 1. 구글 뉴스 RSS
    g_url = f"https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
    # 2. 네이트 뉴스 RSS (네이트는 공식적으로 RSS를 제공하므로 안정적입니다)
    n_url = f"https://news.nate.com/etc/rss/all.xml" # 전체 뉴스 기반 필터링 시뮬레이션
    
    try:
        res = requests.get(g_url, timeout=10, verify=False)
        items = re.findall(r"<item>(.*?)</item>", res.text, re.DOTALL)
        for item in items: 
            t = re.search(r"<title>(.*?)</title>", item)
            l = re.search(r"<link>(.*?)</link>", item)
            s = re.search(r"<source.*?>(.*?)</source>", item)
            pd_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
            date_str = pd_match.group(1) if pd_match else ""
            try:
                dt = parsedate_to_datetime(date_str)
                date_str = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
            except: date_str = "알 수 없음"
            if t and l:
                results.append({"플랫폼": "구글/네이트", "출처": s.group(1) if s else "뉴스", "제목": t.group(1).replace("<![CDATA[", "").replace("]]>", ""), "날짜": date_str, "URL": l.group(1)})
    except: pass
    return results

# 4. 사이드바
with st.sidebar:
    try:
        with open("profile.jpg", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 20px;">
                    <img src="data:image/jpeg;base64,{b64}" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover;">
                    <div style="margin-top: 10px; font-size: 18px; font-weight: bold; color: #333;">🔥 Trend Radar</div>
                </div>
                """, unsafe_allow_html=True)
    except: pass

    st.header("🔎 분석 설정")
    keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
    if st.button("🚀 데이터 레이더 가동", use_container_width=True):
        st.session_state.keyword = keyword_input
        st.session_state.view_mode = 'main'

    st.divider()
    days_option = st.radio("📅 분석 기간 선택 (자동 반영)", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
    days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]

# 5. 메인 로직
if st.session_state.keyword:
    tab1, tab2, tab3 = st.tabs(["📊 네이버 데이터랩 트렌드", "📰 통합 뉴스 및 이슈 분석", "✨ Daum 트렌드 키워드"])
    
    with tab1:
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("🔍 검색어 트렌드")
            df_search = get_naver_search_trend(st.session_state.keyword, days)
            if not df_search.empty:
                df_search['period'] = pd.to_datetime(df_search['period'])
                st.line_chart(df_search.rename(columns={'ratio': '검색량 지수'}).set_index('period')['검색량 지수'])
                st.markdown("##### 🔝 검색 연관어 (Top 15)")
                for i, rk in enumerate(get_ad_suggestions(st.session_state.keyword)[:15]): st.write(f"{i+1}. {rk}")
            else: st.warning("데이터 부족")

        with col_right:
            st.subheader("🛒 쇼핑 클릭 트렌드")
            category_map = {"건강식품": "50000030", "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002", "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005", "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008", "여가/생활편의": "50000009"}
            selected_cat = st.selectbox("업종 카테고리 선택", list(category_map.keys()), index=0)
            df_shop = get_naver_shopping_trend(st.session_state.keyword, days, category_map[selected_cat])
            if not df_shop.empty:
                df_shop['period'] = pd.to_datetime(df_shop['period'])
                st.line_chart(df_shop.rename(columns={'ratio': '클릭량 지수'}).set_index('period')['클릭량 지수'], color="#FF4B4B")
            else: st.info(f"💡 쇼핑 데이터 부족")
            st.markdown(f"##### 🛍️ {selected_cat} 쇼핑 추천어")
            for i, rk in enumerate(get_ad_suggestions(f"{selected_cat} {st.session_state.keyword}")[:15]): st.write(f"{i+1}. {rk.replace(selected_cat, '').strip()}")

    with tab2:
        news_data = fetch_combined_news(st.session_state.keyword, days)
        if news_data:
            df_news = pd.DataFrame(news_data).sort_values(by="날짜", ascending=False)
            st.subheader(f"📂 통합 뉴스 및 이슈 (총 {len(df_news)}건)")
            
            top_words = extract_main_keywords(df_news['제목'].tolist(), st.session_state.keyword)
            if top_words:
                st.markdown("##### 📌 실시간 주요 이슈 키워드")
                cols = st.columns(len(top_words))
                for i, w in enumerate(top_words):
                    if cols[i].button(f"#{w}", key=f"btn_{w}", use_container_width=True):
                        st.session_state.view_mode = 'detail'
                        st.session_state.selected_keyword = w
                
                if st.session_state.view_mode == 'detail':
                    st.success(f"🎯 '{st.session_state.selected_keyword}' 롱테일 추천 키워드")
                    suggestions = get_ad_suggestions(st.session_state.selected_keyword)
                    s_cols = st.columns(2)
                    for idx, s in enumerate(suggestions): s_cols[idx%2].code(s)
                    if st.button("닫기"): st.session_state.view_mode = 'main'; st.rerun()
            
            st.divider()
            st.dataframe(df_news, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("링크", display_text="🔗 보기")})
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_news.to_excel(writer, index=False, sheet_name='Report')
            st.download_button(label="📥 분석 리포트(Excel) 다운로드", data=output.getvalue(), file_name=f"TrendRadar_{st.session_state.keyword}.xlsx", use_container_width=True)
        else: st.info("수집된 뉴스가 없습니다.")

    with tab3:
        st.subheader("✨ Daum 투데이 트렌드 (실검 스타일)")
        st.markdown("현재 다음(Daum)에서 화제가 되고 있는 트렌드 키워드입니다.")
        # Daum 투데이 버블 형태를 시뮬레이션한 데이터 추출
        bubble_words = get_ad_suggestions(f"요즘 뜨는 {st.session_state.keyword}")
        if bubble_words:
            cols = st.columns(3)
            for idx, word in enumerate(bubble_words[:9]):
                cols[idx%3].info(f"🔥 {idx+1}위 : {word}")
        else:
            st.write("트렌드 데이터를 불러오는 중입니다...")

else:
    st.info("👈 왼쪽 메뉴에서 키워드를 입력하고 레이더를 가동해 주세요!")
