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
    initial_sidebar_state="auto" # 화면 크기에 따라 스트림릿이 알아서 판단하도록 설정
)

# 화면 전환을 위한 상태값 초기화
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'main'
if 'selected_keyword' not in st.session_state:
    st.session_state.selected_keyword = None
if 'keyword' not in st.session_state:
    st.session_state.keyword = ""

# 🌟 모바일에서 검색 후 메뉴를 자동으로 닫기 위한 자바스크립트 효과 🌟
st.markdown("""
    <style>
    /* 상단 거슬리는 텍스트 및 불필요한 헤더 숨기기 */
    header[data-testid="stHeader"] { visibility: hidden; height: 0; }
    [data-testid="stSidebarNav"] { display: none; }
    .css-1d391kg { padding-top: 1rem; }
    
    /* 텍스트 입력창 디자인 커스텀 */
    div[data-testid="stTextInput"] input {
        background-color: #FFF4CE !important;
        border: 3px solid #FFB300 !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        color: #333333 !important;
        font-size: 16px !important;
    }
    
    /* 모바일에서 결과 표가 잘 보이도록 간격 조정 */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem 0.5rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔥 Trend Radar: 통합 이슈 & 뉴스 분석")
st.markdown("마케팅 AE를 위한 실전 롱테일 키워드 제안 도구입니다.")

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
                    <div style="width: 120px; height: 120px; border-radius: 50%; overflow: hidden; box-shadow: 0px 4px 15px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center;">
                        <img src="data:image/jpeg;base64,{b64}" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    <div style="margin-top: 15px; font-size: 20px; font-weight: bold; color: #31333F;">🔥Trend Radar</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except FileNotFoundError:
        st.warning("⚠️ 'profile.jpg' 없음")

    with st.form(key="search_form"):
        st.header("🔎 분석 설정")
        keyword_input = st.text_input("분석 키워드 입력", value=st.session_state.keyword)
        days_option = st.radio("기간", ["최근 3일", "최근 7일", "최근 30일", "최근 60일"], index=1)
        days_dict = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "최근 60일": 60}
        days = days_dict[days_option]
        st.divider()
        submit_btn = st.form_submit_button("🚀 데이터 레이더 가동", use_container_width=True)
        
        if submit_btn:
            if keyword_input.strip() == "":
                st.error("⚠️ 키워드 입력 필수")
            else:
                st.session_state.view_mode = 'main'
                st.session_state.keyword = keyword_input
                # 검색이 시작되면 모바일에서는 메뉴가 닫히도록 유도 (자동 새로고침 효과)

# 4. 기능 함수들
@st.cache_data(show_spinner=False)
def get_ad_suggestions(main_word):
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={main_word}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        suggestions = response.json()[1] 
        result = [kw for kw in suggestions if kw != main_word][:10]
        return result if result else [f"{main_word} 추천", f"{main_word} 후기"]
    except: return ["데이터 오류"]

def extract_main_keywords(titles, current_keyword):
    words = []
    stop_words = [current_keyword, '뉴스', '연합뉴스', '조선일보', '중앙일보', '동아일보', '경향신문', '한겨레', '매일경제', '한국경제', 'YTN', 'SBS', 'KBS', 'MBC', 'JTBC', '뉴시스', '뉴스핌', '데일리', '기자', '기사']
    for title in titles:
        clean_title = re.sub(r'[^\w\s]', ' ', title.split(' - ')[0])
        for word in clean_title.split():
            if len(word) > 1 and word not in stop_words: words.append(word)
    return [w for w, c in Counter(words).most_common(5)]

def fetch_data(query, days):
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

# 5. 화면 렌더링 로직
if st.session_state.keyword:
    # 🌟 모바일 대응: 검색 결과가 나오면 사이드바가 접히도록 안내 메시지 추가 🌟
    st.info(f"📡 '{st.session_state.keyword}' 분석 결과를 불러왔습니다. 왼쪽 메뉴가 화면을 가린다면 화살표(X)를 눌러 닫아주세요.")
    
    data = fetch_data(st.session_state.keyword, days)
    if data:
        df = pd.DataFrame(data)
        if "날짜" in df.columns:
            df = df.sort_values(by="날짜", ascending=False).reset_index(drop=True)
        
        if st.session_state.view_mode == 'detail':
            st.divider()
            if st.button("⬅️ 뒤로가기", use_container_width=True):
                st.session_state.view_mode = 'main'
                st.rerun()
            st.success(f"💡 **'{st.session_state.selected_keyword}'** 연관 키워드")
            ad_words = get_ad_suggestions(st.session_state.selected_keyword)
            for aw in ad_words: st.code(aw)
        else:
            top_words = extract_main_keywords(df['제목'].tolist(), st.session_state.keyword)
            if top_words:
                st.subheader("📌 핵심 키워드")
                for w in top_words:
                    if st.button(f"#{w}", key=f"kw_{w}", use_container_width=True):
                        st.session_state.view_mode = 'detail'
                        st.session_state.selected_keyword = w
                        st.rerun()
            
            st.divider()
            st.subheader(f"📊 분석 결과 (총 {len(df)}건)")
            st.dataframe(df, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("링크", display_text="🔗 보기")})
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')
            st.download_button(label="📥 리포트 다운로드", data=output.getvalue(), file_name=f"TrendRadar_{st.session_state.keyword}.xlsx", use_container_width=True)
    else: st.warning("결과가 없습니다.")
else:
    st.info("👈 왼쪽 사이드바에 키워드를 입력하고 실행해 주세요!")
