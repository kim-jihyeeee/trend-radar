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
st.set_page_config(page_title="Trend Radar v3.0", layout="wide", initial_sidebar_state="expanded")

# 🌟 여기에 네이버에서 발급받은 정보를 입력하세요 🌟
NAVER_CLIENT_ID = "여기에_ID_입력"
NAVER_CLIENT_SECRET = "여기에_SECRET_입력"

# 상태값 초기화
if 'keyword' not in st.session_state: st.session_state.keyword = ""

# 2. UI 디자인 (모바일 아이콘 오류 수정 포함)
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
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Trend Radar v3.0")
st.caption("Google News + Naver DataLab 통합 마케팅 분석 툴")

# 3. 네이버 데이터랩 API 함수
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
        return pd.DataFrame()
    except: return pd.DataFrame()

# 4. 사이드바 검색창
with st.sidebar:
    try:
        with open("profile.jpg", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/jpeg;base64,{b64}" style="width:120px;border-radius:50%"></div>', unsafe_allow_html=True)
    except: pass
    
    with st.form("search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
        days_dict = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}
        days = days_dict[days_option]
        submit_btn = st.form_submit_button("레이더 가동", use_container_width=True)
        if submit_btn: st.session_state.keyword = keyword_input

# 5. 메인 화면 로직
if st.session_state.keyword:
    tab1, tab2 = st.tabs(["📊 네이버 트렌드 분석", "📰 뉴스/이슈 수집"])
    
    with tab1:
        st.subheader(f"📈 '{st.session_state.keyword}' 네이버 검색 트렌드 ({days_option})")
        df_trend = get_naver_datalab(st.session_state.keyword, days)
        
        if not df_trend.empty:
            df_trend['period'] = pd.to_datetime(df_trend['period'])
            df_trend = df_trend.rename(columns={'ratio': '검색량 지수', 'period': '날짜'})
            # 차트 그리기
            st.line_chart(df_trend.set_index('날짜'))
            st.caption("※ 네이버 데이터랩 기준: 기간 내 최고 검색량을 100으로 설정한 상대적 수치입니다.")
            
            # 통계 요약
            avg_val = round(df_trend['검색량 지수'].mean(), 2)
            max_val = df_trend['검색량 지수'].max()
            col1, col2 = st.columns(2)
            col1.metric("평균 트렌드 지수", avg_val)
            col2.metric("최고 트렌드 지수", max_val)
        else:
            st.error("네이버 API 연결에 실패했습니다. Client ID/Secret을 확인해주세요.")

    with tab2:
        # 기존 뉴스 수집 로직 (간략화 버전)
        url = f"https://news.google.com/rss/search?q={st.session_state.keyword}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, verify=False)
        items = re.findall(r"<item>(.*?)</item>", res.text, re.DOTALL)
        news_list = []
        for item in items:
            t = re.search(r"<title>(.*?)</title>", item)
            l = re.search(r"<link>(.*?)</link>", item)
            if t and l:
                news_list.append({"제목": t.group(1).replace("<![CDATA[", "").replace("]]>", ""), "URL": l.group(1)})
        
        if news_list:
            st.dataframe(pd.DataFrame(news_list), use_container_width=True)
        else:
            st.warning("수집된 뉴스가 없습니다.")

else:
    st.info("👈 왼쪽 메뉴에서 분석할 키워드를 입력해 주세요!")
