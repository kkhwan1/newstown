# -*- coding: utf-8 -*-
"""
뉴스 자동화 대시보드
Streamlit 기반 GUI로 뉴스 수집, 업로드 감시, 프롬프트 관리 기능 통합
"""
import streamlit as st
import os
import sys
from pathlib import Path

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
    .keyword-tag { display: inline-block; background: #e8f4fd; color: #0056b3; padding: 2px 8px; border-radius: 4px; margin: 2px; font-size: 0.8rem; }
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


def init_database():
    try:
        from utils.database import init_database as db_init
        db_init()
        return True
    except Exception as e:
        st.error(f"DB 초기화 실패: {e}")
        return False


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

    with st.expander("키워드 설정", expanded=False):
        news_config = cm.get("news_collection")
        keywords = dict(news_config.get('keywords', {"연애": 15, "경제": 15, "스포츠": 15}))
        category_keywords = cm.get("category_keywords", default={})

        cols = st.columns(len(keywords))
        updated = {}
        for idx, (kw, cnt) in enumerate(keywords.items()):
            with cols[idx]:
                updated[kw] = st.number_input(kw, min_value=1, max_value=100, value=cnt, key=f"kw_{kw}")
        
        if updated != keywords:
            cm.set("news_collection", "keywords", updated)

        st.markdown("---")
        
        selected_cat = st.selectbox("세부 키워드 편집", list(keywords.keys()))
        if selected_cat:
            cat_data = category_keywords.get(selected_cat, {"core": [], "general": []})
            
            col1, col2 = st.columns(2)
            with col1:
                core_text = st.text_area(
                    "Core 키워드 (검색용)",
                    value=", ".join(cat_data.get("core", [])),
                    key=f"core_{selected_cat}",
                    height=80
                )
            with col2:
                general_text = st.text_area(
                    "General 키워드 (분류용)",
                    value=", ".join(cat_data.get("general", [])),
                    key=f"general_{selected_cat}",
                    height=80
                )
            
            if st.button("키워드 저장", key="save_kw"):
                new_core = [k.strip() for k in core_text.split(",") if k.strip()]
                new_general = [k.strip() for k in general_text.split(",") if k.strip()]
                cat_data["core"] = list(dict.fromkeys(new_core))
                cat_data["general"] = list(dict.fromkeys(new_general))
                category_keywords[selected_cat] = cat_data
                cm.set_section("category_keywords", category_keywords)
                st.success("저장됨!")


def render_news_page():
    st.title("수집된 뉴스")
    
    try:
        from utils.database import get_news_list, get_news_stats, get_news_count
        
        stats = get_news_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("전체", stats.get('total', 0))
        col2.metric("대기중", stats.get('pending', 0))
        col3.metric("업로드됨", stats.get('uploaded', 0))
        col4.metric("실패", stats.get('failed', 0))

        st.divider()

        col1, col2 = st.columns([1, 3])
        with col1:
            category_filter = st.selectbox("카테고리", ["전체", "연애", "경제", "스포츠"])
        with col2:
            status_filter = st.selectbox("상태", ["전체", "pending", "uploaded", "failed"])

        cat = None if category_filter == "전체" else category_filter
        stat = None if status_filter == "전체" else status_filter
        
        news_list = get_news_list(category=cat, status=stat, limit=20)

        if news_list:
            for news in news_list:
                with st.container():
                    st.markdown(f"""
                    <div class="news-card">
                        <div class="news-title">{news.get('title', '')[:80]}...</div>
                        <div class="news-meta">
                            <span class="keyword-tag">{news.get('category', '미분류')}</span>
                            상태: {news.get('status', 'pending')} | 
                            {news.get('created_at', '')[:16] if news.get('created_at') else ''}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("본문 보기"):
                        st.write(news.get('content', '')[:500] + "..." if len(news.get('content', '')) > 500 else news.get('content', ''))
                        if news.get('link'):
                            st.markdown(f"[원본 링크]({news.get('link')})")
        else:
            st.info("수집된 뉴스가 없습니다. 뉴스 수집을 시작해주세요.")
            
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        st.info("데이터베이스가 아직 초기화되지 않았습니다.")


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
            
            new_prompt = st.text_area(
                "프롬프트 내용",
                height=150,
                placeholder="뉴스 기사를 가공할 프롬프트를 입력하세요.\n\n예: 다음 뉴스 기사를 300자 이내로 요약해주세요. 핵심 내용만 포함하고, 자극적인 표현은 피해주세요."
            )
            
            if st.button("프롬프트 추가", type="primary"):
                if new_name and new_prompt:
                    save_prompt(new_name, new_category, new_prompt)
                    st.success("프롬프트가 추가되었습니다!")
                    st.rerun()
                else:
                    st.warning("이름과 내용을 입력해주세요.")

        st.divider()
        st.subheader("저장된 프롬프트")

        prompts = get_prompts(active_only=False)
        
        if prompts:
            for prompt in prompts:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{prompt['name']}** ({prompt.get('category', '전체')})")
                    with col2:
                        status = "활성" if prompt.get('is_active') else "비활성"
                        st.caption(status)
                    with col3:
                        if st.button("삭제", key=f"del_{prompt['id']}"):
                            delete_prompt(prompt['id'])
                            st.rerun()
                    
                    with st.expander("프롬프트 보기/편집"):
                        edited = st.text_area(
                            "내용",
                            value=prompt.get('prompt_text', ''),
                            key=f"edit_{prompt['id']}",
                            height=120
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("저장", key=f"save_{prompt['id']}"):
                                update_prompt(prompt['id'], prompt_text=edited)
                                st.success("저장됨!")
                        with col2:
                            active = st.checkbox("활성화", value=prompt.get('is_active', True), key=f"active_{prompt['id']}")
                            if active != prompt.get('is_active'):
                                update_prompt(prompt['id'], is_active=active)
        else:
            st.info("저장된 프롬프트가 없습니다. 새 프롬프트를 추가해주세요.")
            
    except Exception as e:
        st.error(f"오류: {e}")


def render_settings_page():
    st.title("설정")
    
    cm = st.session_state.config_manager
    
    st.subheader("구글 시트 연동")
    sheet_url = st.text_input(
        "구글 시트 URL",
        value=cm.get("google_sheet", "url", ""),
        help="뉴스 데이터가 저장될 구글 시트 URL"
    )
    if st.button("URL 저장"):
        cm.set("google_sheet", "url", sheet_url)
        st.success("저장됨!")

    st.divider()
    
    st.subheader("뉴스타운 로그인")
    col1, col2 = st.columns(2)
    with col1:
        site_id = st.text_input("아이디", value=cm.get("newstown", "site_id", ""))
    with col2:
        site_pw = st.text_input("비밀번호", value=cm.get("newstown", "site_pw", ""), type="password")
    
    if st.button("로그인 정보 저장"):
        cm.set("newstown", "site_id", site_id)
        cm.set("newstown", "site_pw", site_pw)
        st.success("저장됨!")

    st.divider()

    st.subheader("네이버 API")
    col1, col2 = st.columns(2)
    with col1:
        client_id = st.text_input("Client ID", value=cm.get("naver_api", "client_id", ""))
    with col2:
        client_secret = st.text_input("Client Secret", value=cm.get("naver_api", "client_secret", ""), type="password")
    
    if st.button("API 정보 저장"):
        cm.set("naver_api", "client_id", client_id)
        cm.set("naver_api", "client_secret", client_secret)
        st.success("저장됨!")

    st.divider()

    st.subheader("업로드/삭제 설정")
    col1, col2 = st.columns(2)
    with col1:
        check_interval = st.number_input(
            "업로드 체크 간격 (초)",
            min_value=10, max_value=600,
            value=cm.get("upload_monitor", "check_interval", 30)
        )
    with col2:
        delete_interval = st.number_input(
            "삭제 간격 (분)",
            min_value=1, max_value=1440,
            value=cm.get("row_deletion", "delete_interval", 60)
        )
    
    if st.button("간격 설정 저장"):
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
            ["대시보드", "뉴스 조회", "프롬프트 관리", "설정"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        pm = st.session_state.process_manager
        if st.button("모든 프로세스 중지", use_container_width=True):
            pm.stop_all()
            st.rerun()

    if page == "대시보드":
        render_main_page()
    elif page == "뉴스 조회":
        render_news_page()
    elif page == "프롬프트 관리":
        render_prompt_page()
    elif page == "설정":
        render_settings_page()


if __name__ == "__main__":
    main()
