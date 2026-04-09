import streamlit as st
import pandas as pd
import requests
import re
import io
import urllib3
import base64
import datetime
from email.utils import parsedate_to_datetime
from collections import Counter

# 1. 보안 설정
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. 페이지 기본 설정
st.set_page_config(
    page_title="Trend Radar v2.0", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 화면 전환을 위한 상태값 초기화
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'main'
if 'selected_keyword' not in st.session_state:
    st.session_state.selected_keyword = None
if 'keyword' not in st.session_state:
    st.session_state.keyword = ""

st.title("🔥 Trend Radar: 통합 이슈 & 뉴스 분석")
st.markdown("마케팅 AE를 위한 실시간 트렌드 수집 및 실전 롱테일 키워드 제안 도구입니다.")

# 3. 사이드바 검색 및 기간 설정
with st.sidebar:
    try:
        image_path = "profile.jpg" 
        with open(image_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            st.markdown(
                f"""
                <div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 25px; margin-top: 10px;">
                    <div style="width: 140px; height: 140px; border-radius: 50%; overflow: hidden; box-shadow: 0px 4px 15px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center;">
                        <img src="data:image/jpeg;base64,{b64}" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    <div style="margin-top: 15px; font-size: 24px; font-weight: bold; color: #31333F;">🔥Trend Radar</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except FileNotFoundError:
        st.warning("⚠️ 'profile.jpg' 파일을 찾을 수 없습니다.")

    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] + div, button[kind="header"] { display: none !important; }
        div[data-testid="stTextInput"] input {
            background-color: #FFF4CE !important;
            border: 3px solid #FFB300 !important;
            border-radius: 8px !important;
            font-weight: bold !important;
            color: #333333 !important;
            font-size: 16px !important;
        }
        div[data-testid="stTextInput"] input:focus { outline: none !important; border: 3px solid #FF8F00 !important; }
        </style>
    """, unsafe_allow_html=True)

    with st.form(key="search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간 선택", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1, label_visibility="collapsed")
        days_dict = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}
        days = days_dict[days_option]
        st.divider()
        submit_btn = st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True)
        if submit_btn:
            if keyword_input.strip() == "":
                st.error("⚠️ 키워드를 입력해 주세요.")
            else:
                st.session_state.view_mode = 'main'
                st.session_state.keyword = keyword_input

# 4. 기능 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        suggestions = response.json()[1] 
        result = [kw for kw in suggestions if kw != main_word][:10]
        return result if result else [f"{main_word} 추천", f"{main_word} 후기", f"{main_word} 가격"]
    except: return ["데이터 오류 발생"]

def extract_main_keywords(titles, current_keyword):
    words = []
    stop_words = [current_keyword, '뉴스', 'com', 'daum', 'naver', '연합뉴스', '뉴스1', '조선일보', '중앙일보', '동아일보', '경향신문', '한겨레', '매일경제', '한국경제', 'YTN', 'SBS', 'KBS', 'MBC', 'JTBC', '뉴시스', '뉴스핌', '데일리', '기자', '기사']
    for title in titles:
