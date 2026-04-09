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
st.set_page_config(page_title="Trend Radar v4.0", layout="wide", initial_sidebar_state="expanded")

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

st.title("🚀 Trend Radar v4.0")

# 3. 데이터 수집 및 분석 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    try:
        res = requests.get(url, timeout=5).json()[1]
        return res[:10] if res else [f"{main_word} 추천", f"{main_word} 효과"]
    except: return []

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
    g_url = f"https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(g_url, timeout=10, verify=False)
        items = re.findall(r"<item>(.*?)</item>", res.text, re.DOTALL)
        for item in items: 
            t_match = re.search(r"<title>(.*?)</title>", item)
            l_match = re.search(r"<link>(.*?)</link>", item)
            s_match = re.search(r"<source.*?>(.*?)</source>", item)
            pd_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
            if t_match and l_match:
                title = t_match.group(1).replace("<![CDATA[", "").replace("]]>", "")
                source = s_match.group(1) if s_match else "뉴스"
                platform = "구글 뉴스"
                if "nate.com" in l_match.group(1):
                    platform = "네이트 뉴스"
                    if " : " in title: source = title.split(" : ")[-1].strip()
                date_str = pd_match.group(1) if pd_match else ""
                try:
                    dt = parsedate_to_datetime(date_str)
                    date_str = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
                except: date_str = "알 수 없음"
                results.append({"플랫폼": platform, "출처": source, "제목": title.split(" - ")[0], "날짜": date_str, "URL": l_match.group(1)})
    except: pass
    return results

def get_realtime_daum():
    # 실제 Daum 뉴스 토픽 데이터를 파싱하는 시뮬레이션 (최대한 실제와 가깝게 추출)
    try:
        res = requests.get("https://news.daum.net/", timeout=5)
        keywords = re.findall(r'data-tiara-layer="article_main".*?>(.*?)</a>', res.text, re.DOTALL)
        # 중복 제거 및 클리닝
        unique_kws = list(dict.fromkeys([re.sub('<[^>]*>', '', k).strip() for k in keywords if len(k) < 20]))
        return unique_kws[:10] if unique_kws else ["실시간 데이터 로딩 실패"]
    except: return ["데이터 연동 오류"]

# 4. 사이드바
with st.sidebar:
    try:
        with open("profile.jpg", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center;margin-bottom:10px;"><img src="data:image/jpeg;base64,{b64}" style="width:120px;border-radius:50%"></div>', unsafe_allow_html=True)
            st.markdown('<p style="text-align:center;font-weight:bold;margin-bottom:20px;">🔥 Trend Radar</p>', unsafe_allow_html=True)
    except: pass

    # 🌟 엔터 키 동작을 위해 버튼 클릭 로직 수정 🌟
    keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword, placeholder="키워드 입력 후 엔터!")
    if keyword_input != st.session_state.keyword:
        st.session_state.keyword = keyword_input
        st.session_state.view_mode = 'main'
        st.rerun()

    if st.button("🚀 데이터 레이더 가동", use_container_width=True):
        st.session_state.keyword = keyword_input
        st.session_state.view_mode = 'main'

    st.divider()
    days_option = st.radio("📅 분석 기간 선택 (자동 반영)", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
    days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]

    st.divider()
    if st.button("✨ Daum 실시간 트렌드 확인", use_container_width=True):
        st.session_state.view_mode = 'daum'

# 5. 메
