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
st.set_page_config(page_title="Trend Radar v3.1", layout="wide", initial_sidebar_state="expanded")

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

st.title("🚀 Trend Radar v3.1")

# 3. 함수 정의
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    try:
        response = requests.get(url, timeout=5)
        suggestions = response.json()[1] 
        return suggestions[:10] if suggestions else [f"{main_word} 후기", f"{main_word} 가격"]
    except: return ["데이터 오류"]

def extract_main_keywords(titles, current_keyword):
    words = []
    stop_words = [current_keyword, '뉴스', '연합뉴스', '조선일보', '중앙일보', '동아일보', '경향신문', '한겨레', '매일경제', '한국경제', 'YTN', 'SBS', 'KBS', 'MBC', 'JTBC', '뉴시스', '뉴스핌', '데일리', '기자', '기사', '출시', '개최', '진행']
    for title in titles:
        clean_title = re.sub(r'[^\w\s]', ' ', title.split(' - ')[0])
        for word in clean_title.split():
            if len(word) > 1 and word not in stop_words: words.append(word)
    return [w for w, c in Counter(words).most_common(5)]

def get_naver_datalab(keyword, days):
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
            st.markdown(f'<div style="text-align:center"><img src="data:image/jpeg;base64,{b64}" style="width:120px;border-radius:50%"></div>', unsafe_allow_html=True)
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
    tab1, tab2 = st.tabs(["📊 네이버 트렌드", "📰 실시간 뉴스 및 키워드"])
    
    with tab1:
        st.subheader(f"📈 '{st.session_state.keyword}' 검색량 추이")
        df_trend = get_naver_datalab(st.session_state.keyword, days)
        if not df_trend.empty:
            df_trend['period'] = pd.to_datetime(df_trend['period'])
            df_trend = df_trend.rename(columns={'ratio': '지수', 'period': '날짜'})
            st.line_chart(df_trend.set_index('날짜'))
            
            # 정보 보강: 통계표 추가
            st.markdown("#### 📋 기간 내 트렌드 요약")
            col1, col2, col3 = st.columns(3)
            col1.metric("평균 지수", round(df_trend['지수'].mean(), 1))
            col2.metric("최고 지수", df_trend['지수'].max())
            col3.metric("최저 지수", df_trend['지수'].min())
        else: st.warning("네이버 데이터를 불러올 수 없습니다.")

    with tab2:
        news_data = fetch_news_data(st.session_state.keyword, days)
        if news_data:
            df_news = pd.DataFrame(news_data).sort_values(by="날짜", ascending=False)
            
            # --- 이슈 키워드 추출 & 롱테일 섹션 (부활!) ---
            top_words = extract_main_keywords(df_news['제목'].tolist(), st.session_state.keyword)
            if top_words:
                st.subheader("📌 뉴스 속 이슈 키워드 (클릭시 롱테일 확장)")
                cols = st.columns(len(top_words))
                for i, w in enumerate(top_words):
                    if cols[i].button(f"#{w}", key=f"btn_{w}", use_container_width=True):
                        st.session_state.view_mode = 'detail'
                        st.session_state.selected_keyword = w
                
                if st.session_state.view_mode == 'detail':
                    st.info(f"💡 '{st.session_state.selected_keyword}' 관련 추천 롱테일 키워드")
                    suggestions = get_ad_suggestions(st.session_state.selected_keyword)
                    s_cols = st.columns(2)
                    for idx, s in enumerate(suggestions): s_cols[idx%2].code(s)
                    if st.button("닫기"): st.session_state.view_mode = 'main'; st.rerun()
            
            st.divider()
            st.subheader("📰 실시간 뉴스 리스트")
            st.dataframe(df_news, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("링크", display_text="🔗 보기")})
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_news.to_excel(writer, index=False, sheet_name='Report')
            st.download_button(label="📥 분석 리포트(Excel) 다운로드", data=output.getvalue(), file_name=f"TrendRadar_{st.session_state.keyword}.xlsx", use_container_width=True)
        else: st.info("수집된 뉴스가 없습니다.")
else: st.info("👈 왼쪽 메뉴에서 키워드를 입력해 주세요!")
