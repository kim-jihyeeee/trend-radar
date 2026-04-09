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
st.set_page_config(page_title="Trend Radar v4.3", layout="wide", initial_sidebar_state="expanded")

# Secrets 연동
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except:
    st.error("⚠️ Streamlit Cloud의 Secrets 설정에서 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 확인해주세요.")

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

st.title("🚀 Trend Radar v4.3")

# 3. 데이터 수집 및 분석 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    try:
        res = requests.get(url, timeout=5).json()[1]
        return res[:10] if res else [f"{main_word} 추천", f"{main_word} 가격"]
    except:
        return []

def extract_main_keywords(titles, current_keyword):
    words = []
    stop_words = [current_keyword, '뉴스', '연합뉴스', '조선일보', '중앙일보', '동아일보', '경향신문', '한겨레', '매일경제', '한국경제', 'YTN', 'SBS', 'KBS', 'MBC', 'JTBC', '뉴시스', '뉴스핌', '데일리', '기자', '기사', '출시', '진행', '개최']
    for title in titles:
        clean_title = re.sub(r'[^\w\s]', ' ', title.split(' - ')[0])
        for word in clean_title.split():
            if len(word) > 1 and word not in stop_words:
                words.append(word)
    return [w for w, c in Counter(words).most_common(5)]

def get_naver_search_trend(keyword, days):
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "date", "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]}
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return pd.DataFrame(res.json()['results'][0]['data'])
    except:
        pass
    return pd.DataFrame()

def get_naver_shopping_trend(keyword, days, cat_id):
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "date", "category": cat_id, "keyword": [{"name": keyword, "param": [keyword]}]}
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET, "Content-Type": "application/json"}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return pd.DataFrame(res.json()['results'][0]['data'])
    except:
        pass
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
                except:
                    date_str = "알 수 없음"
                results.append({"플랫폼": platform, "출처": source, "제목": title.split(" - ")[0], "날짜": date_str, "URL": l_match.group(1)})
    except:
        pass
    return results

def get_realtime_daum():
    try:
        res = requests.get("https://news.daum.net/", timeout=5)
        keywords = re.findall(r'data-tiara-layer="article_main".*?>(.*?)</a>', res.text, re.DOTALL)
        unique_kws = list(dict.fromkeys([re.sub('<[^>]*>', '', k).strip() for k in keywords if 2 <= len(k) < 20]))
        return unique_kws[:10] if unique_kws else ["실시간 데이터 로딩 실패"]
    except:
        return ["데이터 연동 오류"]

# 4. 사이드바
with st.sidebar:
    try:
        with open("profile.jpg", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center;margin-bottom:10px;"><img src="data:image/jpeg;base64,{b64}" style="width:120px;border-radius:50%"></div>', unsafe_allow_html=True)
            st.markdown('<p style="text-align:center;font-weight:bold;margin-bottom:20px;">🔥 Trend Radar</p>', unsafe_allow_html=True)
    except:
        pass

    with st.form("search_input_form"):
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        submit_search = st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True)
        if submit_search:
            st.session_state.keyword = keyword_input
            st.session_state.view_mode = 'main'
            st.rerun()

    st.divider()
    days_option = st.radio("📅 분석 기간 선택 (자동 반영)", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
    days = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}[days_option]

    st.divider()
    if st.button("✨ Daum 실시간 트렌드 확인", use_container_width=True):
        st.session_state.view_mode = 'daum'
        st.rerun()

# 5. 메인 로직
if st.session_state.keyword or st.session_state.view_mode == 'daum':
    if st.session_state.view_mode == 'daum':
        st.subheader("✨ Daum 실시간 트렌드 (실제 데이터)")
        daum_trends = get_realtime_daum()
        cols = st.columns(2)
        for idx, kw in enumerate(daum_trends):
            if cols[idx%2].button(f"🔥 {idx+1}위: {kw}", key=f"d_{idx}", use_container_width=True):
                st.session_state.keyword = kw
                st.session_state.view_mode = 'main'
                st.rerun()
        if st.button("⬅️ 메인 화면으로"):
            st.session_state.view_mode = 'main'; st.rerun()
    else:
        t1, t2 = st.tabs(["📊 네이버 데이터 트렌드", "📰 통합 뉴스 및 이슈 분석"])
        
        with t1:
            cl, cr = st.columns(2)
            with cl:
                st.subheader("🔍 검색어 트렌드")
                df_s = get_naver_search_trend(st.session_state.keyword, days)
                if not df_s.empty:
                    df_s['period'] = pd.to_datetime(df_s['period'])
                    st.line_chart(df_s.set_index('period')['ratio'])
                    st.markdown("##### 🔝 검색 연관어 (Top 15)")
                    for rk in get_ad_suggestions(st.session_state.keyword): st.write(f"- {rk}")
                else:
                    st.warning("검색 데이터를 찾을 수 없습니다.")

            with cr:
                st.subheader("🛒 쇼핑 클릭 트렌드")
                cmap = {"건강식품": "50000030", "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002", "디지털/가전": "50000003", "식품": "50000006", "생활/건강": "50000008"}
                scat = st.selectbox("업종 선택", list(cmap.keys()))
                df_p = get_naver_shopping_trend(st.session_state.keyword, days, cmap[scat])
                if not df_p.empty:
                    df_p['period'] = pd.to_datetime(df_p['period'])
                    st.line_chart(df_p.set_index('period')['ratio'], color="#FF4B4B")
                else:
                    st.info("쇼핑 클릭 데이터가 부족합니다.")

        with t2:
            news_data = fetch_combined_news(st.session_state.keyword, days)
            if news_data:
                df_n = pd.DataFrame(news_data).sort_values(by="날짜", ascending=False)
                st.subheader(f"📂 통합 뉴스 및 이슈 (총 {len(df_n)}건 수집)")
                
                tw = extract_main_keywords(df_n['제목'].tolist(), st.session_state.keyword)
                if tw:
                    st.markdown("##### 📌 실시간 주요 이슈 키워드")
                    hcols = st.columns(len(tw))
                    for i, w in enumerate(tw):
                        if hcols[i].button(f"#{w}", key=f"h_{i}", use_container_width=True):
                            st.session_state.view_mode = 'detail'
                            st.session_state.selected_keyword = w
                    
                    if st.session_state.view_mode == 'detail':
                        st.success(f"🎯 '{st.session_state.selected_keyword}' 롱테일 추천")
                        sug = get_ad_suggestions(st.session_state.selected_keyword)
                        sc1, sc2 = st.columns(2)
                        for idx, s in enumerate(sug):
                            if idx % 2 == 0: sc1.code(s)
                            else: sc2.code(s)
                        if st.button("닫기"):
                            st.session_state.view_mode = 'main'; st.rerun()
                
                st.divider()
                st.dataframe(df_n, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("링크", display_text="🔗 보기")})
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                    df_n.to_excel(wr, index=False, sheet_name='Report')
                st.download_button(label="📥 분석 리포트(Excel) 다운로드", data=out.getvalue(), file_name=f"Report_{st.session_state.keyword}.xlsx", use_container_width=True)
            else:
                st.info("수집된 뉴스가 없습니다.")
else:
    st.info("👈 왼쪽 메뉴에서 키워드를 입력하고 레이더를 가동해 주세요!")
