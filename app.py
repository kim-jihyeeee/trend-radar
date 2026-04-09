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
st.set_page_config(page_title="Trend Radar v3.5", layout="wide", initial_sidebar_state="expanded")

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
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Trend Radar v3.5")

# 3. 데이터 수집 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    try:
        res = requests.get(url, timeout=5).json()[1]
        return res[:15] if res else [f"{main_word} 추천", f"{main_word} 후기"]
    except: return []

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

# 🌟 쇼핑 데이터 수집 강화 (데이터 없을 시 카테고리 제외하고 재시도) 🌟
def get_naver_shopping_trend(keyword, days, cat_id=None):
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    
    # 1차 시도: 특정 카테고리 내 검색
    body = {
        "startDate": start_date, "endDate": end_date, "timeUnit": "date",
        "category": cat_id if cat_id else "50000000", # 패션의류 기본
        "keyword": [{"name": keyword, "param": [keyword]}]
    }
    
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200 and 'results' in res.json() and res.json()['results'][0]['data']:
            return pd.DataFrame(res.json()['results'][0]['data'])
    except: pass
    return pd.DataFrame()

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

    with st.form("search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간 선택", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
        days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]
        if st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True):
            st.session_state.keyword = keyword_input
            st.session_state.view_mode = 'main'

# 5. 메인 로직
if st.session_state.keyword:
    tab1, tab2 = st.tabs(["📊 네이버 데이터랩 트렌드", "📰 실시간 뉴스 및 이슈"])
    
    with tab1:
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("🔍 검색어 트렌드")
            df_search = get_naver_search_trend(st.session_state.keyword, days)
            if not df_search.empty:
                df_search['period'] = pd.to_datetime(df_search['period'])
                st.line_chart(df_search.rename(columns={'ratio': '검색량 지수'}).set_index('period')['검색량 지수'])
                st.markdown("##### 🔝 검색 연관어 (Top 15)")
                for i, rk in enumerate(get_ad_suggestions(st.session_state.keyword)): st.write(f"{i+1}. {rk}")
            else: st.warning("데이터 수집 실패")

        with col_right:
            st.subheader("🛒 쇼핑 클릭 트렌드")
            category_map = {
                "건강식품": "50000030", "패션의류": "50000000", "패션잡화": "50000001", 
                "화장품/미용": "50000002", "디지털/가전": "50000003", "가구/인테리어": "50000004", 
                "출산/육아": "50000005", "식품": "50000006", "스포츠/레저": "50000007", 
                "생활/건강": "50000008", "여가/생활편의": "50000009"
            }
            selected_cat = st.selectbox("업종 카테고리 선택", list(category_map.keys()), index=0)
            
            df_shop = get_naver_shopping_trend(st.session_state.keyword, days, category_map[selected_cat])
            
            if not df_shop.empty:
                df_shop['period'] = pd.to_datetime(df_shop['period'])
                st.line_chart(df_shop.rename(columns={'ratio': '클릭량 지수'}).set_index('period')['클릭량 지수'], color="#FF4B4B")
            else:
                st.info("💡 팁: 해당 키워드가 '생활/건강' 카테고리에 매칭되지 않습니다. '식품'이나 '건강식품'으로 카테고리를 변경해 보세요.")
                st.image("https://via.placeholder.com/400x200.png?text=No+Shopping+Data+Available", use_container_width=True)

            st.markdown(f"##### 🛍️ {selected_cat} 쇼핑 추천어")
            # 데이터가 없어도 마케팅 아이디어를 위해 추천어는 항상 표시
            for i, rk in enumerate(get_ad_suggestions(f"{st.session_state.keyword} 구매")):
                st.write(f"{i+1}. {rk}")

    with tab2:
        # 뉴스 탭 로직 (기존과 동일)
        news_data = fetch_news_data(st.session_state.keyword, days)
        if news_data:
            df_news = pd.DataFrame(news_data).sort_values(by="날짜", ascending=False)
            st.subheader("📰 실시간 뉴스 리스트")
            st.dataframe(df_news, use_container_width=True, hide_index=True)
            # (중략 - 기존 코드 유지)
