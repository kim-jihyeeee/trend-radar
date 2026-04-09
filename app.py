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
st.set_page_config(page_title="Trend Radar v3.2", layout="wide", initial_sidebar_state="expanded")

# Secrets 연동
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except:
    st.error("⚠️ Secrets 설정 확인 필요 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)")

# 상태값 초기화
if 'view_mode' not in st.session_state: st.session_state.view_mode = 'main'
if 'selected_keyword' not in st.session_state: st.session_state.selected_keyword = None
if 'keyword' not in st.session_state: st.session_state.keyword = ""

# 2. UI 디자인
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
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #eee; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Trend Radar v3.2")

# 3. 데이터 수집 함수들
@st.cache_data(ttl=3600)
def get_naver_search_trend(keyword, days):
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    body = {
        "startDate": start_date, "endDate": end_date, "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200: return pd.DataFrame(res.json()['results'][0]['data'])
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_naver_shopping_trend(keyword, days):
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    # 식품(50000006) -> 건강식품(50000030) 카테고리 기준 예시
    body = {
        "startDate": start_date, "endDate": end_date, "timeUnit": "date",
        "category": "50000030", 
        "keyword": [{"name": keyword, "param": [keyword]}]
    }
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200: return pd.DataFrame(res.json()['results'][0]['data'])
    except: pass
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def get_related_keywords(word, count=15):
    # 구글 제안어 API 활용 (네이버 연관검색어는 API 비공개이므로 대체)
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={word}"
    try:
        res = requests.get(url, timeout=5).json()[1]
        return res[:count] if res else [f"{word} 추천", f"{word} 효과", f"{word} 가격"]
    except: return []

def fetch_news_data(query, days):
    results = []
    url = f"https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=15, verify=False)
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
                results.append({"플랫폼": "구글 뉴스", "출처": s.group(1) if s else "뉴스", "제목": t.group(1).replace("<![CDATA[", "").replace("]]>", ""), "날짜": date_str, "URL": l.group(1)})
    except: pass
    return results

# 4. 사이드바 (프로필 로고 복구)
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
    except: 
        st.markdown('<div style="text-align:center; font-weight:bold; margin-bottom:20px;">🔥 Trend Radar</div>', unsafe_allow_html=True)

    with st.form("search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간 선택", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
        days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]
        if st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True):
            st.session_state.keyword = keyword_input
            st.session_state.view_mode = 'main'

# 5. 메인 화면 로직
if st.session_state.keyword:
    tab1, tab2 = st.tabs(["📊 네이버 데이터랩 트렌드", "📰 실시간 뉴스 및 이슈"])
    
    with tab1:
        # 화면을 왼쪽(검색) / 오른쪽(쇼핑)으로 분할
        col_left, col_right = st.columns(2)
        
        # --- [왼쪽] 데이터랩 검색어 트렌드 ---
        with col_left:
            st.subheader("🔍 검색어 트렌드")
            df_search = get_naver_search_trend(st.session_state.keyword, days)
            if not df_search.empty:
                df_search['period'] = pd.to_datetime(df_search['period'])
                st.line_chart(df_search.rename(columns={'ratio': '검색량 지수'}).set_index('period')['검색량 지수'])
                
                st.markdown("##### 🔝 검색 연관 키워드 (Top 15)")
                related_search = get_related_keywords(st.session_state.keyword, 15)
                for i, rk in enumerate(related_search):
                    st.write(f"{i+1}. {rk}")
            else: st.warning("검색 데이터를 불러오지 못했습니다.")

        # --- [오른쪽] 데이터랩 쇼핑 인사이트 ---
        with col_right:
            st.subheader("🛒 쇼핑 클릭 트렌드")
            df_shop = get_naver_shopping_trend(st.session_state.keyword, days)
            if not df_shop.empty:
                df_shop['period'] = pd.to_datetime(df_shop['period'])
                st.line_chart(df_shop.rename(columns={'ratio': '클릭량 지수'}).set_index('period')['클릭량 지수'], color="#FF4B4B")
                
                st.markdown("##### 🛍️ 쇼핑 연관 키워드 (Top 15)")
                # 쇼핑 특화 연관 키워드 (검색어와 비슷하지만 쇼핑 의도 강조)
                related_shop = get_related_keywords(f"쇼핑 {st.session_state.keyword}", 15)
                for i, rk in enumerate(related_shop):
                    st.write(f"{i+1}. {rk.replace('쇼핑 ', '')}")
            else: st.info("쇼핑 데이터를 불러오지 못했습니다. (카테고리 매칭 필요)")

    with tab2:
        news_data = fetch_news_data(st.session_state.keyword, days)
        if news_data:
            df_news = pd.DataFrame(news_data).sort_values(by="날짜", ascending=False)
            st.subheader(f"📰 '{st.session_state.keyword}' 뉴스 리스트")
            st.dataframe(df_news, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("링크", display_text="🔗 보기")})
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_news.to_excel(writer, index=False, sheet_name='Report')
            st.download_button(label="📥 분석 리포트(Excel) 다운로드", data=output.getvalue(), file_name=f"TrendRadar_{st.session_state.keyword}.xlsx", use_container_width=True)
        else: st.info("수집된 뉴스가 없습니다.")
else: st.info("👈 왼쪽 메뉴에서 키워드를 입력해 주세요!")
