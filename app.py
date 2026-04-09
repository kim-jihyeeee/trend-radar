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
st.set_page_config(page_title="Trend Radar v4.7", layout="wide", initial_sidebar_state="expanded")

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

st.title("🚀 Trend Radar v4.7")

# 3. 트렌드 분석 핵심 함수 (단순 조합이 아닌 실제 데이터 분석)
@st.cache_data(show_spinner=False)
def get_real_trend_keywords(query, days, mode="general"):
    # 1. 실제 구글/네이버 연관 검색 제안어 수집
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={query}"
    try:
        suggestions = requests.get(url, timeout=5).json()[1]
    except:
        suggestions = []

    # 2. 실시간 뉴스에서 급상승 키워드 추출 (Context Analysis)
    news_url = f"https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
    news_keywords = []
    try:
        res = requests.get(news_url, timeout=5, verify=False)
        titles = re.findall(r"<title>(.*?)</title>", res.text)
        # 뉴스 제목에서 명사 위주 추출 (간이 형태소 분석)
        for t in titles:
            clean = re.sub(r'[^\w\s]', ' ', t)
            for word in clean.split():
                if len(word) > 1 and word not in query:
                    news_keywords.append(word)
    except:
        pass
    
    # 뉴스에서 자주 나오는 단어 상위 10개
    top_news_kws = [w for w, c in Counter(news_keywords).most_common(10)]
    
    # 3. 최종 리스트 믹스 (실제 제안어 + 뉴스 트렌드 단어)
    final_list = list(dict.fromkeys(suggestions + top_news_kws))
    
    # 만약 데이터가 너무 적을 경우에만 마케팅 수식어 보정
    if len(final_list) < 5:
        final_list += [f"{query} 추천", f"{query} 후기", f"{query} 효과"]
        
    return final_list[:15]

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

# 4. 사이드바
with st.sidebar:
    try:
        with open("profile.jpg", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center;margin-bottom:10px;"><img src="data:image/jpeg;base64,{b64}" style="width:120px;border-radius:50%"></div>', unsafe_allow_html=True)
            st.markdown('<p style="text-align:center;font-weight:bold;margin-bottom:20px;">🔥 Trend Radar</p>', unsafe_allow_html=True)
    except: pass

    with st.form("search_input_form"):
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        if st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True):
            st.session_state.keyword = keyword_input
            st.session_state.view_mode = 'main'
            st.rerun()

    st.divider()
    days_option = st.radio("📅 분석 기간 선택 (자동 반영)", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
    days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]

# 5. 메인 로직
if st.session_state.keyword:
    tab1, tab2 = st.tabs(["📊 네이버 데이터 트렌드", "📰 통합 뉴스 및 이슈 분석"])
    
    with tab1:
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("🔍 검색어 트렌드 (네이버 Datalab)")
            df_s = get_naver_search_trend(st.session_state.keyword, days)
            if not df_s.empty:
                df_s['period'] = pd.to_datetime(df_s['period'])
                st.line_chart(df_s.set_index('period')['ratio'])
                
                # 🌟 트렌드 반영 연관어 리스트 🌟
                st.markdown("##### ✨ 실시간 트렌드 연관어 (Top 15)")
                trend_kws = get_real_trend_keywords(st.session_state.keyword, days)
                for tk in trend_kws: st.write(f"- {tk}")
            else: st.warning("데이터 부족")

        with col_r:
            st.subheader("🛒 쇼핑 클릭 트렌드")
            cmap = {"건강식품": "50000030", "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002", "디지털/가전": "50000003", "식품": "50000006", "생활/건강": "50000008"}
            scat = st.selectbox("업종 선택", list(cmap.keys()))
            df_p = get_naver_shopping_trend(st.session_state.keyword, days, cmap[scat])
            if not df_p.empty:
                df_p['period'] = pd.to_datetime(df_p['period'])
                st.line_chart(df_p.set_index('period')['ratio'], color="#FF4B4B")
                
                # 🌟 쇼핑 뉴스/트렌드 믹스 키워드 🌟
                st.markdown("##### 🛍️ 쇼핑/이슈 융합 키워드")
                shop_trend_kws = get_real_trend_keywords(f"쇼핑 {st.session_state.keyword}", days)
                for sk in shop_trend_kws: st.write(f"- {sk.replace('쇼핑 ', '').strip()}")
            else: st.info("쇼핑 데이터 부족")
else:
    st.info("👈 왼쪽 메뉴에서 키워드를 입력하고 레이더를 가동해 주세요!")
