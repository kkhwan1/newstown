# -*- coding: utf-8 -*-
"""
뉴스 자동화 대시보드
Streamlit 기반 GUI로 뉴스 수집, 업로드 감시, 완료행 삭제 기능을 통합 관리
"""
import streamlit as st
import os
import sys
from pathlib import Path

# 현재 디렉토리를 path에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from utils.process_manager import ProcessManager
from utils.config_manager import ConfigManager

def get_category_keywords(cm):
    """config에서 카테고리 키워드 가져오기"""
    return cm.get("category_keywords", default={})

# 페이지 설정
st.set_page_config(
    page_title="뉴스 자동화 대시보드",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Apple 스타일 CSS
st.markdown("""
<style>
    /* 전체 배경 및 기본 스타일 */
    .main {
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    .stApp {
        background-color: #ffffff;
    }

    /* 메인 헤더 */
    .main-header {
        font-size: 2rem;
        font-weight: 600;
        color: #1d1d1f;
        letter-spacing: -0.02em;
        padding: 0.5rem 0 1.5rem 0;
    }

    /* 상태 테이블 */
    .status-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0 2rem 0;
        background: #ffffff;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    .status-table th {
        background: #f5f5f7;
        color: #1d1d1f;
        font-weight: 500;
        font-size: 0.85rem;
        padding: 12px 16px;
        text-align: left;
        border-bottom: 1px solid #e5e5e5;
    }

    .status-table td {
        padding: 14px 16px;
        color: #1d1d1f;
        font-size: 0.9rem;
        border-bottom: 1px solid #f0f0f0;
    }

    .status-table tr:last-child td {
        border-bottom: none;
    }

    .status-running {
        color: #34c759;
        font-weight: 500;
    }

    .status-stopped {
        color: #ff3b30;
        font-weight: 500;
    }

    /* 섹션 제목 */
    .section-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1d1d1f;
        margin: 1.5rem 0 1rem 0;
        letter-spacing: -0.01em;
    }

    .section-subtitle {
        font-size: 1rem;
        font-weight: 500;
        color: #1d1d1f;
        margin: 1rem 0 0.5rem 0;
    }

    /* 키워드 테이블 */
    .keyword-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0.5rem 0;
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 8px;
        overflow: hidden;
    }

    .keyword-table th {
        background: #f5f5f7;
        color: #1d1d1f;
        font-weight: 500;
        font-size: 0.8rem;
        padding: 10px 14px;
        text-align: left;
    }

    .keyword-table td {
        padding: 10px 14px;
        color: #1d1d1f;
        font-size: 0.85rem;
        border-top: 1px solid #f0f0f0;
    }

    /* 버튼 스타일 */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }

    .stButton > button[kind="primary"] {
        background-color: #007aff;
        border: none;
        color: white;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: #0056b3;
    }

    .stButton > button[kind="secondary"] {
        background-color: #f5f5f7;
        border: 1px solid #d1d1d6;
        color: #1d1d1f;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #f5f5f7;
        border-radius: 8px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        font-weight: 500;
        color: #1d1d1f;
        border-radius: 6px;
        font-size: 0.9rem;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    /* 입력 필드 */
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        border: 1px solid #d1d1d6;
        border-radius: 8px;
        font-size: 0.9rem;
        color: #1d1d1f;
    }

    .stNumberInput > div > div > input:focus,
    .stTextInput > div > div > input:focus {
        border-color: #007aff;
        box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
    }

    /* 알림 박스 */
    .info-box {
        background: #f5f5f7;
        border-radius: 8px;
        padding: 12px 16px;
        color: #1d1d1f;
        font-size: 0.85rem;
        margin: 0.5rem 0;
    }

    .success-box {
        background: #f0fff4;
        border: 1px solid #c6f6d5;
        border-radius: 8px;
        padding: 12px 16px;
        color: #1d1d1f;
        font-size: 0.85rem;
        margin: 1rem 0;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 500;
        font-size: 0.95rem;
        color: #1d1d1f;
        background: #f5f5f7;
        border-radius: 8px;
    }

    /* 구분선 */
    hr {
        border: none;
        border-top: 1px solid #e5e5e5;
        margin: 1.5rem 0;
    }

    /* 키워드 개요 */
    .keyword-overview {
        background: #f5f5f7;
        border-radius: 10px;
        padding: 14px 18px;
        margin: 0 0 1.5rem 0;
    }

    .keyword-label {
        font-size: 0.9rem;
        font-weight: 500;
        color: #6e6e73;
        margin-bottom: 10px;
        display: block;
    }

    .keyword-categories {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .keyword-category {
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        overflow: hidden;
    }

    .keyword-category-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: #ffffff;
        cursor: pointer;
        transition: background 0.2s;
    }

    .keyword-category-header:hover {
        background: #fafafa;
    }

    .keyword-category-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1d1d1f;
    }

    .keyword-category-count {
        font-size: 0.8rem;
        font-weight: 500;
        color: #007aff;
        background: #e8f4fd;
        padding: 4px 10px;
        border-radius: 12px;
    }

    .keyword-subcategory {
        padding: 12px 16px;
        border-top: 1px solid #f0f0f0;
        background: #fafafa;
    }

    .keyword-subcategory-inline {
        margin-bottom: 16px;
    }

    .keyword-subcategory-title {
        font-size: 0.75rem;
        font-weight: 500;
        color: #6e6e73;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .keyword-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }

    .keyword-tag {
        background: #ffffff;
        border: 1px solid #d1d1d6;
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 0.75rem;
        color: #1d1d1f;
    }

    .keyword-tag-core {
        background: #e8f4fd;
        border-color: #b3d4fc;
        color: #0056b3;
    }

    .keyword-pill {
        background: #ffffff;
        border: 1px solid #d1d1d6;
        border-radius: 16px;
        padding: 6px 14px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #1d1d1f;
    }

    /* details/summary 스타일 */
    details.keyword-category {
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        overflow: hidden;
    }

    details.keyword-category > summary {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: #ffffff;
        cursor: pointer;
        list-style: none;
        transition: background 0.2s;
    }

    details.keyword-category > summary::-webkit-details-marker {
        display: none;
    }

    details.keyword-category > summary::before {
        content: '+';
        margin-right: 10px;
        font-weight: 600;
        color: #007aff;
        font-size: 1.1rem;
    }

    details.keyword-category[open] > summary::before {
        content: '-';
    }

    details.keyword-category > summary:hover {
        background: #fafafa;
    }

    details.keyword-category[open] > summary {
        border-bottom: 1px solid #f0f0f0;
    }

    /* 사이드바 */
    .css-1d391kg {
        background: #f5f5f7;
    }

    /* selectbox */
    .stSelectbox > div > div {
        border: 1px solid #d1d1d6;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 스크립트 경로
SCRIPTS_DIR = current_dir / "scripts"
NEWS_SCRIPT = SCRIPTS_DIR / "run_news_collection.py"
UPLOAD_SCRIPT = SCRIPTS_DIR / "run_upload_monitor.py"
DELETION_SCRIPT = SCRIPTS_DIR / "run_row_deletion.py"

# 프로세스 이름
PROC_NEWS = "news_collection"
PROC_UPLOAD = "upload_monitor"
PROC_DELETION = "row_deletion"


def init_session_state():
    """세션 상태 초기화"""
    if 'process_manager' not in st.session_state:
        st.session_state.process_manager = ProcessManager()
    if 'config_manager' not in st.session_state:
        st.session_state.config_manager = ConfigManager()


def render_status_overview():
    """상단 상태 개요 표시 - 테이블 형식"""
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown('<div class="main-header">뉴스 자동화 대시보드</div>', unsafe_allow_html=True)

    # 상태 데이터 수집
    news_status = pm.get_status(PROC_NEWS)
    upload_status = pm.get_status(PROC_UPLOAD)
    deletion_status = pm.get_status(PROC_DELETION)

    def get_status_html(running):
        if running:
            return '<span class="status-running">실행중</span>'
        return '<span class="status-stopped">중지됨</span>'

    # 상태 테이블 HTML
    st.markdown(f"""
    <table class="status-table">
        <thead>
            <tr>
                <th>기능</th>
                <th>상태</th>
                <th>실행 시간</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>뉴스 수집</td>
                <td>{get_status_html(news_status['running'])}</td>
                <td>{news_status['runtime'] or '-'}</td>
            </tr>
            <tr>
                <td>업로드 감시</td>
                <td>{get_status_html(upload_status['running'])}</td>
                <td>{upload_status['runtime'] or '-'}</td>
            </tr>
            <tr>
                <td>완료행 삭제</td>
                <td>{get_status_html(deletion_status['running'])}</td>
                <td>{deletion_status['runtime'] or '-'}</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # 등록된 키워드 표시 (세부 키워드 포함)
    news_config = cm.get("news_collection")
    keywords = news_config.get('keywords', {"연애": 15, "경제": 15, "스포츠": 15})
    category_keywords = get_category_keywords(cm)

    st.markdown('<div class="keyword-overview"><span class="keyword-label">등록된 키워드:</span></div>', unsafe_allow_html=True)

    # 각 카테고리별 확장 가능한 섹션 표시
    for kw, cnt in keywords.items():
        if kw in category_keywords:
            cat_info = category_keywords[kw]
            core_keywords = cat_info.get("core", [])
            general_keywords = cat_info.get("general", [])
            total_count = len(core_keywords) + len(general_keywords)

            with st.expander(f"{kw} ({cnt}개 수집) - 세부 키워드 {total_count}개", expanded=False):
                # 핵심 키워드
                core_tags = " ".join([f'<span class="keyword-tag keyword-tag-core">{k}</span>' for k in core_keywords])
                st.markdown(f'''
                <div class="keyword-subcategory-inline">
                    <div class="keyword-subcategory-title">핵심 ({len(core_keywords)})</div>
                    <div class="keyword-tags">{core_tags}</div>
                </div>
                ''', unsafe_allow_html=True)

                # 일반 키워드
                general_tags = " ".join([f'<span class="keyword-tag">{k}</span>' for k in general_keywords])
                st.markdown(f'''
                <div class="keyword-subcategory-inline">
                    <div class="keyword-subcategory-title">일반 ({len(general_keywords)})</div>
                    <div class="keyword-tags">{general_tags}</div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            # category_keywords에 없는 키워드는 기본 pill로 표시
            st.markdown(f'<span class="keyword-pill">{kw} ({cnt})</span>', unsafe_allow_html=True)


def render_news_collection_tab():
    """뉴스 수집 탭"""
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown('<div class="section-title">뉴스 수집</div>', unsafe_allow_html=True)

    status = pm.get_status(PROC_NEWS)
    is_running = status['running']

    # 설정
    with st.expander("설정", expanded=not is_running):
        news_config = cm.get("news_collection")
        keywords = dict(news_config.get('keywords', {"연애": 15, "경제": 15, "스포츠": 15}))

        # 현재 키워드 테이블
        st.markdown('<div class="section-subtitle">현재 키워드 설정</div>', unsafe_allow_html=True)

        keyword_rows = ""
        for kw, cnt in keywords.items():
            keyword_rows += f"<tr><td>{kw}</td><td>{cnt}개</td></tr>"

        st.markdown(f"""
        <table class="keyword-table">
            <thead>
                <tr><th>키워드</th><th>수집 개수</th></tr>
            </thead>
            <tbody>{keyword_rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

        # 키워드별 수집 개수 수정
        st.markdown('<div class="section-subtitle">키워드별 수집 개수 수정</div>', unsafe_allow_html=True)

        updated_keywords = {}
        need_save = False

        if keywords:
            cols = st.columns(min(len(keywords), 3))
            for idx, (keyword, count) in enumerate(keywords.items()):
                with cols[idx % len(cols)]:
                    new_count = st.number_input(
                        keyword,
                        min_value=1,
                        max_value=100,
                        value=count,
                        key=f"keyword_{keyword}",
                        disabled=is_running
                    )
                    updated_keywords[keyword] = new_count
                    if new_count != count:
                        need_save = True

        # 수정된 내용 자동 저장
        if need_save and not is_running:
            cm.set("news_collection", "keywords", updated_keywords)
            st.markdown('<div class="info-box">설정이 자동 저장되었습니다.</div>', unsafe_allow_html=True)

        # 새 키워드 추가
        st.markdown("---")
        st.markdown('<div class="section-subtitle">새 키워드 추가</div>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            new_keyword = st.text_input("키워드 이름", key="new_keyword", disabled=is_running, placeholder="예: 경제")
        with col2:
            new_keyword_count = st.number_input("수집 개수", min_value=1, max_value=100, value=15, key="new_keyword_count", disabled=is_running)
        with col3:
            st.write("")
            if st.button("추가", disabled=is_running or not new_keyword, use_container_width=True):
                if new_keyword and new_keyword.strip():
                    new_kw = new_keyword.strip()
                    if new_kw not in keywords:
                        keywords[new_kw] = new_keyword_count
                        cm.set("news_collection", "keywords", keywords)
                        # 새 카테고리에 대한 빈 키워드 목록 생성
                        category_keywords = cm.get("category_keywords", default={})
                        if new_kw not in category_keywords:
                            category_keywords[new_kw] = {"core": [], "general": []}
                            cm.set_section("category_keywords", category_keywords)
                        st.rerun()

        # 키워드 삭제
        if len(keywords) > 1:
            st.markdown('<div class="section-subtitle">키워드 삭제</div>', unsafe_allow_html=True)
            col1, col2 = st.columns([3, 1])
            with col1:
                keyword_to_delete = st.selectbox(
                    "삭제할 키워드 선택",
                    options=["선택하세요"] + list(keywords.keys()),
                    key="delete_keyword",
                    disabled=is_running
                )
            with col2:
                st.write("")
                if st.button("삭제", disabled=is_running or keyword_to_delete == "선택하세요", use_container_width=True):
                    if keyword_to_delete != "선택하세요" and keyword_to_delete in keywords:
                        del keywords[keyword_to_delete]
                        cm.set("news_collection", "keywords", keywords)
                        # 카테고리 키워드도 함께 삭제
                        category_keywords = cm.get("category_keywords", default={})
                        if keyword_to_delete in category_keywords:
                            del category_keywords[keyword_to_delete]
                            cm.set_section("category_keywords", category_keywords)
                        st.rerun()

        # 카테고리별 세부 키워드 수정
        st.markdown("---")
        st.markdown('<div class="section-subtitle">카테고리별 세부 키워드 수정</div>', unsafe_allow_html=True)
        st.caption("각 카테고리의 core(핵심) 및 general(일반) 키워드를 개별적으로 수정할 수 있습니다.")

        category_keywords = get_category_keywords(cm)

        for category in keywords.keys():
            with st.expander(f"{category} 세부 키워드", expanded=False):
                cat_data = category_keywords.get(category, {"core": [], "general": []})
                core_kws = list(cat_data.get("core", []))
                general_kws = list(cat_data.get("general", []))

                # Core 키워드 섹션
                st.markdown("**Core 키워드** (핵심 검색어)")
                if core_kws:
                    # 키워드 태그로 표시
                    core_tags = " ".join([f'<span class="keyword-pill">{kw}</span>' for kw in core_kws])
                    st.markdown(f'<div style="margin-bottom: 10px;">{core_tags}</div>', unsafe_allow_html=True)

                    # Core 키워드 삭제
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        core_to_delete = st.selectbox(
                            "삭제할 Core 키워드",
                            options=["선택하세요"] + core_kws,
                            key=f"del_core_{category}",
                            disabled=is_running
                        )
                    with col2:
                        st.write("")
                        if st.button("삭제", key=f"btn_del_core_{category}", disabled=is_running or core_to_delete == "선택하세요"):
                            if core_to_delete != "선택하세요" and core_to_delete in core_kws:
                                core_kws.remove(core_to_delete)
                                cat_data["core"] = core_kws
                                category_keywords[category] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()
                else:
                    st.info("Core 키워드가 없습니다.")

                # Core 키워드 추가
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_core = st.text_input("새 Core 키워드", key=f"new_core_{category}", disabled=is_running, placeholder="예: 연애")
                with col2:
                    st.write("")
                    if st.button("추가", key=f"btn_add_core_{category}", disabled=is_running or not new_core):
                        if new_core and new_core.strip():
                            new_kw = new_core.strip()
                            if new_kw not in core_kws:
                                core_kws.append(new_kw)
                                cat_data["core"] = core_kws
                                category_keywords[category] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()

                st.markdown("---")

                # General 키워드 섹션
                st.markdown("**General 키워드** (일반 검색어)")
                if general_kws:
                    # 키워드 태그로 표시
                    general_tags = " ".join([f'<span class="keyword-pill">{kw}</span>' for kw in general_kws])
                    st.markdown(f'<div style="margin-bottom: 10px;">{general_tags}</div>', unsafe_allow_html=True)

                    # General 키워드 삭제
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        general_to_delete = st.selectbox(
                            "삭제할 General 키워드",
                            options=["선택하세요"] + general_kws,
                            key=f"del_general_{category}",
                            disabled=is_running
                        )
                    with col2:
                        st.write("")
                        if st.button("삭제", key=f"btn_del_general_{category}", disabled=is_running or general_to_delete == "선택하세요"):
                            if general_to_delete != "선택하세요" and general_to_delete in general_kws:
                                general_kws.remove(general_to_delete)
                                cat_data["general"] = general_kws
                                category_keywords[category] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()
                else:
                    st.info("General 키워드가 없습니다.")

                # General 키워드 추가
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_general = st.text_input("새 General 키워드", key=f"new_general_{category}", disabled=is_running, placeholder="예: 신랑")
                with col2:
                    st.write("")
                    if st.button("추가", key=f"btn_add_general_{category}", disabled=is_running or not new_general):
                        if new_general and new_general.strip():
                            new_kw = new_general.strip()
                            if new_kw not in general_kws:
                                general_kws.append(new_kw)
                                cat_data["general"] = general_kws
                                category_keywords[category] = cat_data
                                cm.set_section("category_keywords", category_keywords)
                                st.rerun()

    # 제어
    st.markdown('<div class="section-subtitle">제어</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        if is_running:
            if st.button("중지", key="stop_news", type="secondary", use_container_width=True):
                pm.stop_process(PROC_NEWS)
                st.rerun()
        else:
            if st.button("시작", key="start_news", type="primary", use_container_width=True):
                # 최신 설정을 다시 로드하여 사용
                config = cm.get_news_config()
                pm.start_process(PROC_NEWS, str(NEWS_SCRIPT), config)
                st.rerun()

    with col2:
        if is_running and status['runtime']:
            st.markdown(f'<div class="info-box">실행 시간: {status["runtime"]}</div>', unsafe_allow_html=True)


def render_upload_monitor_tab():
    """업로드 감시 탭"""
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown('<div class="section-title">업로드 감시</div>', unsafe_allow_html=True)

    status = pm.get_status(PROC_UPLOAD)
    is_running = status['running']

    with st.expander("설정", expanded=not is_running):
        upload_config = cm.get("upload_monitor")

        check_interval = st.number_input(
            "체크 간격 (초)",
            min_value=10,
            max_value=600,
            value=upload_config.get('check_interval', 30),
            step=10,
            key="check_interval",
            disabled=is_running,
            help="구글 시트를 확인하는 간격"
        )

        if not is_running:
            if st.button("설정 저장", key="save_upload", type="secondary"):
                cm.set("upload_monitor", "check_interval", check_interval)
                st.success("설정이 저장되었습니다.")

    st.markdown('<div class="section-subtitle">제어</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        if is_running:
            if st.button("중지", key="stop_upload", type="secondary", use_container_width=True):
                pm.stop_process(PROC_UPLOAD)
                st.rerun()
        else:
            if st.button("시작", key="start_upload", type="primary", use_container_width=True):
                config = cm.get_upload_config()
                config['check_interval'] = check_interval
                pm.start_process(PROC_UPLOAD, str(UPLOAD_SCRIPT), config)
                st.rerun()

    with col2:
        if is_running and status['runtime']:
            st.markdown(f'<div class="info-box">실행 시간: {status["runtime"]}</div>', unsafe_allow_html=True)

    if is_running:
        st.markdown('<div class="success-box">E열/F열 데이터가 채워지면 자동으로 뉴스타운에 업로드합니다.</div>', unsafe_allow_html=True)


def render_row_deletion_tab():
    """완료행 삭제 탭"""
    pm = st.session_state.process_manager
    cm = st.session_state.config_manager

    st.markdown('<div class="section-title">완료행 삭제</div>', unsafe_allow_html=True)

    status = pm.get_status(PROC_DELETION)
    is_running = status['running']

    with st.expander("설정", expanded=not is_running):
        deletion_config = cm.get("row_deletion")

        col1, col2 = st.columns(2)
        with col1:
            delete_interval = st.number_input(
                "삭제 간격 (분)",
                min_value=1,
                max_value=1440,
                value=deletion_config.get('delete_interval', 60),
                step=10,
                key="delete_interval",
                disabled=is_running,
                help="완료된 행을 삭제하는 간격"
            )

        with col2:
            max_delete_count = st.number_input(
                "최대 삭제 개수",
                min_value=1,
                max_value=100,
                value=deletion_config.get('max_delete_count', 10),
                step=5,
                key="max_delete_count",
                disabled=is_running,
                help="한 번에 삭제할 최대 행 수"
            )

        if not is_running:
            if st.button("설정 저장", key="save_deletion", type="secondary"):
                cm.set("row_deletion", "delete_interval", delete_interval, save=False)
                cm.set("row_deletion", "max_delete_count", max_delete_count)
                st.success("설정이 저장되었습니다.")

    st.markdown('<div class="section-subtitle">제어</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        if is_running:
            if st.button("중지", key="stop_deletion", type="secondary", use_container_width=True):
                pm.stop_process(PROC_DELETION)
                st.rerun()
        else:
            if st.button("시작", key="start_deletion", type="primary", use_container_width=True):
                config = cm.get_deletion_config()
                config['delete_interval'] = delete_interval
                config['max_delete_count'] = max_delete_count
                pm.start_process(PROC_DELETION, str(DELETION_SCRIPT), config)
                st.rerun()

    with col2:
        if is_running and status['runtime']:
            st.markdown(f'<div class="info-box">실행 시간: {status["runtime"]}</div>', unsafe_allow_html=True)

    if is_running:
        st.markdown(f'<div class="success-box">H열에 "완료" 표시된 행을 {delete_interval}분마다 자동으로 삭제합니다.</div>', unsafe_allow_html=True)


def render_sidebar():
    """사이드바"""
    with st.sidebar:
        st.markdown("### 전역 설정")

        cm = st.session_state.config_manager

        sheet_url = st.text_input(
            "구글 시트 URL",
            value=cm.get("google_sheet", "url", ""),
            key="sheet_url"
        )

        if st.button("URL 저장"):
            cm.set("google_sheet", "url", sheet_url)
            st.success("저장됨")

        st.divider()

        pm = st.session_state.process_manager
        if st.button("모든 프로세스 중지", type="secondary", use_container_width=True):
            pm.stop_all()
            st.rerun()

        st.divider()

        auto_refresh = st.checkbox("자동 새로고침 (5초)", value=False, key="auto_refresh")
        if auto_refresh:
            st.rerun()

        st.divider()

        st.markdown("### 기능 안내")
        st.markdown("""
        **뉴스 수집**: 네이버 뉴스를 검색하여 구글 시트에 저장

        **업로드 감시**: E/F열 데이터를 감시하여 뉴스타운에 업로드

        **완료행 삭제**: H열 '완료' 표시된 행을 자동 삭제
        """)


def main():
    """메인 함수"""
    init_session_state()
    render_status_overview()
    render_sidebar()

    tab1, tab2, tab3 = st.tabs(["뉴스 수집", "업로드 감시", "완료행 삭제"])

    with tab1:
        render_news_collection_tab()

    with tab2:
        render_upload_monitor_tab()

    with tab3:
        render_row_deletion_tab()


if __name__ == "__main__":
    main()
