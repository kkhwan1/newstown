# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import os
import sys
import json
import requests
import pandas as pd
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 사용자 계정 정보 (admin: 전체 권한, 일반 사용자: 네이버 API 설정 제외)
USERS = {
    "admin": {
        "password": hashlib.sha256("test1234".encode()).hexdigest(),
        "role": "admin"
    },
    "ksj0070086": {
        "password": hashlib.sha256("ksj0070086".encode()).hexdigest(),
        "role": "user"
    }
}


def check_login(username, password):
    """로그인 검증"""
    if username in USERS:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if USERS[username]["password"] == hashed:
            return True, USERS[username]["role"]
    return False, None


def render_login_page():
    """로그인 페이지"""
    st.markdown("# 뉴스타운 자동화 시스템")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 로그인")
        username = st.text_input("아이디", key="login_username")
        password = st.text_input("비밀번호", type="password", key="login_password")
        
        if st.button("로그인", type="primary", use_container_width=True):
            if username and password:
                success, role = check_login(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_role = role
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            else:
                st.warning("아이디와 비밀번호를 입력해주세요.")


def is_admin():
    """관리자 권한 확인"""
    return st.session_state.get("user_role") == "admin"

from utils.process_manager import ProcessManager
from utils.config_manager import ConfigManager

st.set_page_config(page_title="뉴스 자동화", page_icon="N", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main { background: #fff; font-family: -apple-system, sans-serif; }
    .stApp { background: #fff; }
    * { font-size: 13px; }
    h1 { font-size: 20px !important; font-weight: 600; color: #111; margin-bottom: 16px; }
    h2, h3 { font-size: 15px !important; font-weight: 600; color: #222; }
    .stButton>button { font-size: 12px; padding: 6px 16px; border-radius: 4px; }
    .stButton>button[kind="primary"] { background: #111; color: #fff; border: none; }
    .stButton>button[kind="secondary"] { background: #fff; color: #111; border: 1px solid #ddd; }
    .status-box { background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 12px; margin: 4px 0; }
    .status-run { color: #111; font-weight: 500; }
    .status-stop { color: #999; }
    .metric-box { text-align: center; padding: 8px; background: #fafafa; border-radius: 4px; }
    .metric-num { font-size: 20px; font-weight: 600; color: #111; }
    .metric-label { font-size: 11px; color: #666; }
    .data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .data-table th { background: #f5f5f5; padding: 8px 10px; text-align: left; font-weight: 500; border-bottom: 1px solid #ddd; }
    .data-table td { padding: 8px 10px; border-bottom: 1px solid #eee; color: #333; }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; margin: 1px; }
    .tag-cat { background: #f0f0f0; color: #333; }
    .tag-pending { background: #fff3cd; color: #856404; }
    .tag-uploaded { background: #d4edda; color: #155724; }
    .tag-failed { background: #f8d7da; color: #721c24; }
    .kw-tag { display: inline-block; background: #f5f5f5; border: 1px solid #ddd; padding: 3px 8px; border-radius: 3px; margin: 2px; font-size: 11px; }
    .search-item { background: #fafafa; border-left: 2px solid #111; padding: 8px 12px; margin: 4px 0; font-size: 12px; }
    div[data-testid="stSidebar"] { background: #fafafa; }
    div[data-testid="stSidebar"] * { font-size: 12px; }
    .stRadio label { font-size: 12px !important; }
    .stSelectbox label, .stTextInput label, .stNumberInput label { font-size: 11px !important; color: #666; }
    .stExpander { border: 1px solid #eee; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

SCRIPTS_DIR = current_dir / "scripts"
NEWS_SCRIPT = SCRIPTS_DIR / "run_news_collection.py"
UPLOAD_SCRIPT = SCRIPTS_DIR / "run_upload_monitor.py"
DELETION_SCRIPT = SCRIPTS_DIR / "run_row_deletion.py"
NAVER_API_CONFIG = current_dir / "config" / "naver_api.json"

PROC_NEWS = "news_collection"
PROC_UPLOAD = "upload_monitor"
PROC_DELETION = "row_deletion"


def load_naver_api():
    if NAVER_API_CONFIG.exists():
        with open(NAVER_API_CONFIG, 'r') as f:
            return json.load(f)
    return {"client_id": "", "client_secret": ""}


def save_naver_api(client_id, client_secret):
    NAVER_API_CONFIG.parent.mkdir(exist_ok=True)
    with open(NAVER_API_CONFIG, 'w') as f:
        json.dump({"client_id": client_id, "client_secret": client_secret}, f)


def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'process_manager' not in st.session_state:
        st.session_state.process_manager = ProcessManager()
    if 'config_manager' not in st.session_state:
        st.session_state.config_manager = ConfigManager()
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'selected_news' not in st.session_state:
        st.session_state.selected_news = set()
    if 'current_search_keyword' not in st.session_state:
        st.session_state.current_search_keyword = ''
    if 'current_search_category' not in st.session_state:
        st.session_state.current_search_category = ''


def init_database():
    try:
        from utils.database import init_database as db_init
        db_init()
        return True
    except:
        return False


def check_scheduled_news_collection():
    """스케줄된 뉴스 수집 체크 및 실행"""
    from datetime import datetime, timedelta
    
    if 'config_manager' not in st.session_state or 'process_manager' not in st.session_state:
        return
    
    cm = st.session_state.config_manager
    pm = st.session_state.process_manager
    
    schedule_config = cm.get("news_schedule")
    if not schedule_config.get("enabled", False):
        return
    
    news_status = pm.get_status(PROC_NEWS)
    if news_status['running']:
        return
    
    interval_hours = schedule_config.get("interval_hours", 3)
    last_run = schedule_config.get("last_run")
    
    now = datetime.now()
    should_run = False
    
    if last_run is None:
        should_run = True
    else:
        try:
            last_dt = datetime.fromisoformat(last_run)
            next_run = last_dt + timedelta(hours=interval_hours)
            if now >= next_run:
                should_run = True
        except:
            should_run = True
    
    if should_run:
        config = cm.get_news_config()
        pm.start_process(PROC_NEWS, str(NEWS_SCRIPT), config)
        cm.set("news_schedule", "last_run", now.isoformat())
        st.toast(f"스케줄된 뉴스 수집이 시작되었습니다.")


def search_naver_news(keyword, display=10, sort="date"):
    api = load_naver_api()
    if not api.get('client_id') or not api.get('client_secret'):
        return None, "네이버 API 설정 필요 (config/naver_api.json)"
    
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": api['client_id'], "X-Naver-Client-Secret": api['client_secret']}
    params = {"query": keyword, "display": display, "start": 1, "sort": sort}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            return [{
                'title': BeautifulSoup(i.get('title', ''), 'html.parser').get_text(),
                'content': BeautifulSoup(i.get('description', ''), 'html.parser').get_text(),
                'link': i.get('originallink') or i.get('link', ''),
                'pubDate': i.get('pubDate', '')
            } for i in items], None
        return None, f"API 오류: {resp.status_code}"
    except Exception as e:
        return None, str(e)


def normalize_text_for_dup(text):
    """텍스트 정규화 (중복 체크용)"""
    import re
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip().lower()
    text = re.sub(r'[^\w\s가-힣]', '', text)
    return text

def calculate_similarity_for_dup(text1, text2):
    """두 텍스트의 유사도 계산"""
    from difflib import SequenceMatcher
    if not text1 or not text2:
        return 0.0
    norm1 = normalize_text_for_dup(text1)
    norm2 = normalize_text_for_dup(text2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
    return SequenceMatcher(None, norm1, norm2).ratio()

def extract_key_phrases_for_dup(text):
    """핵심 키워드/구절 추출"""
    if not text:
        return set()
    normalized = normalize_text_for_dup(text)
    words = normalized.split()
    key_words = set(w for w in words if len(w) >= 2)
    for i in range(len(words) - 1):
        if len(words[i]) >= 2 and len(words[i+1]) >= 2:
            key_words.add(words[i] + words[i+1])
    return key_words

def is_duplicate_news(new_title, existing_titles, threshold=0.55):
    """중복 뉴스 체크 (유사도 55% 또는 키워드 70%)"""
    if not existing_titles:
        return False
    
    new_normalized = normalize_text_for_dup(new_title)
    new_phrases = extract_key_phrases_for_dup(new_title)
    
    for existing_title in existing_titles:
        existing_normalized = normalize_text_for_dup(existing_title)
        
        # 1. 완전 일치 체크
        if new_normalized == existing_normalized:
            return True
        
        # 2. 유사도 55% 이상이면 중복
        similarity = calculate_similarity_for_dup(new_title, existing_title)
        if similarity >= threshold:
            return True
        
        # 3. 핵심 키워드 70% 이상 겹치면 중복
        existing_phrases = extract_key_phrases_for_dup(existing_title)
        if new_phrases and existing_phrases:
            common = new_phrases.intersection(existing_phrases)
            smaller = min(len(new_phrases), len(existing_phrases))
            if smaller > 0 and len(common) / smaller >= 0.7:
                return True
    
    return False

def save_news_to_db_and_sheet(news_list, category, search_keyword=None):
    """뉴스를 DB와 구글 시트에 저장 (중복 체크 포함)
    
    Args:
        news_list: 저장할 뉴스 목록
        category: 대분류 카테고리 (연애/경제/스포츠)
        search_keyword: 검색에 사용된 키워드
    """
    from utils.database import save_news, get_connection
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    
    # 1. DB에서 기존 제목들 로드
    existing_db_titles = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT title FROM news")
        existing_db_titles = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        st.warning(f"DB 조회 오류: {e}")
    
    # 2. 시트에서 기존 제목들 로드
    existing_sheet_titles = []
    existing_sheet_links = set()
    sheet = None
    if sheet_url:
        try:
            creds_path = current_dir / 'credentials.json'
            if creds_path.exists():
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_url(sheet_url).sheet1
                all_values = sheet.get_all_values()
                for row in all_values[1:]:  # 헤더 제외
                    if len(row) > 0 and row[0]:
                        existing_sheet_titles.append(row[0])
                    if len(row) > 2 and row[2]:
                        existing_sheet_links.add(row[2])
        except Exception as e:
            st.warning(f"시트 조회 오류: {e}")
    
    # 3. 기존 제목 합치기
    all_existing_titles = list(set(existing_db_titles + existing_sheet_titles))
    
    # 4. 중복 필터링
    filtered_news = []
    skipped_count = 0
    saved_titles = []  # 이번에 저장된 제목들 (중복 방지)
    
    for n in news_list:
        link = n.get('link', '')
        title = n.get('title', '')
        
        # 링크 중복 체크
        if link in existing_sheet_links:
            skipped_count += 1
            continue
        
        # 기존 + 이번 저장 제목들과 중복 체크
        combined_titles = all_existing_titles + saved_titles
        if is_duplicate_news(title, combined_titles, 0.55):
            skipped_count += 1
            continue
        
        filtered_news.append(n)
        saved_titles.append(title)
        existing_sheet_links.add(link)
    
    if skipped_count > 0:
        st.info(f"중복 뉴스 {skipped_count}개 제외됨")
    
    # 5. 필터링된 뉴스 저장
    saved = 0
    for n in filtered_news:
        if save_news(n['title'], n['content'], n['link'], category, search_keyword=search_keyword):
            saved += 1
    
    # 6. 시트에 배치 저장 (A~D열에 고정)
    if sheet and filtered_news:
        try:
            rows = [[n['title'], n['content'], n['link'], category] for n in filtered_news]
            sheet.append_rows(rows, value_input_option='RAW', table_range='A:D')
        except Exception as e:
            st.warning(f"시트 저장 오류: {e}")
    
    return saved


def render_main_page():
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown("# 대시보드")
    
    col_link1, col_link2, col_link3 = st.columns([1, 1, 2])
    with col_link1:
        st.link_button("스프레드시트", "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit?gid=0#gid=0", use_container_width=True)
    with col_link2:
        st.link_button("Make 시나리오", "https://eu2.make.com/318441/scenarios/8251433/edit", use_container_width=True)

    category_keywords = cm.get("category_keywords", default={})
    news_config = cm.get("news_collection")
    keywords = dict(news_config.get('keywords', {"연애": 15, "경제": 15, "스포츠": 15}))
    categories = ["연애", "경제", "스포츠"]

    st.markdown("### 뉴스타운 업로드")
    st.caption("스프레드시트의 뉴스를 뉴스타운에 자동 업로드합니다")
    
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        upload_status = pm.get_status(PROC_UPLOAD)
        is_upload_run = upload_status['running']
        st.markdown(f'<div class="status-box"><b>업로드 감시</b><br><span class="{"status-run" if is_upload_run else "status-stop"}">{"● 실행중" if is_upload_run else "○ 중지됨"}</span></div>', unsafe_allow_html=True)
        
        if is_upload_run:
            if st.button("중지", key="stop_upload_main", use_container_width=True):
                pm.stop_process(PROC_UPLOAD)
                st.rerun()
        else:
            if st.button("뉴스타운 업로드 시작", key="start_upload_main", type="primary", use_container_width=True):
                config = cm.get_upload_config()
                pm.start_process(PROC_UPLOAD, str(UPLOAD_SCRIPT), config)
                st.rerun()
    
    with col_up2:
        deletion_status = pm.get_status(PROC_DELETION)
        is_del_run = deletion_status['running']
        st.markdown(f'<div class="status-box"><b>완료행 삭제</b><br><span class="{"status-run" if is_del_run else "status-stop"}">{"● 실행중" if is_del_run else "○ 중지됨"}</span></div>', unsafe_allow_html=True)
        
        if is_del_run:
            if st.button("중지", key="stop_del_main", use_container_width=True):
                pm.stop_process(PROC_DELETION)
                st.rerun()
        else:
            if st.button("완료행 삭제 시작", key="start_del_main", type="primary", use_container_width=True):
                config = cm.get_deletion_config()
                pm.start_process(PROC_DELETION, str(DELETION_SCRIPT), config)
                st.rerun()

    with st.expander("실행 로그", expanded=False):
        log_tabs = st.tabs(["업로드 감시", "완료행 삭제"])
        with log_tabs[0]:
            upload_logs = pm.get_logs(PROC_UPLOAD, lines=30)
            if upload_logs:
                st.code(upload_logs, language="text")
            else:
                st.caption("로그가 없습니다")
        with log_tabs[1]:
            del_logs = pm.get_logs(PROC_DELETION, lines=30)
            if del_logs:
                st.code(del_logs, language="text")
            else:
                st.caption("로그가 없습니다")

    st.markdown("---")
    
    st.markdown("### 뉴스 수집")
    st.caption("네이버 API로 뉴스를 수집하여 DB와 스프레드시트에 저장합니다")
    
    # 스케줄러 및 수집 설정 상태 표시
    schedule_config = cm.get("news_schedule")
    news_config = cm.get("news_collection")
    sort_option = news_config.get("sort", "sim")
    sort_text = "인기순" if sort_option == "sim" else "최신순"
    pub_keywords = news_config.get("keywords", {"연애": 15, "경제": 15, "스포츠": 15})
    total_count = sum(pub_keywords.values())
    
    # 수집 설정 요약 표시
    settings_text = f"정렬: {sort_text} | 총 {total_count}개 (연애 {pub_keywords.get('연애', 15)}, 경제 {pub_keywords.get('경제', 15)}, 스포츠 {pub_keywords.get('스포츠', 15)})"
    
    if schedule_config.get("enabled", False):
        interval = schedule_config.get("interval_hours", 3)
        last_run = schedule_config.get("last_run")
        if last_run:
            from datetime import datetime
            try:
                last_dt = datetime.fromisoformat(last_run)
                next_dt = last_dt + __import__('datetime').timedelta(hours=interval)
                now = datetime.now()
                if next_dt > now:
                    remaining = next_dt - now
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes = remainder // 60
                    st.success(f"자동 스케줄러 ON: {interval}시간 간격 | 다음 수집까지 {hours}시간 {minutes}분")
                else:
                    st.success(f"자동 스케줄러 ON: {interval}시간 간격 | 곧 수집 시작")
            except:
                st.success(f"자동 스케줄러 ON: {interval}시간 간격")
        else:
            st.success(f"자동 스케줄러 ON: {interval}시간 간격 | 첫 수집 대기중")
        st.caption(f"수집 설정: {settings_text}")
    else:
        st.caption(f"수집 설정: {settings_text} (스케줄러 OFF - 수동 수집만 가능)")
    
    news_status = pm.get_status(PROC_NEWS)
    is_news_run = news_status['running']
    
    col_n1, col_n2 = st.columns([2, 1])
    with col_n1:
        runtime_str = f" ({news_status['runtime']})" if news_status.get('runtime') else ""
        st.markdown(f'<div class="status-box"><b>뉴스 수집</b><br><span class="{"status-run" if is_news_run else "status-stop"}">{"● 실행중" + runtime_str if is_news_run else "○ 중지됨"}</span></div>', unsafe_allow_html=True)
    with col_n2:
        if is_news_run:
            if st.button("중지", key="stop_news_main", use_container_width=True):
                pm.stop_process(PROC_NEWS)
                st.rerun()
        else:
            if st.button("뉴스 수집 시작", key="start_news_main", type="primary", use_container_width=True):
                config = cm.get_news_config()
                pm.start_process(PROC_NEWS, str(NEWS_SCRIPT), config)
                st.rerun()

    if is_news_run:
        with st.expander("수집 로그", expanded=True):
            news_logs = pm.get_logs(PROC_NEWS, lines=50)
            if news_logs:
                st.code(news_logs, language="text")
                # 수집 완료 메시지 확인 시 자동 새로고침
                if "[완료] 수집 완료 요약" in news_logs:
                    import time
                    time.sleep(1)
                    st.rerun()
            else:
                st.caption("로그가 없습니다")
            if st.button("새로고침", key="refresh_news_log"):
                st.rerun()
        
        # 5초마다 자동 새로고침 (수집 중일 때만)
        import time
        time.sleep(5)
        st.rerun()

    st.markdown("---")
    
    news_status = pm.get_status(PROC_NEWS)
    if not news_status['running']:
        with st.expander("수집 설정", expanded=True):
            current_sort = cm.get("news_collection", "sort", "sim")
            default_sort_idx = 0 if current_sort == "sim" else 1
            sort_option = st.radio("정렬 방식", ["인기순", "최신순"], horizontal=True, key="sort_option", index=default_sort_idx, help="인기순: 관심도 높은 뉴스 / 최신순: 최근 발행 뉴스")
            new_sort = "sim" if sort_option == "인기순" else "date"
            if st.button("정렬 방식 저장", key="save_sort"):
                if new_sort != current_sort:
                    cm.set("news_collection", "sort", new_sort)
                    st.success("정렬 방식이 저장되었습니다.")
                    st.rerun()
            
        with st.expander("발행 개수 설정", expanded=True):
            mode = st.radio("설정 방식", ["전체 동일", "카테고리별"], horizontal=True, key="pub_mode")
            
            if mode == "전체 동일":
                current_val = keywords.get("연애", 15)
                total_count = st.number_input("전체 카테고리 발행 개수", min_value=0, max_value=100, value=current_val, key="total_pub")
                if st.button("적용", key="apply_total_pub"):
                    new_keywords = {cat: total_count for cat in categories}
                    if new_keywords != keywords:
                        cm.set("news_collection", "keywords", new_keywords)
                        st.rerun()
                display_keywords = {cat: total_count for cat in categories}
            else:
                cols = st.columns(3)
                new_keywords = {}
                for idx, cat in enumerate(categories):
                    with cols[idx]:
                        new_keywords[cat] = st.number_input(f"{cat}", min_value=0, max_value=100, value=keywords.get(cat, 15), key=f"pub_{cat}")
                if st.button("적용", key="apply_cat_pub"):
                    if new_keywords != keywords:
                        cm.set("news_collection", "keywords", new_keywords)
                        st.rerun()
                display_keywords = new_keywords
            
            total_sum = sum(display_keywords.values())
            st.caption(f"총 {total_sum}개 뉴스 수집 예정 (연애 {display_keywords['연애']} + 경제 {display_keywords['경제']} + 스포츠 {display_keywords['스포츠']})")

        with st.expander("자동 수집 스케줄", expanded=False):
            schedule_config = cm.get("news_schedule")
            schedule_enabled = schedule_config.get("enabled", False)
            schedule_interval = schedule_config.get("interval_hours", 3)
            last_run = schedule_config.get("last_run")
            
            new_enabled = st.checkbox("자동 수집 활성화", value=schedule_enabled, key="schedule_enabled")
            new_interval = st.number_input("수집 간격 (시간)", min_value=1, max_value=24, value=schedule_interval, key="schedule_interval")
            
            if last_run:
                from datetime import datetime, timedelta
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    next_dt = last_dt + timedelta(hours=schedule_interval)
                    st.caption(f"마지막 수집: {last_dt.strftime('%Y-%m-%d %H:%M')}")
                    st.caption(f"다음 수집 예정: {next_dt.strftime('%Y-%m-%d %H:%M')}")
                except:
                    st.caption("마지막 수집: 기록 없음")
            else:
                st.caption("마지막 수집: 아직 실행되지 않음")
            
            if st.button("스케줄 설정 저장", key="save_schedule"):
                if new_enabled != schedule_enabled or new_interval != schedule_interval:
                    cm.set("news_schedule", "enabled", new_enabled)
                    cm.set("news_schedule", "interval_hours", new_interval)
                    st.success("스케줄 설정이 저장되었습니다.")
                    st.rerun()

    st.markdown("---")

    with st.expander("키워드 설정", expanded=False):
        if 'keyword_saved' in st.session_state:
            st.success(st.session_state['keyword_saved'])
            del st.session_state['keyword_saved']
        
        for cat in categories:
            cat_data = category_keywords.get(cat, {"core": [], "general": []})
            core_kws = cat_data.get("core", [])
            kw_count = len(core_kws)
            
            st.markdown(f"**{cat}** ({kw_count}개 키워드)")
            
            if core_kws:
                cols = st.columns(min(len(core_kws), 6))
                for idx, kw in enumerate(core_kws):
                    with cols[idx % 6]:
                        if st.button(f"× {kw}", key=f"del_{cat}_{kw}"):
                            core_kws.remove(kw)
                            cat_data["core"] = core_kws
                            category_keywords[cat] = cat_data
                            if cm.set_section("category_keywords", category_keywords):
                                st.session_state['keyword_saved'] = f"'{kw}' 키워드가 삭제되었습니다."
                            else:
                                st.session_state['keyword_saved'] = f"'{kw}' 키워드 삭제 실패!"
                            st.rerun()
            
            c1, c2 = st.columns([5, 1])
            with c1:
                new_kw = st.text_input("키워드 추가", key=f"add_{cat}", placeholder="새 키워드 입력", label_visibility="collapsed")
            with c2:
                if st.button("+", key=f"btn_{cat}"):
                    if new_kw and new_kw not in core_kws:
                        core_kws.append(new_kw)
                        cat_data["core"] = core_kws
                        category_keywords[cat] = cat_data
                        if cm.set_section("category_keywords", category_keywords):
                            st.session_state['keyword_saved'] = f"'{new_kw}' 키워드가 추가되었습니다."
                        else:
                            st.session_state['keyword_saved'] = f"'{new_kw}' 키워드 추가 실패!"
                        st.rerun()
            
            st.markdown("---")


def get_sync_status():
    """DB와 스프레드시트 동기화 상태 확인"""
    from utils.database import get_connection
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    
    result = {
        "db_links": set(),
        "sheet_links": set(),
        "sheet_rows": {},  # link -> row_number
        "only_in_db": [],
        "only_in_sheet": [],
        "synced": []
    }
    
    # DB에서 모든 링크 가져오기
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, link, category FROM news WHERE status = 'pending'")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        for row in rows:
            if row[2]:
                result["db_links"].add(row[2])
    except Exception as e:
        print(f"DB 조회 오류: {e}")
    
    # 스프레드시트에서 모든 링크 가져오기
    if sheet_url:
        try:
            creds_path = current_dir / 'credentials.json'
            if creds_path.exists():
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_url(sheet_url).sheet1
                
                all_values = sheet.get_all_values()
                for i, row in enumerate(all_values[1:], start=2):  # 헤더 제외
                    if len(row) >= 3 and row[2]:  # C열=링크
                        link = row[2].strip()
                        result["sheet_links"].add(link)
                        result["sheet_rows"][link] = i
        except Exception as e:
            print(f"시트 조회 오류: {e}")
    
    # 차이 계산
    result["only_in_db"] = list(result["db_links"] - result["sheet_links"])
    result["only_in_sheet"] = list(result["sheet_links"] - result["db_links"])
    result["synced"] = list(result["db_links"] & result["sheet_links"])
    
    return result


def sync_delete_from_db(links):
    """시트에 없는 항목들을 DB에서 삭제"""
    from utils.database import get_connection
    
    deleted = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        for link in links:
            cur.execute("DELETE FROM news WHERE link = %s", (link,))
            deleted += cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB 삭제 오류: {e}")
    return deleted


def sync_delete_from_sheet(links, sheet_rows):
    """DB에 없는 항목들을 스프레드시트에서 삭제"""
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    
    deleted = 0
    if not sheet_url:
        return 0
    
    try:
        creds_path = current_dir / 'credentials.json'
        if creds_path.exists():
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_url(sheet_url).sheet1
            
            # 행 번호 내림차순으로 삭제 (아래에서부터)
            rows_to_delete = sorted([sheet_rows[link] for link in links if link in sheet_rows], reverse=True)
            for row_num in rows_to_delete:
                try:
                    sheet.delete_rows(row_num)
                    deleted += 1
                except:
                    pass
    except Exception as e:
        print(f"시트 삭제 오류: {e}")
    return deleted


def delete_news_from_db_and_sheet(news_id, link):
    """DB와 스프레드시트에서 뉴스 삭제"""
    from utils.database import get_connection
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    
    # 1. DB에서 삭제
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"DB 삭제 오류: {e}")
        return False
    
    # 2. 스프레드시트에서 삭제 (링크로 찾아서)
    if sheet_url and link:
        try:
            creds_path = current_dir / 'credentials.json'
            if creds_path.exists():
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_url(sheet_url).sheet1
                
                # C열(링크)에서 해당 링크 찾기
                try:
                    cell = sheet.find(link)
                    if cell:
                        sheet.delete_rows(cell.row)
                except:
                    pass  # 시트에 없으면 무시
        except Exception as e:
            st.warning(f"시트 삭제 오류: {e}")
    
    return True

def render_news_page():
    st.markdown("# 뉴스 조회")
    
    try:
        from utils.database import get_news_list, get_news_stats
        
        stats = get_news_stats()
        
        cols = st.columns(4)
        for col, (label, key) in zip(cols, [("전체", "total"), ("대기", "pending"), ("업로드", "uploaded"), ("실패", "failed")]):
            with col:
                st.markdown(f'<div class="metric-box"><div class="metric-num">{stats.get(key, 0)}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        tab1, tab2, tab3 = st.tabs(["📁 DB/시트 저장됨", "✅ 뉴스타운 업로드됨", "🔄 동기화"])
        
        with tab1:
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                cat = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="cat1")
            with c2:
                sort1 = st.selectbox("정렬", ["최신순", "오래된순"], key="sort1")
            with c3:
                if st.button("전체 삭제", key="del_all_pending", type="secondary"):
                    st.session_state.confirm_delete_all = True
            
            if st.session_state.get('confirm_delete_all', False):
                st.warning("정말로 모든 대기중 뉴스를 삭제하시겠습니까?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("예, 삭제합니다", type="primary", key="confirm_yes"):
                        from utils.database import get_connection
                        cat_val_del = None if cat == "전체" else cat
                        news_to_del = get_news_list(category=cat_val_del, status="pending", limit=500)
                        deleted = 0
                        for n in news_to_del:
                            if delete_news_from_db_and_sheet(n['id'], n.get('link', '')):
                                deleted += 1
                        st.success(f"{deleted}개 뉴스 삭제 완료")
                        st.session_state.confirm_delete_all = False
                        st.rerun()
                with c2:
                    if st.button("취소", key="confirm_no"):
                        st.session_state.confirm_delete_all = False
                        st.rerun()
            
            cat_val = None if cat == "전체" else cat
            news_list = get_news_list(category=cat_val, status="pending", limit=50)
            
            if sort1 == "오래된순":
                news_list = list(reversed(news_list))
            
            if news_list:
                st.caption(f"총 {len(news_list)}개 뉴스")
                
                # 표 형태로 데이터 표시
                table_data = []
                for n in news_list:
                    table_data.append({
                        "ID": n['id'],
                        "제목": n.get('title', '')[:50] + "...",
                        "카테고리": n.get('category', '-'),
                        "검색어": n.get('search_keyword', '-') or '-',
                        "수집일": str(n.get('created_at', ''))[:10]
                    })
                
                st.dataframe(
                    pd.DataFrame(table_data),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", width="small"),
                        "제목": st.column_config.TextColumn("제목", width="large"),
                        "카테고리": st.column_config.TextColumn("카테고리", width="small"),
                        "검색어": st.column_config.TextColumn("검색어", width="small"),
                        "수집일": st.column_config.TextColumn("수집일", width="small")
                    }
                )
                
                # 개별 삭제 영역
                with st.expander("개별 삭제 / 상세보기"):
                    selected_id = st.selectbox("뉴스 선택 (ID)", [n['id'] for n in news_list], format_func=lambda x: f"ID {x}: {next((n.get('title', '')[:40] for n in news_list if n['id'] == x), '')}")
                    selected_news = next((n for n in news_list if n['id'] == selected_id), None)
                    
                    if selected_news:
                        st.markdown(f"**제목**: {selected_news.get('title', '')}")
                        st.markdown(f"**카테고리**: {selected_news.get('category', '-')} | **검색어**: {selected_news.get('search_keyword', '-')}")
                        st.caption(selected_news.get('content', '')[:300] + "...")
                        st.markdown(f"[원문 링크]({selected_news.get('link', '')})")
                        
                        if st.button("이 뉴스 삭제", key="del_selected_pending", type="secondary"):
                            if delete_news_from_db_and_sheet(selected_news['id'], selected_news.get('link', '')):
                                st.success("삭제됨")
                                st.rerun()
            else:
                st.info("대기 중인 뉴스가 없습니다.")
        
        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                cat2 = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="cat2")
            with c2:
                sort2 = st.selectbox("정렬", ["최신순", "오래된순"], key="sort2")
            
            cat_val2 = None if cat2 == "전체" else cat2
            uploaded_list = get_news_list(category=cat_val2, status="uploaded", limit=50)
            
            if sort2 == "오래된순":
                uploaded_list = list(reversed(uploaded_list))
            
            if uploaded_list:
                st.caption(f"총 {len(uploaded_list)}개 업로드됨")
                
                # 표 형태로 데이터 표시
                table_data2 = []
                for n in uploaded_list:
                    uploaded_at = str(n.get('uploaded_at', ''))[:16] if n.get('uploaded_at') else '-'
                    table_data2.append({
                        "ID": n['id'],
                        "제목": n.get('title', '')[:50] + "...",
                        "카테고리": n.get('category', '-'),
                        "업로드일": uploaded_at
                    })
                
                st.dataframe(
                    pd.DataFrame(table_data2),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", width="small"),
                        "제목": st.column_config.TextColumn("제목", width="large"),
                        "카테고리": st.column_config.TextColumn("카테고리", width="small"),
                        "업로드일": st.column_config.TextColumn("업로드일", width="medium")
                    }
                )
                
                # 개별 삭제 영역
                with st.expander("개별 삭제 / 상세보기"):
                    selected_id2 = st.selectbox("뉴스 선택 (ID)", [n['id'] for n in uploaded_list], format_func=lambda x: f"ID {x}: {next((n.get('title', '')[:40] for n in uploaded_list if n['id'] == x), '')}", key="sel_uploaded")
                    selected_news2 = next((n for n in uploaded_list if n['id'] == selected_id2), None)
                    
                    if selected_news2:
                        uploaded_at2 = str(selected_news2.get('uploaded_at', ''))[:16] if selected_news2.get('uploaded_at') else '-'
                        st.markdown(f"**제목**: {selected_news2.get('title', '')}")
                        st.markdown(f"**카테고리**: {selected_news2.get('category', '-')} | **업로드 시간**: {uploaded_at2}")
                        st.caption(selected_news2.get('content', '')[:300] + "...")
                        
                        if st.button("이 뉴스 삭제", key="del_selected_uploaded", type="secondary"):
                            if delete_news_from_db_and_sheet(selected_news2['id'], selected_news2.get('link', '')):
                                st.success("삭제됨")
                                st.rerun()
            else:
                st.info("뉴스타운에 업로드된 뉴스가 없습니다.")
        
        with tab3:
            st.markdown("### DB ↔ 스프레드시트 동기화 상태")
            
            if st.button("동기화 상태 확인", type="primary"):
                with st.spinner("확인 중..."):
                    sync_status = get_sync_status()
                    st.session_state.sync_status = sync_status
            
            if 'sync_status' in st.session_state:
                sync = st.session_state.sync_status
                
                cols = st.columns(3)
                with cols[0]:
                    st.metric("동기화됨", len(sync["synced"]))
                with cols[1]:
                    st.metric("DB에만 있음", len(sync["only_in_db"]), delta=len(sync["only_in_db"]) if sync["only_in_db"] else None, delta_color="inverse")
                with cols[2]:
                    st.metric("시트에만 있음", len(sync["only_in_sheet"]), delta=len(sync["only_in_sheet"]) if sync["only_in_sheet"] else None, delta_color="inverse")
                
                st.markdown("---")
                
                # DB에만 있는 항목 (시트에서 삭제됨)
                if sync["only_in_db"]:
                    st.warning(f"DB에만 있는 뉴스: {len(sync['only_in_db'])}개 (시트에서 삭제됨)")
                    with st.expander("DB에만 있는 항목 보기"):
                        for link in sync["only_in_db"][:10]:
                            st.caption(link[:80] + "...")
                    
                    if st.button("DB에서 삭제 (시트와 맞춤)", key="sync_del_db"):
                        deleted = sync_delete_from_db(sync["only_in_db"])
                        st.success(f"DB에서 {deleted}개 삭제 완료")
                        if 'sync_status' in st.session_state:
                            del st.session_state.sync_status
                        st.rerun()
                
                # 시트에만 있는 항목 (DB에서 삭제됨)
                if sync["only_in_sheet"]:
                    st.warning(f"시트에만 있는 뉴스: {len(sync['only_in_sheet'])}개 (DB에서 삭제됨)")
                    with st.expander("시트에만 있는 항목 보기"):
                        for link in sync["only_in_sheet"][:10]:
                            st.caption(link[:80] + "...")
                    
                    if st.button("시트에서 삭제 (DB와 맞춤)", key="sync_del_sheet"):
                        deleted = sync_delete_from_sheet(sync["only_in_sheet"], sync["sheet_rows"])
                        st.success(f"시트에서 {deleted}개 삭제 완료")
                        if 'sync_status' in st.session_state:
                            del st.session_state.sync_status
                        st.rerun()
                
                if not sync["only_in_db"] and not sync["only_in_sheet"]:
                    st.success("DB와 스프레드시트가 완전히 동기화되었습니다!")
            
    except Exception as e:
        st.error(f"오류: {e}")


def render_search_page():
    st.markdown("# 키워드 검색")
    
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        keyword = st.text_input("검색어", placeholder="키워드 입력", label_visibility="collapsed")
    with c2:
        count = st.number_input("개수", min_value=5, max_value=100, value=20, label_visibility="collapsed")
    with c3:
        sort_opt = st.selectbox("정렬", ["최신순", "인기순"], label_visibility="collapsed")
    with c4:
        category = st.selectbox("카테고리", ["연애", "경제", "스포츠"], label_visibility="collapsed")

    sort_val = "date" if sort_opt == "최신순" else "sim"
    
    if st.button("검색", type="primary"):
        if keyword:
            results, err = search_naver_news(keyword, count, sort_val)
            if err:
                st.error(err)
            elif results:
                st.session_state.search_results = results
                st.session_state.selected_news = set()
                st.session_state.current_search_keyword = keyword
                st.session_state.current_search_category = category
            else:
                st.warning("결과 없음")

    if st.session_state.search_results:
        st.markdown("---")
        
        save_category = st.session_state.get('current_search_category', category)
        save_keyword = st.session_state.get('current_search_keyword', '')
        
        total_results = len(st.session_state.search_results)
        
        # 체크박스 상태를 session_state에서 동기화
        for idx in range(total_results):
            key = f"news_sel_{idx}"
            if key not in st.session_state:
                st.session_state[key] = idx in st.session_state.selected_news
        
        # 버튼 콜백 함수들
        def select_all_callback():
            for idx in range(total_results):
                st.session_state[f"news_sel_{idx}"] = True
            st.session_state.selected_news = set(range(total_results))
        
        def deselect_all_callback():
            for idx in range(total_results):
                st.session_state[f"news_sel_{idx}"] = False
            st.session_state.selected_news = set()
        
        def save_all_callback():
            all_news = st.session_state.search_results
            saved = save_news_to_db_and_sheet(all_news, save_category, search_keyword=save_keyword)
            st.session_state.save_message = f"전체 {saved}개 저장 완료! (카테고리: {save_category})"
            # 체크박스 상태 초기화
            for idx in range(total_results):
                if f"news_sel_{idx}" in st.session_state:
                    del st.session_state[f"news_sel_{idx}"]
            st.session_state.search_results = []
            st.session_state.selected_news = set()
            st.session_state.current_search_keyword = ''
            st.session_state.current_search_category = ''
        
        # 저장 메시지 표시
        if 'save_message' in st.session_state and st.session_state.save_message:
            st.success(st.session_state.save_message)
            st.session_state.save_message = ''
        
        c1, c2, c3 = st.columns([1.5, 1, 1])
        with c1:
            st.button(f"전체 선택 + 저장 ({total_results}개)", type="primary", key="save_all_btn", on_click=save_all_callback)
        with c2:
            st.button("전체 선택", key="select_all_btn", on_click=select_all_callback)
        with c3:
            st.button("선택 해제", key="deselect_btn", on_click=deselect_all_callback)
        
        # selected_news를 체크박스 상태에서 동기화
        current_selected = set()
        for idx in range(total_results):
            if st.session_state.get(f"news_sel_{idx}", False):
                current_selected.add(idx)
        st.session_state.selected_news = current_selected
        
        st.caption(f"검색 결과: {total_results}개 | 선택됨: {len(st.session_state.selected_news)}개")
        
        for idx, news in enumerate(st.session_state.search_results):
            col1, col2 = st.columns([0.05, 0.95])
            with col1:
                st.checkbox("선택", key=f"news_sel_{idx}", label_visibility="collapsed")
            with col2:
                st.markdown(f'<div class="search-item"><b>{news["title"]}</b><br><small>{news["content"][:100]}...</small></div>', unsafe_allow_html=True)

        selected_count = len(st.session_state.selected_news)
        if selected_count > 0:
            st.markdown("---")
            st.caption(f"저장 대상: {save_category} 카테고리, 검색어: {save_keyword}")
            if st.button(f"선택한 {selected_count}개 저장", type="primary", key="save_selected_btn"):
                selected = [st.session_state.search_results[i] for i in sorted(st.session_state.selected_news)]
                saved = save_news_to_db_and_sheet(selected, save_category, search_keyword=save_keyword)
                st.success(f"{saved}개 저장됨 (대분류: {save_category}, 검색어: {save_keyword})")
                # 체크박스 상태 초기화
                for idx in range(total_results):
                    if f"news_sel_{idx}" in st.session_state:
                        del st.session_state[f"news_sel_{idx}"]
                st.session_state.search_results = []
                st.session_state.selected_news = set()
                st.session_state.current_search_keyword = ''
                st.session_state.current_search_category = ''
                st.rerun()


def render_prompt_page():
    st.markdown("# 프롬프트 관리")
    
    try:
        from utils.database import get_prompts, save_prompt, update_prompt, delete_prompt
        
        prompts = get_prompts(active_only=False)
        
        # 저장된 프롬프트 목록
        st.markdown("### 저장된 프롬프트")
        if prompts:
            st.caption(f"총 {len(prompts)}개의 프롬프트")
            
            for p in prompts:
                with st.expander(f"**{p['name']}** ({p.get('category', '전체')}) - {'활성' if p.get('is_active') else '비활성'}"):
                    st.markdown("**프롬프트 내용:**")
                    st.text_area("내용 보기", value=p.get('prompt_text', ''), height=150, key=f"view_{p['id']}", disabled=True)
                    
                    st.markdown("---")
                    st.markdown("**편집:**")
                    
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        new_name = st.text_input("이름", value=p['name'], key=f"name_{p['id']}")
                    with c2:
                        cats = ["전체", "연애", "경제", "스포츠"]
                        current_cat = p.get('category', '전체')
                        cat_idx = cats.index(current_cat) if current_cat in cats else 0
                        new_cat = st.selectbox("카테고리", cats, index=cat_idx, key=f"cat_{p['id']}")
                    
                    new_content = st.text_area("내용 수정", value=p.get('prompt_text', ''), height=120, key=f"edit_{p['id']}")
                    
                    is_active = st.checkbox("활성화", value=p.get('is_active', True), key=f"active_{p['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("저장", key=f"save_{p['id']}", type="primary"):
                            update_prompt(p['id'], name=new_name, category=new_cat, prompt_text=new_content, is_active=is_active)
                            st.success("저장됨")
                            st.rerun()
                    with col2:
                        pass
                    with col3:
                        if st.button("삭제", key=f"del_{p['id']}"):
                            delete_prompt(p['id'])
                            st.rerun()
        else:
            st.info("저장된 프롬프트가 없습니다.")
        
        st.markdown("---")
        
        # 새 프롬프트 추가
        st.markdown("### 새 프롬프트 추가")
        c1, c2 = st.columns([3, 1])
        with c1:
            name = st.text_input("이름", placeholder="프롬프트 이름", key="new_prompt_name")
        with c2:
            cat = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="new_prompt_cat")
        content = st.text_area("내용", height=120, placeholder="프롬프트 내용을 입력하세요...", key="new_prompt_content")
        if st.button("추가", type="primary", key="add_prompt_btn"):
            if name and content:
                save_prompt(name, cat, content)
                st.success(f"'{name}' 프롬프트가 추가되었습니다.")
                st.rerun()
            else:
                st.warning("이름과 내용을 모두 입력해주세요.")
                
    except Exception as e:
        st.error(f"오류: {e}")


def render_log_page():
    st.markdown("# 실시간 로그")
    
    from utils.logger import get_logs, clear_logs
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("새로고침", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("로그 삭제", use_container_width=True):
            clear_logs()
            st.rerun()
    with col3:
        auto_refresh = st.checkbox("자동 새로고침 (5초)", value=False)
    
    if auto_refresh:
        import time
        time.sleep(5)
        st.rerun()
    
    category_filter = st.selectbox("카테고리 필터", ["전체", "뉴스수집", "업로드", "시스템"], index=0)
    
    cat_map = {"전체": None, "뉴스수집": "NEWS", "업로드": "UPLOAD", "시스템": "SYSTEM"}
    logs = get_logs(limit=200, category=cat_map.get(category_filter))
    
    if not logs:
        st.info("로그가 없습니다. 뉴스 수집이나 업로드를 시작하면 로그가 표시됩니다.")
    else:
        st.markdown(f"**최근 {len(logs)}개 로그**")
        
        log_html = '<div style="background:#f8f8f8; border:1px solid #ddd; border-radius:4px; padding:8px; max-height:500px; overflow-y:auto; font-family:monospace; font-size:11px;">'
        
        for log in logs:
            level = log.get('level', 'INFO')
            cat = log.get('category', 'SYSTEM')
            ts = log.get('timestamp', '')
            msg = log.get('message', '')
            
            if level == 'ERROR':
                color = '#dc3545'
            elif level == 'WARN':
                color = '#ffc107'
            elif level == 'SUCCESS':
                color = '#28a745'
            else:
                color = '#333'
            
            cat_badge = '#6c757d'
            if cat == 'NEWS':
                cat_badge = '#007bff'
            elif cat == 'UPLOAD':
                cat_badge = '#17a2b8'
            
            log_html += f'<div style="padding:4px 0; border-bottom:1px solid #eee;">'
            log_html += f'<span style="color:#888;">{ts}</span> '
            log_html += f'<span style="background:{cat_badge}; color:#fff; padding:1px 4px; border-radius:2px; font-size:10px;">{cat}</span> '
            log_html += f'<span style="color:{color};">{msg}</span>'
            log_html += '</div>'
        
        log_html += '</div>'
        
        st.markdown(log_html, unsafe_allow_html=True)


def render_settings_page():
    st.markdown("# 설정")
    
    cm = st.session_state.config_manager
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 구글 시트")
        url = st.text_input("URL", value=cm.get("google_sheet", "url", ""))
        if st.button("저장", key="save_sheet"):
            cm.set("google_sheet", "url", url)
            st.success("저장됨")

        st.markdown("### 뉴스타운")
        site_id = st.text_input("아이디", value=cm.get("newstown", "site_id", ""))
        site_pw = st.text_input("비밀번호", value=cm.get("newstown", "site_pw", ""), type="password")
        if st.button("저장", key="save_news"):
            cm.set("newstown", "site_id", site_id)
            cm.set("newstown", "site_pw", site_pw)
            st.success("저장됨")
    
    with c2:
        st.markdown("### 자동화 간격")
        check = st.number_input("업로드 체크 (초)", min_value=10, max_value=600, value=cm.get("upload_monitor", "check_interval", 30))
        delete = st.number_input("삭제 간격 (분)", min_value=1, max_value=1440, value=cm.get("row_deletion", "delete_interval", 60))
        concurrent = st.number_input("동시 업로드 개수", min_value=1, max_value=3, value=cm.get("upload_monitor", "concurrent_uploads", 2), help="뉴스타운에 동시에 업로드할 뉴스 개수 (1~3개)")
        if st.button("저장", key="save_interval"):
            cm.set("upload_monitor", "check_interval", check)
            cm.set("row_deletion", "delete_interval", delete)
            cm.set("upload_monitor", "concurrent_uploads", concurrent)
            st.success("저장됨")
        
        # 네이버 API 사용량 표시
        st.markdown("### 네이버 API 사용량")
        try:
            from naver_to_sheet import get_api_usage_info
            usage = get_api_usage_info()
            
            st.caption(f"날짜: {usage['date']}")
            
            # 프로그레스 바
            progress = usage['usage_percent'] / 100
            st.progress(min(progress, 1.0))
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("API 호출", f"{usage['calls']:,}회")
            with col_b:
                st.metric("수집 뉴스", f"{usage['news_count']:,}개")
            with col_c:
                st.metric("남은 한도", f"{usage['remaining']:,}회")
            
            st.caption(f"일일 한도: {usage['daily_limit']:,}회 ({usage['usage_percent']}% 사용)")
        except Exception as e:
            st.caption(f"API 사용량 조회 실패: {e}")
        
        # 네이버 API 설정 (관리자만 표시)
        if is_admin():
            st.markdown("### 네이버 API 설정")
            st.caption("config/naver_api.json 파일에 저장됨")
            api = load_naver_api()
            cid = st.text_input("Client ID", value=api.get('client_id', ''))
            csec = st.text_input("Client Secret", value=api.get('client_secret', ''), type="password")
            if st.button("저장", key="save_api"):
                save_naver_api(cid, csec)
                st.success("저장됨")


def main():
    init_session_state()
    
    # 로그인 체크
    if not st.session_state.logged_in:
        render_login_page()
        return
    
    init_database()
    
    cm = st.session_state.config_manager
    schedule_config = cm.get("news_schedule")
    if schedule_config.get("enabled", False):
        st_autorefresh(interval=5 * 60 * 1000, key="schedule_refresh")
    
    check_scheduled_news_collection()

    with st.sidebar:
        st.markdown(f"**{st.session_state.username}** 님")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.rerun()
        st.markdown("---")
        st.markdown("### 메뉴")
        page = st.radio("페이지 선택", ["대시보드", "키워드 검색", "뉴스 조회", "로그", "프롬프트", "설정"], label_visibility="collapsed")
        st.markdown("---")
        if st.button("모든 프로세스 중지", use_container_width=True):
            st.session_state.process_manager.stop_all()
            st.rerun()

    pages = {
        "대시보드": render_main_page,
        "키워드 검색": render_search_page,
        "뉴스 조회": render_news_page,
        "로그": render_log_page,
        "프롬프트": render_prompt_page,
        "설정": render_settings_page
    }
    pages[page]()


if __name__ == "__main__":
    main()
