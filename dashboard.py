# -*- coding: utf-8 -*-
"""
뉴스 자동화 대시보드
Streamlit 기반 GUI로 뉴스 수집, 업로드 감시, 프롬프트 관리 기능 통합
"""
import streamlit as st
import os
import sys
import requests
import urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from utils.process_manager import ProcessManager
from utils.config_manager import ConfigManager

st.set_page_config(
    page_title="뉴스 자동화",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #ffffff; }
    .status-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 500; }
    .status-running { background: #d4edda; color: #155724; }
    .status-stopped { background: #f8d7da; color: #721c24; }
    .compact-box { background: #f8f9fa; border-radius: 8px; padding: 12px; margin: 8px 0; }
    .news-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; margin: 8px 0; }
    .news-title { font-weight: 600; color: #1d1d1f; margin-bottom: 4px; }
    .news-meta { font-size: 0.8rem; color: #666; }
    .keyword-tag { display: inline-block; background: #e8f4fd; color: #0056b3; padding: 4px 10px; border-radius: 16px; margin: 3px; font-size: 0.85rem; }
    .keyword-tag-delete { display: inline-block; background: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 16px; margin: 3px; font-size: 0.85rem; cursor: pointer; }
    .search-result { background: #f8f9fa; border-left: 3px solid #0056b3; padding: 10px; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

SCRIPTS_DIR = current_dir / "scripts"
NEWS_SCRIPT = SCRIPTS_DIR / "run_news_collection.py"
UPLOAD_SCRIPT = SCRIPTS_DIR / "run_upload_monitor.py"
DELETION_SCRIPT = SCRIPTS_DIR / "run_row_deletion.py"

PROC_NEWS = "news_collection"
PROC_UPLOAD = "upload_monitor"
PROC_DELETION = "row_deletion"


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
    except Exception as e:
        st.error(f"DB 초기화 실패: {e}")
        return False


def search_naver_news(keyword, display=10, sort="date"):
    """네이버 뉴스 API로 검색"""
    cm = st.session_state.config_manager
    client_id = cm.get("naver_api", "client_id", "")
    client_secret = cm.get("naver_api", "client_secret", "")
    
    if not client_id or not client_secret:
        return None, "네이버 API 설정이 필요합니다. 설정 페이지에서 API 정보를 입력해주세요."
    
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": keyword,
        "display": display,
        "start": 1,
        "sort": sort
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            results = []
            for item in items:
                title = BeautifulSoup(item.get('title', ''), 'html.parser').get_text()
                description = BeautifulSoup(item.get('description', ''), 'html.parser').get_text()
                results.append({
                    'title': title,
                    'content': description,
                    'link': item.get('originallink') or item.get('link', ''),
                    'pubDate': item.get('pubDate', '')
                })
            return results, None
        else:
            return None, f"API 오류: {response.status_code}"
    except Exception as e:
        return None, f"검색 오류: {str(e)}"


def save_news_to_db_and_sheet(news_list, category):
    """뉴스를 DB와 구글시트에 저장"""
    from utils.database import save_news
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    
    cm = st.session_state.config_manager
    sheet_url = cm.get("google_sheet", "url", "")
    
    saved_count = 0
    
    for news in news_list:
        db_id = save_news(
            title=news['title'],
            content=news['content'],
            link=news['link'],
            category=category
        )
        if db_id:
            saved_count += 1
    
    if sheet_url:
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds_path = current_dir / 'credentials.json'
            if creds_path.exists():
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_path), scope)
                client = gspread.authorize(creds)
                doc = client.open_by_url(sheet_url)
                sheet = doc.sheet1
                
                rows = [[n['title'], n['content'], n['link'], category] for n in news_list]
                if rows:
                    sheet.append_rows(rows, value_input_option='RAW')
        except Exception as e:
            st.warning(f"시트 저장 실패: {e}")
    
    return saved_count


def render_main_page():
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.title("뉴스 자동화 대시보드")

    col1, col2, col3 = st.columns(3)
    
    news_status = pm.get_status(PROC_NEWS)
    upload_status = pm.get_status(PROC_UPLOAD)
    deletion_status = pm.get_status(PROC_DELETION)

    with col1:
        status_class = "status-running" if news_status['running'] else "status-stopped"
        status_text = "실행중" if news_status['running'] else "중지됨"
        st.markdown(f'<div class="compact-box"><b>뉴스 수집</b><br><span class="status-badge {status_class}">{status_text}</span></div>', unsafe_allow_html=True)
        
        if news_status['running']:
            if st.button("중지", key="stop_news", use_container_width=True):
                pm.stop_process(PROC_NEWS)
                st.rerun()
        else:
            if st.button("시작", key="start_news", type="primary", use_container_width=True):
                config = cm.get_news_config()
                pm.start_process(PROC_NEWS, str(NEWS_SCRIPT), config)
                st.rerun()

    with col2:
        status_class = "status-running" if upload_status['running'] else "status-stopped"
        status_text = "실행중" if upload_status['running'] else "중지됨"
        st.markdown(f'<div class="compact-box"><b>업로드 감시</b><br><span class="status-badge {status_class}">{status_text}</span></div>', unsafe_allow_html=True)
        
        if upload_status['running']:
            if st.button("중지", key="stop_upload", use_container_width=True):
                pm.stop_process(PROC_UPLOAD)
                st.rerun()
        else:
            if st.button("시작", key="start_upload", type="primary", use_container_width=True):
                config = cm.get_upload_config()
                pm.start_process(PROC_UPLOAD, str(UPLOAD_SCRIPT), config)
                st.rerun()

    with col3:
        status_class = "status-running" if deletion_status['running'] else "status-stopped"
        status_text = "실행중" if deletion_status['running'] else "중지됨"
        st.markdown(f'<div class="compact-box"><b>완료행 삭제</b><br><span class="status-badge {status_class}">{status_text}</span></div>', unsafe_allow_html=True)
        
        if deletion_status['running']:
            if st.button("중지", key="stop_deletion", use_container_width=True):
                pm.stop_process(PROC_DELETION)
                st.rerun()
        else:
            if st.button("시작", key="start_deletion", type="primary", use_container_width=True):
                config = cm.get_deletion_config()
                pm.start_process(PROC_DELETION, str(DELETION_SCRIPT), config)
                st.rerun()

    st.divider()

    with st.expander("키워드 설정", expanded=True):
        news_config = cm.get("news_collection")
        keywords = dict(news_config.get('keywords', {"연애": 15, "경제": 15, "스포츠": 15}))
        category_keywords = cm.get("category_keywords", default={})

        cols = st.columns(len(keywords))
        for idx, (kw, cnt) in enumerate(keywords.items()):
            with cols[idx]:
                new_cnt = st.number_input(f"{kw} 수집 개수", min_value=1, max_value=100, value=cnt, key=f"cnt_{kw}")
                if new_cnt != cnt:
                    keywords[kw] = new_cnt
                    cm.set("news_collection", "keywords", keywords)

        st.markdown("---")
        
        selected_cat = st.selectbox("카테고리 선택", list(keywords.keys()), key="cat_select")
        
        if selected_cat:
            cat_data = category_keywords.get(selected_cat, {"core": [], "general": []})
            
            st.markdown("**Core 키워드** (실제 검색에 사용)")
            core_kws = cat_data.get("core", [])
            
            if core_kws:
                cols_per_row = 5
                for i in range(0, len(core_kws), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, kw in enumerate(core_kws[i:i+cols_per_row]):
                        with cols[j]:
                            if st.button(f"❌ {kw}", key=f"del_core_{selected_cat}_{kw}"):
                                core_kws.remove(kw)
                                cat_data["core"] = core_kws
                                category_keywords[selected_cat] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()
            else:
                st.caption("등록된 키워드 없음")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                new_core = st.text_input("새 Core 키워드", key=f"new_core_{selected_cat}", placeholder="키워드 입력")
            with col2:
                st.write("")
                st.write("")
                if st.button("추가", key=f"add_core_{selected_cat}"):
                    if new_core and new_core not in core_kws:
                        core_kws.append(new_core)
                        cat_data["core"] = core_kws
                        category_keywords[selected_cat] = cat_data
                        cm.set_section("category_keywords", category_keywords)
                        st.rerun()

            st.markdown("**General 키워드** (분류에 사용)")
            general_kws = cat_data.get("general", [])
            
            if general_kws:
                cols_per_row = 5
                for i in range(0, len(general_kws), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, kw in enumerate(general_kws[i:i+cols_per_row]):
                        with cols[j]:
                            if st.button(f"❌ {kw}", key=f"del_gen_{selected_cat}_{kw}"):
                                general_kws.remove(kw)
                                cat_data["general"] = general_kws
                                category_keywords[selected_cat] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()
            else:
                st.caption("등록된 키워드 없음")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                new_general = st.text_input("새 General 키워드", key=f"new_gen_{selected_cat}", placeholder="키워드 입력")
            with col2:
                st.write("")
                st.write("")
                if st.button("추가", key=f"add_gen_{selected_cat}"):
                    if new_general and new_general not in general_kws:
                        general_kws.append(new_general)
                        cat_data["general"] = general_kws
                        category_keywords[selected_cat] = cat_data
                        cm.set_section("category_keywords", category_keywords)
                        st.rerun()


def render_news_page():
    st.title("수집된 뉴스")
    
    try:
        from utils.database import get_news_list, get_news_stats
        
        stats = get_news_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("전체", stats.get('total', 0))
        col2.metric("대기중", stats.get('pending', 0))
        col3.metric("업로드됨", stats.get('uploaded', 0))
        col4.metric("실패", stats.get('failed', 0))

        st.divider()

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            category_filter = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"])
        with col2:
            status_filter = st.selectbox("상태", ["전체", "pending", "uploaded", "failed"])
        with col3:
            sort_order = st.selectbox("정렬", ["최신순", "오래된순"])

        cat = None if category_filter == "전체" else category_filter
        stat = None if status_filter == "전체" else status_filter
        
        news_list = get_news_list(category=cat, status=stat, limit=30)
        
        if sort_order == "오래된순":
            news_list = list(reversed(news_list))

        if news_list:
            for news in news_list:
                created = str(news.get('created_at', ''))[:16] if news.get('created_at') else ''
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-title">{news.get('title', '')[:80]}...</div>
                    <div class="news-meta">
                        <span class="keyword-tag">{news.get('category', '미분류')}</span>
                        상태: {news.get('status', 'pending')} | {created}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("본문 보기"):
                    content = news.get('content', '')
                    st.write(content[:500] + "..." if len(content) > 500 else content)
                    if news.get('link'):
                        st.markdown(f"[원본 링크]({news.get('link')})")
        else:
            st.info("수집된 뉴스가 없습니다.")
            
    except Exception as e:
        st.error(f"오류: {e}")


def render_search_page():
    st.title("키워드 뉴스 검색")
    st.caption("키워드로 뉴스를 검색하고, 선택한 뉴스를 DB와 스프레드시트에 저장합니다.")
    
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        search_keyword = st.text_input("검색 키워드", placeholder="검색할 키워드 입력")
    with col2:
        search_count = st.number_input("검색 개수", min_value=5, max_value=100, value=20)
    with col3:
        sort_option = st.selectbox("정렬", ["최신순", "인기순"])
    with col4:
        target_category = st.selectbox("저장 카테고리", ["연애", "경제", "스포츠"])

    sort_value = "date" if sort_option == "최신순" else "sim"
    
    if st.button("검색", type="primary"):
        if search_keyword:
            with st.spinner("검색 중..."):
                results, error = search_naver_news(search_keyword, search_count, sort_value)
                if error:
                    st.error(error)
                elif results:
                    st.session_state.search_results = results
                    st.session_state.selected_news = set()
                    st.success(f"{len(results)}개의 뉴스를 찾았습니다.")
                else:
                    st.warning("검색 결과가 없습니다.")
        else:
            st.warning("검색 키워드를 입력해주세요.")

    if st.session_state.search_results:
        st.divider()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("전체 선택"):
                st.session_state.selected_news = set(range(len(st.session_state.search_results)))
                st.rerun()
        with col2:
            if st.button("선택 해제"):
                st.session_state.selected_news = set()
                st.rerun()
        
        for idx, news in enumerate(st.session_state.search_results):
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                is_selected = st.checkbox("", value=idx in st.session_state.selected_news, key=f"sel_{idx}")
                if is_selected:
                    st.session_state.selected_news.add(idx)
                else:
                    st.session_state.selected_news.discard(idx)
            
            with col2:
                st.markdown(f"""
                <div class="search-result">
                    <b>{news['title']}</b><br>
                    <small>{news['content'][:150]}...</small><br>
                    <small style="color:#666">{news.get('pubDate', '')}</small>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        
        selected_count = len(st.session_state.selected_news)
        st.write(f"**선택된 뉴스: {selected_count}개**")
        
        if selected_count > 0:
            if st.button(f"선택한 {selected_count}개 뉴스 저장 (DB + 시트)", type="primary"):
                selected_news = [st.session_state.search_results[i] for i in st.session_state.selected_news]
                saved = save_news_to_db_and_sheet(selected_news, target_category)
                st.success(f"{saved}개의 뉴스가 저장되었습니다!")
                st.session_state.search_results = []
                st.session_state.selected_news = set()


def render_prompt_page():
    st.title("프롬프트 관리")
    
    try:
        from utils.database import get_prompts, save_prompt, update_prompt, delete_prompt
        
        with st.expander("새 프롬프트 추가", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                new_name = st.text_input("프롬프트 이름", placeholder="예: 뉴스 요약 프롬프트")
            with col2:
                new_category = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"], key="new_cat")
            
            new_prompt = st.text_area("프롬프트 내용", height=120, placeholder="AI 가공용 프롬프트 입력...")
            
            if st.button("프롬프트 추가", type="primary"):
                if new_name and new_prompt:
                    save_prompt(new_name, new_category, new_prompt)
                    st.success("추가되었습니다!")
                    st.rerun()
                else:
                    st.warning("이름과 내용을 입력해주세요.")

        st.divider()

        prompts = get_prompts(active_only=False)
        
        if prompts:
            for prompt in prompts:
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.markdown(f"**{prompt['name']}** ({prompt.get('category', '전체')})")
                with col2:
                    st.caption("활성" if prompt.get('is_active') else "비활성")
                with col3:
                    if st.button("삭제", key=f"del_{prompt['id']}"):
                        delete_prompt(prompt['id'])
                        st.rerun()
                
                with st.expander("보기/편집"):
                    edited = st.text_area("내용", value=prompt.get('prompt_text', ''), key=f"edit_{prompt['id']}", height=100)
                    if st.button("저장", key=f"save_{prompt['id']}"):
                        update_prompt(prompt['id'], prompt_text=edited)
                        st.success("저장됨!")
        else:
            st.info("저장된 프롬프트가 없습니다.")
            
    except Exception as e:
        st.error(f"오류: {e}")


def render_settings_page():
    st.title("설정")
    
    cm = st.session_state.config_manager
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("구글 시트")
        sheet_url = st.text_input("시트 URL", value=cm.get("google_sheet", "url", ""))
        if st.button("URL 저장"):
            cm.set("google_sheet", "url", sheet_url)
            st.success("저장됨!")

        st.subheader("네이버 API")
        client_id = st.text_input("Client ID", value=cm.get("naver_api", "client_id", ""))
        client_secret = st.text_input("Client Secret", value=cm.get("naver_api", "client_secret", ""), type="password")
        if st.button("API 저장"):
            cm.set("naver_api", "client_id", client_id)
            cm.set("naver_api", "client_secret", client_secret)
            st.success("저장됨!")
    
    with col2:
        st.subheader("뉴스타운 로그인")
        site_id = st.text_input("아이디", value=cm.get("newstown", "site_id", ""))
        site_pw = st.text_input("비밀번호", value=cm.get("newstown", "site_pw", ""), type="password")
        if st.button("로그인 정보 저장"):
            cm.set("newstown", "site_id", site_id)
            cm.set("newstown", "site_pw", site_pw)
            st.success("저장됨!")

        st.subheader("자동화 간격")
        check_interval = st.number_input("업로드 체크 (초)", min_value=10, max_value=600, value=cm.get("upload_monitor", "check_interval", 30))
        delete_interval = st.number_input("삭제 간격 (분)", min_value=1, max_value=1440, value=cm.get("row_deletion", "delete_interval", 60))
        if st.button("간격 저장"):
            cm.set("upload_monitor", "check_interval", check_interval)
            cm.set("row_deletion", "delete_interval", delete_interval)
            st.success("저장됨!")


def main():
    init_session_state()
    init_database()

    with st.sidebar:
        st.title("메뉴")
        page = st.radio(
            "페이지 선택",
            ["대시보드", "키워드 검색", "뉴스 조회", "프롬프트 관리", "설정"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        pm = st.session_state.process_manager
        if st.button("모든 프로세스 중지", use_container_width=True):
            pm.stop_all()
            st.rerun()

    if page == "대시보드":
        render_main_page()
    elif page == "키워드 검색":
        render_search_page()
    elif page == "뉴스 조회":
        render_news_page()
    elif page == "프롬프트 관리":
        render_prompt_page()
    elif page == "설정":
        render_settings_page()


if __name__ == "__main__":
    main()
