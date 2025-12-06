# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import json
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

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
    if 'process_manager' not in st.session_state:
        st.session_state.process_manager = ProcessManager()
    if 'config_manager' not in st.session_state:
        st.session_state.config_manager = ConfigManager()
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'selected_news' not in st.session_state:
        st.session_state.selected_news = set()


def init_database():
    try:
        from utils.database import init_database as db_init
        db_init()
        return True
    except:
        return False


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


def save_news_to_db_and_sheet(news_list, category):
    from utils.database import save_news
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    saved = 0
    
    for n in news_list:
        if save_news(n['title'], n['content'], n['link'], category):
            saved += 1
    
    if sheet_url:
        try:
            creds_path = current_dir / 'credentials.json'
            if creds_path.exists():
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_url(sheet_url).sheet1
                rows = [[n['title'], n['content'], n['link'], category] for n in news_list]
                if rows:
                    sheet.append_rows(rows, value_input_option='RAW')
        except Exception as e:
            st.warning(f"시트 저장 오류: {e}")
    
    return saved


def render_main_page():
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown("# 대시보드")

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
            else:
                st.caption("로그가 없습니다")
            if st.button("새로고침", key="refresh_news_log"):
                st.rerun()

    st.markdown("---")
    
    news_status = pm.get_status(PROC_NEWS)
    if not news_status['running']:
        with st.expander("수집 설정", expanded=True):
            sort_option = st.radio("정렬 방식", ["인기순", "최신순"], horizontal=True, key="sort_option", help="인기순: 관심도 높은 뉴스 / 최신순: 최근 발행 뉴스")
            cm.set("news_collection", "sort", "sim" if sort_option == "인기순" else "date")
            
        with st.expander("발행 개수 설정", expanded=True):
            mode = st.radio("설정 방식", ["전체 동일", "카테고리별"], horizontal=True, key="pub_mode")
            
            if mode == "전체 동일":
                total_count = st.number_input("전체 카테고리 발행 개수", min_value=0, max_value=100, value=keywords.get("연애", 15), key="total_pub")
                for cat in categories:
                    keywords[cat] = total_count
            else:
                cols = st.columns(3)
                for idx, cat in enumerate(categories):
                    with cols[idx]:
                        keywords[cat] = st.number_input(f"{cat}", min_value=0, max_value=100, value=keywords.get(cat, 15), key=f"pub_{cat}")
            
            total_sum = sum(keywords.values())
            st.caption(f"총 {total_sum}개 뉴스 수집 예정 (연애 {keywords['연애']} + 경제 {keywords['경제']} + 스포츠 {keywords['스포츠']})")
            
            cm.set("news_collection", "keywords", keywords)

    st.markdown("---")

    with st.expander("키워드 설정", expanded=False):
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
                            cm.set_section("category_keywords", category_keywords)
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
                        cm.set_section("category_keywords", category_keywords)
                        st.rerun()
            
            st.markdown("---")


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

        tab1, tab2 = st.tabs(["📁 DB/시트 저장됨", "✅ 뉴스타운 업로드됨"])
        
        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                cat = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="cat1")
            with c2:
                sort1 = st.selectbox("정렬", ["최신순", "오래된순"], key="sort1")
            
            cat_val = None if cat == "전체" else cat
            news_list = get_news_list(category=cat_val, status="pending", limit=50)
            
            if sort1 == "오래된순":
                news_list = list(reversed(news_list))
            
            if news_list:
                data = []
                for n in news_list:
                    data.append({
                        "제목": n.get('title', '')[:50] + "...",
                        "카테고리": n.get('category', '-'),
                        "수집일": str(n.get('created_at', ''))[:10]
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
                
                with st.expander("상세 보기"):
                    for n in news_list[:10]:
                        st.markdown(f"**{n.get('title', '')}**")
                        st.caption(n.get('content', '')[:200])
                        st.markdown("---")
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
                data = []
                for n in uploaded_list:
                    data.append({
                        "제목": n.get('title', '')[:50] + "...",
                        "카테고리": n.get('category', '-'),
                        "업로드일": str(n.get('uploaded_at', ''))[:10] if n.get('uploaded_at') else '-'
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("뉴스타운에 업로드된 뉴스가 없습니다.")
            
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
            else:
                st.warning("결과 없음")

    if st.session_state.search_results:
        st.markdown("---")
        
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("전체 선택"):
                st.session_state.selected_news = set(range(len(st.session_state.search_results)))
                st.rerun()
        with c2:
            if st.button("선택 해제"):
                st.session_state.selected_news = set()
                st.rerun()
        
        for idx, news in enumerate(st.session_state.search_results):
            c1, c2 = st.columns([0.05, 0.95])
            with c1:
                sel = st.checkbox("", value=idx in st.session_state.selected_news, key=f"s{idx}", label_visibility="collapsed")
                if sel:
                    st.session_state.selected_news.add(idx)
                else:
                    st.session_state.selected_news.discard(idx)
            with c2:
                st.markdown(f'<div class="search-item"><b>{news["title"]}</b><br><small>{news["content"][:100]}...</small></div>', unsafe_allow_html=True)

        selected_count = len(st.session_state.selected_news)
        if selected_count > 0:
            st.markdown("---")
            if st.button(f"선택한 {selected_count}개 저장", type="primary"):
                selected = [st.session_state.search_results[i] for i in st.session_state.selected_news]
                saved = save_news_to_db_and_sheet(selected, category)
                st.success(f"{saved}개 저장됨")
                st.session_state.search_results = []
                st.session_state.selected_news = set()


def render_prompt_page():
    st.markdown("# 프롬프트 관리")
    
    try:
        from utils.database import get_prompts, save_prompt, update_prompt, delete_prompt
        
        with st.expander("새 프롬프트"):
            c1, c2 = st.columns([3, 1])
            with c1:
                name = st.text_input("이름", placeholder="프롬프트 이름")
            with c2:
                cat = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="p_cat")
            content = st.text_area("내용", height=80, placeholder="프롬프트 내용...")
            if st.button("추가", type="primary"):
                if name and content:
                    save_prompt(name, cat, content)
                    st.rerun()

        prompts = get_prompts(active_only=False)
        if prompts:
            data = []
            for p in prompts:
                data.append({
                    "이름": p['name'],
                    "카테고리": p.get('category', '전체'),
                    "상태": "활성" if p.get('is_active') else "비활성"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            
            with st.expander("편집/삭제"):
                sel_prompt = st.selectbox("프롬프트 선택", [p['name'] for p in prompts])
                sel_p = next((p for p in prompts if p['name'] == sel_prompt), None)
                if sel_p:
                    edited = st.text_area("내용", value=sel_p.get('prompt_text', ''), height=80)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("저장"):
                            update_prompt(sel_p['id'], prompt_text=edited)
                            st.success("저장됨")
                    with c2:
                        if st.button("삭제"):
                            delete_prompt(sel_p['id'])
                            st.rerun()
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
        if st.button("저장", key="save_interval"):
            cm.set("upload_monitor", "check_interval", check)
            cm.set("row_deletion", "delete_interval", delete)
            st.success("저장됨")
        
        st.markdown("### 네이버 API")
        st.caption("config/naver_api.json 파일에 저장됨")
        api = load_naver_api()
        cid = st.text_input("Client ID", value=api.get('client_id', ''))
        csec = st.text_input("Client Secret", value=api.get('client_secret', ''), type="password")
        if st.button("저장", key="save_api"):
            save_naver_api(cid, csec)
            st.success("저장됨")


def main():
    init_session_state()
    init_database()

    with st.sidebar:
        st.markdown("### 메뉴")
        page = st.radio("", ["대시보드", "키워드 검색", "뉴스 조회", "로그", "프롬프트", "설정"], label_visibility="collapsed")
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
