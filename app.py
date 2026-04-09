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
st.set_page_config(
    page_title="Trend Radar v3.0", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 🌟 Secrets 기능으로 보안 강화: 금고에서 열쇠를 꺼내옵니다 🌟
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except:
    st.error("⚠️ Streamlit Cloud의 Secrets 설정이 필요합니다. NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 확인해주세요.")

# 상태값 초기화
if 'view_mode' not in st.session_state: st.session_state.view_mode = 'main'
if 'selected_keyword' not in st.session_state: st.session_state.selected_keyword = None
if 'keyword' not in st.session_state: st.session_state.keyword = ""

# 2. UI 디자인 커스텀 (모바일/PC 통합 최적화)
st.markdown("""
    <style>
    /* 아이콘 텍스트 오류 강제 수정 및 삼선 메뉴 삽입 */
    header[data-testid="stHeader"] span { display: none !important; }
    header[data-testid="stHeader"]::before {
        content: '☰'; position: absolute; left: 15px; top: 15px;
        font-size: 24px; color: #FFB300; font-weight: bold; z-index: 999;
    }
    /* 텍스트 입력창 디자인 */
    div[data-testid="stTextInput"] input {
        background-color: #FFF4CE !important;
        border: 3px solid #FFB300 !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        color: #333333 !important;
        font-size: 16px !important;
    }
    /* 사이드바 내부 불필요 요소 제거 */
    [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Trend Radar v3.0")
st.caption("Google News + Naver DataLab 통합 마케팅 분석 툴")

# 3. 데이터 수집 함수 (네이버 & 구글 뉴스)
def get_naver_datalab(keyword, days):
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    
    body = {
        "startDate": start_date, "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            data = res.json()['results'][0]['data']
            return pd.DataFrame(data)
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
            date_str = "알 수 없음"
            if pd_match:
                try:
                    dt = parsedate_to_datetime(pd_match.group(1))
                    date_str = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
                except: pass
            if t and l:
                results.append({
                    "플랫폼": "구글 뉴스", "출처": s.group(1) if s else "뉴스",
                    "제목": t.group(1).replace("<![CDATA[", "").replace("]]>", ""),
                    "날짜": date_str, "URL": l.group(1)
                })
    except: pass
    return results

# 4. 사이드바 검색창
with st.sidebar:
    try:
        image_path = "profile.jpg" 
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 25px;">
                    <div style="width: 120px; height: 120px; border-radius: 50%; overflow: hidden; box-shadow: 0px 4px 15px rgba(0,0,0,0.1); display: flex; align-items: center; justify-content: center;">
                        <img src="data:image/jpeg;base64,{b64}" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    <div style="margin-top: 15px; font-size: 20px; font-weight: bold; color: #31333F;">🔥Trend Radar</div>
                </div>
                """, unsafe_allow_html=True)
    except: pass

    with st.form(key="search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간 선택", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
        days_dict = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}
        days = days_dict[days_option]
        st.divider()
        submit_btn = st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True)
        if submit_btn:
            if keyword_input.strip() == "": st.error("⚠️ 키워드를 입력해 주세요.")
            else:
                st.session_state.keyword = keyword_input
                st.session_state.view_mode = 'main'

# 5. 화면 렌더링 로직
if st.session_state.keyword:
    tab1, tab2 = st.tabs(["📊 네이버 트렌드 지수", "📰 실시간 뉴스 및 이슈"])
    
    # --- Tab 1: 네이버 데이터랩 ---
    with tab1:
        st.subheader(f"📈 '{st.session_state.keyword}' 검색량 추이")
        df_trend = get_naver_datalab(st.session_state.keyword, days)
        if not df_trend.empty:
            df_trend['period'] = pd.to_datetime(df_trend['period'])
            df_trend = df_trend.rename(columns={'ratio': '트렌드 지수', 'period': '날짜'})
            st.line_chart(df_trend.set_index('날짜'))
            
            c1, c2 = st.columns(2)
            c1.metric("평균 지수", round(df_trend['트렌드 지수'].mean(), 1))
            c2.metric("최고 지수", df_trend['트렌드 지수'].max())
        else:
            st.warning("네이버 트렌드 데이터를 불러올 수 없습니다. Secrets 설정을 확인해 주세요.")

    # --- Tab 2: 구글 뉴스 ---
    with tab2:
        st.subheader(f"📂
