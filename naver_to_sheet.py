# -*- coding: utf-8 -*-

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import urllib.request
import urllib.parse
import json
import time
import sys
import io
import requests
from bs4 import BeautifulSoup
import re
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime, timezone
from difflib import SequenceMatcher
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Windows 콘솔에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==========================================
# [CONFIG] 설정 구역
# ==========================================
# 1. 네이버 API 설정
NAVER_CLIENT_ID = "hj620p2ZnD94LNjNaW8d"
NAVER_CLIENT_SECRET = "sDRT5fUUaK"

# 2. 구글 시트 설정
SHEET_URL = "https://docs.google.com/spreadsheets/d/1H0aj-bN63LMMFcinfe51J-gwewzxIyzFOkqSA5POHkk/edit"

# 3. 검색어 설정 (연애 30개, 스포츠 40개, 경제 30개 - 총 100개)
# 일반적인 키워드로 최신순 뉴스 수집
KEYWORDS = {
    # 연애 관련 (일반 키워드로 최신 뉴스 수집)
    "연애": 8,
    "연예": 8,
    "커플": 5,
    "결혼": 5,
    "데이트": 4,

    # 스포츠 관련 (일반 키워드로 최신 뉴스 수집)
    "스포츠": 20,
    "야구": 10,
    "축구": 10,
    "농구": 5,
    "손흥민": 5,
    "이강인": 5,
    "K리그": 5,
    "프로야구": 5,

    # 경제 관련 (ENABLE_ECONOMY_CATEGORY=True 시 사용)
    "주식": 8,
    "부동산": 6,
    "금리": 5,
    "환율": 4,
    "경제": 5,
    "금융": 4,
    "투자": 4,
    "코스피": 4,
}

# 검색어별 목표 카테고리 매핑
KEYWORD_CATEGORY_MAP = {
    # 연애 매핑
    "연애": "연애",
    "연예": "연애",
    "커플": "연애",
    "결혼": "연애",
    "데이트": "연애",
    # 스포츠 매핑
    "스포츠": "스포츠",
    "야구": "스포츠",
    "축구": "스포츠",
    "농구": "스포츠",
    "손흥민": "스포츠",
    "이강인": "스포츠",
    "K리그": "스포츠",
    "프로야구": "스포츠",
    # 경제 매핑
    "주식": "경제",
    "부동산": "경제",
    "금리": "경제",
    "환율": "경제",
    "경제": "경제",
    "금융": "경제",
    "투자": "경제",
    "코스피": "경제",
}

# 4. 업로드 순서: 랜덤으로 섞어서 업로드
# (패턴 없이 완전 랜덤)

# 4. 검색 옵션
DISPLAY_COUNT = 70  # 총 70개 (연애 30개, 스포츠 40개)

# 5. 카테고리 필터 설정 (None이면 모든 뉴스 수집 후 자동 분류)
CATEGORY = None  # "연애", "경제", "스포츠" 등 (None이면 필터링 안 함)

# 6. 뉴스타운 업로드 설정
SITE_ID = "kim123"
SITE_PW = "love1105()"
AUTO_UPLOAD_TO_NEWSTOWN = False  # False면 구글 시트에만 저장 (뉴스타운 업로드 안 함)

# 7. 카테고리 불일치 정책
SKIP_MISMATCHED_CATEGORY = True  # True: 카테고리 불일치 시 저장 건너뛰기
                                  # False: 경고만 출력하고 저장 (기존 동작)

# 8. 경제 카테고리 활성화
ENABLE_ECONOMY_CATEGORY = True   # True: 경제 뉴스도 수집
                                  # False: 연애/스포츠만 수집 (기존 동작)

# ==========================================

def get_naver_news(keyword, display=20, sort='date'):
    """네이버 뉴스 검색 함수
    
    Args:
        keyword: 검색어
        display: 가져올 개수
        sort: 정렬 방식 ('date'=최신순, 'sim'=정확도순/검색량 높은 순)
    """
    encText = urllib.parse.quote(keyword)
    # 검색어, 출력 개수(display=10~100), 정렬(sim=정확도순/검색량 높은 순, date=날짜순/최신순)
    url = f"https://openapi.naver.com/v1/search/news?query={encText}&display={display}&sort={sort}"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        
        if(rescode == 200):
            response_body = response.read()
            return json.loads(response_body.decode('utf-8'))
        else:
            print(f"[ERROR] Error Code: {rescode}")
            return None
    except Exception as e:
        print(f"[ERROR] 네이버 API 요청 실패: {e}")
        return None

def clean_element(element):
    """요소에서 불필요한 부분을 제거하는 함수"""
    if not element:
        return
    
    # 불필요한 요소 제거
    for tag in element.find_all(['script', 'style', 'button', 'nav', 'aside', 'footer', 'header', 
                                  'form', 'input', 'select', 'textarea', 'iframe', 'embed', 'menu',
                                  'noscript', 'svg', 'canvas', 'object', 'applet']):
        tag.decompose()
    
    # 댓글 영역 제거
    for comment_area in element.find_all(['div', 'section'], 
                                         class_=re.compile(r'comment|reply|댓글|reply-box|comment-box', re.I)):
        comment_area.decompose()
    
    # 공유 버튼 등 제거
    for share_btn in element.find_all(['div', 'span', 'a'], 
                                      class_=re.compile(r'share|공유|sns|social|facebook|twitter|kakao', re.I)):
        share_btn.decompose()
    
    # 메뉴/네비게이션 영역 제거
    for nav_area in element.find_all(['div', 'ul', 'li', 'section'], 
                                     class_=re.compile(r'nav|menu|navigation|gnb|lnb|메뉴|네비|구독|rss|속보|sidebar', re.I)):
        nav_area.decompose()
    
    # 광고 영역 제거
    for ad_area in element.find_all(['div', 'section'], 
                                    class_=re.compile(r'ad|advertisement|광고|sponsor|promotion', re.I)):
        ad_area.decompose()
    
    # 구독 관련 제거
    for sub_area in element.find_all(['div', 'span', 'a'], 
                                     string=re.compile(r'구독|RSS|신문|PDF|subscribe', re.I)):
        if sub_area.parent:
            sub_area.parent.decompose()
    
    # 관련뉴스, 최신뉴스, 주요뉴스 섹션 제거
    for news_section in element.find_all(['div', 'section', 'ul', 'ol'], 
                                         class_=re.compile(r'related|latest|popular|news.*list|관련|최신|주요', re.I)):
        news_section.decompose()
    
    # "관련뉴스", "최신뉴스" 등의 제목이 있는 섹션 제거
    for title in element.find_all(['h2', 'h3', 'h4', 'div', 'span'], 
                                  string=re.compile(r'^관련뉴스$|^최신뉴스$|^주요뉴스$|^최신포토$', re.I)):
        if title.parent:
            title.parent.decompose()
    
    # AI 메시지나 시스템 메시지 제거
    for ai_msg in element.find_all(['div', 'span', 'p'], 
                                   string=re.compile(r'본문의 검색 링크|AI 자동 인식|오분류 제보', re.I)):
        if ai_msg.parent:
            ai_msg.parent.decompose()
    
    # 언론사 정보 섹션 제거
    for press_info in element.find_all(['div', 'section'], 
                                      class_=re.compile(r'press|publisher|언론사|기자정보', re.I)):
        press_info.decompose()

def extract_text_quality(text):
    """텍스트 품질 점수 계산 (한글 비율, 길이 등)"""
    if not text or len(text) < 50:
        return 0
    
    # 한글 비율 계산
    korean_chars = len(re.findall(r'[가-힣]', text))
    total_chars = len(re.findall(r'[가-힣a-zA-Z0-9]', text))
    korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
    
    # 문장 수 계산
    sentences = len(re.findall(r'[.!?。！？]\s*', text))
    
    # 점수 계산 (한글 비율 40%, 길이 40%, 문장 수 20%)
    length_score = min(len(text) / 2000, 1.0) * 0.4
    korean_score = min(korean_ratio * 2, 1.0) * 0.4
    sentence_score = min(sentences / 10, 1.0) * 0.2
    
    return length_score + korean_score + sentence_score

def scrape_news_content(url):
    """뉴스 링크에서 본문 내용을 스크래핑하는 함수 (개선된 버전)"""
    try:
        # User-Agent 설정 (봇 차단 방지)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 요청 타임아웃 설정 (속도 개선: 15초 -> 5초)
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        
        # 인코딩 자동 감지
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        if response.status_code != 200:
            print(f"   [WARN] HTTP {response.status_code} 오류")
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 여러 방법으로 본문 추출 시도 (품질 점수와 함께 저장)
        candidates = []
        
        # 방법 1: 네이버 뉴스 본문 (다양한 선택자 시도)
        naver_selectors = [
            {'id': 'articleBodyContents'},
            {'class': '_article_body_contents'},
            {'id': re.compile(r'articleBody', re.I)},
            {'class': re.compile(r'article.*body|body.*article', re.I)},
            {'id': re.compile(r'newsEndBody|articleBody|article_body', re.I)},
        ]
        
        for selector in naver_selectors:
            element = soup.find('div', selector)
            if element:
                clean_element(element)
                text = element.get_text(separator='\n', strip=True)
                if text and len(text) > 100:
                    quality = extract_text_quality(text)
                    candidates.append((text, quality, '네이버뉴스'))
                    break
        
        # 방법 2: <article> 태그
        article = soup.find('article')
        if article:
            clean_element(article)
            text = article.get_text(separator='\n', strip=True)
            if text and len(text) > 100:
                quality = extract_text_quality(text)
                candidates.append((text, quality, 'article태그'))
        
        # 방법 3: <main> 태그
        main = soup.find('main')
        if main:
            clean_element(main)
            text = main.get_text(separator='\n', strip=True)
            if text and len(text) > 100:
                quality = extract_text_quality(text)
                candidates.append((text, quality, 'main태그'))
        
        # 방법 4: 본문 관련 클래스/ID (확장된 선택자)
        content_selectors = [
            {'id': re.compile(r'article.*content|content.*article|article.*body|body.*article', re.I)},
            {'class': re.compile(r'article.*content|content.*article|article.*body|body.*article', re.I)},
            {'id': re.compile(r'news.*body|body.*news|story.*body|body.*story', re.I)},
            {'class': re.compile(r'news.*body|body.*news|story.*body|body.*story', re.I)},
            {'id': 'article_content'},
            {'class': 'article-content'},
            {'class': 'article_body'},
            {'class': 'article-body'},
            {'id': 'content'},
            {'class': 'content'},
            {'id': 'article'},
            {'class': 'article'},
            {'id': re.compile(r'^article$|^content$|^body$', re.I)},
            {'class': re.compile(r'^article$|^content$|^body$', re.I)},
        ]
        
        for selector in content_selectors:
            elements = soup.find_all('div', selector)
            for element in elements:
                clean_element(element)
                text = element.get_text(separator='\n', strip=True)
                if text and len(text) > 200:  # 충분한 길이
                    quality = extract_text_quality(text)
                    candidates.append((text, quality, 'div선택자'))
                    break
            if candidates and any(c[2] == 'div선택자' for c in candidates):
                break
        
        # 방법 5: <section> 태그 중 본문으로 보이는 것
        sections = soup.find_all('section')
        for section in sections:
            # 본문 관련 클래스/ID가 있는 section만
            if section.get('class') and any(re.search(r'article|content|body|story|news', str(c), re.I) 
                                             for c in section.get('class', [])):
                clean_element(section)
                text = section.get_text(separator='\n', strip=True)
                if text and len(text) > 200:
                    quality = extract_text_quality(text)
                    candidates.append((text, quality, 'section태그'))
        
        # 방법 6: <p> 태그들을 모아서 본문으로 사용 (긴 문단만)
        paragraphs = soup.find_all('p')
        if paragraphs:
            content_parts = []
            for p in paragraphs:
                # 부모가 article, main, content 관련이면 우선
                parent = p.parent
                is_in_content = False
                if parent:
                    parent_class = ' '.join(parent.get('class', []))
                    parent_id = parent.get('id', '')
                    if re.search(r'article|content|body|story|news', parent_class + parent_id, re.I):
                        is_in_content = True
                
                text = p.get_text(strip=True)
                # 본문에 포함된 p 태그이거나, 충분히 긴 문단
                if text and (len(text) > 50 or (is_in_content and len(text) > 20)):
                    content_parts.append(text)
            
            if len(content_parts) >= 3:  # 최소 3개 문단
                text = '\n\n'.join(content_parts)
                if len(text) > 200:
                    quality = extract_text_quality(text)
                    candidates.append((text, quality, 'p태그모음'))
        
        # 방법 7: 모든 div 중에서 가장 긴 텍스트를 가진 것 (최후의 수단)
        if not candidates or max([c[1] for c in candidates], default=0) < 0.3:
            all_divs = soup.find_all('div')
            best_div = None
            best_length = 0
            
            for div in all_divs:
                # 불필요한 클래스/ID 제외
                div_class = ' '.join(div.get('class', []))
                div_id = div.get('id', '')
                if re.search(r'header|footer|nav|menu|sidebar|comment|ad|광고', div_class + div_id, re.I):
                    continue
                
                clean_element(div)
                text = div.get_text(separator='\n', strip=True)
                if len(text) > best_length and len(text) > 300:
                    # 한글 비율 확인
                    korean_chars = len(re.findall(r'[가-힣]', text))
                    if korean_chars > 100:  # 최소 100자 이상 한글
                        best_div = div
                        best_length = len(text)
            
            if best_div:
                text = best_div.get_text(separator='\n', strip=True)
                quality = extract_text_quality(text)
                candidates.append((text, quality, '최장div'))
        
        # 후보 중 가장 품질이 좋은 본문 선택
        if candidates:
            # 품질 점수로 정렬
            candidates.sort(key=lambda x: x[1], reverse=True)
            content = candidates[0][0]
        else:
            content = None
        
        # 본문 정리
        if content:
            # 불필요한 UI 요소 및 텍스트 제거
            unwanted_patterns = [
                # UI 요소
                r'래도 삭제하시겠습니까\?',
                r'^비밀번호$',
                r'^삭제$',
                r'^닫기$',
                r'댓글수정',
                r'댓글 수정은 작성 후 \d+분내에만 가능합니다\.',
                r'본문\s*/\s*\d+',
                r'^수정$',
                r'공유하기',
                r'좋아요',
                r'댓글\s*\d*',
                r'조회수',
                # 뉴스 섹션 제목
                r'^관련뉴스$',
                r'^최신뉴스$',
                r'^주요뉴스$',
                r'^최신포토$',
                r'^Editer.*Pick$',
                r'^News Ranking$',
                r'^Latest$',
                r'^Popular$',
                r'^Related$',
                r'^comments$',
                # AI/시스템 메시지
                r'본문의 검색 링크는.*',
                r'AI 자동 인식.*',
                r'오분류 제보하기',
                r'일부에 대해서는.*',
                r'동일한 명칭이 다수 존재.*',
                # 언론사/기자 정보
                r'언론사홈 바로가기',
                r'기사 섹션 분류 안내',
                r'개별 기사의 섹션 정보.*',
                r'해당 언론사에서 선정.*',
                r'언론사 페이지.*',
                r'출처\s*:.*',
                r'^출처$',
                r'기자\s*이메일',
                r'Copyright.*',
                r'©.*',
                r'무단 전재.*',
                r'재배포.*',
                r'\[.*기자.*\]',
                r'기자\s*=\s*.*',
                r'사진\s*=\s*.*',
                r'<.*기자.*>',
                r'저작권자.*',
                r'저작권.*',
                # 메뉴/네비게이션
                r'^속보창$',
                r'신문/PDF 구독',
                r'^RSS$',
                r'정치·경제',
                r'대통령실/총리실',
                r'^정책$',
                r'국회/정당',
                r'국방/외교',
                r'^경제$',
                r'^일반$',
                r'^오피니언$',
                r'증권·금융',
                r'^부동산$',
                r'^기업$',
                r'글로벌경제',
                r'^사회$',
                r'문화·라이프',
                r'뉴스발전소',
                r'e스튜디오',
                # 기타 불필요한 텍스트
                r'^구독$',
                r'^알림$',
                r'^로그인$',
                r'^회원가입$',
                r'^검색$',
                r'^메뉴$',
                r'^홈$',
                r'^뉴스$',
                r'^더보기$',
                r'다른기사 보기',
                r'다른 기사',
                # 다른 기사 링크
                r'▶.*기사.*보기',
                r'다른기사.*보기',
                r'관련기사',
                r'인기키워드',
                r'기자의 다른기사',
                # 언론사명/저작권 표시
                r'<.*ⓒ.*>',
                r'<.*©.*>',
                r'<.*가장.*뉴스.*>',
                r'^스포츠투데이$',
                r'^아시아경제$',
                r'^TV리포트$',
                r'^엑스포츠뉴스$',
                r'^OSEN$',
                r'^뉴스컬처$',
                r'^스카이데일리$',
                r'^스포츠조선$',
                r'^인스타일$',
                r'www\..*\.com',
                r'http.*\.com',
                # 해시태그
                r'^#.*$',
                r'#\w+',
                # 기자 이메일
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                # UI 텍스트
                r'스크롤 이동 상태바',
                r'기사의 본문 내용은.*',
                r'디지털뉴스콘텐츠 이용규칙',
                r'해외주식 투자 도우미',
                r'뉴스핌 베스트 기사',
                r'주요포토',
                # 섹션 정보 안내
                r'기사의 섹션 정보는.*',
                r'해당 언론사의 분류를 따르고 있습니다.*',
                r'언론사는 개별 기사를.*',
                r'2개 이상 섹션으로 중복 분류할 수 있습니다.*',
                # 구독 안내
                r'뉴시스 구독하고.*',
                r'구독하고.*메인에서.*만나보세요.*',
                r'메인에서 바로 만나보세요.*',
                # 추천 기사 안내
                r'이 기사를 본 이용자들이.*',
                r'함께 많이 본 기사.*',
                r'해당 기사와 유사한 기사.*',
                r'관심 기사 등을 자동 추천합니다.*',
                # 프리미엄 콘텐츠 안내
                r'프리미엄콘텐츠는.*',
                r'네이버가 인터넷뉴스 서비스사업자로서.*',
                r'제공.*매개하는 기사가 아니고.*',
                r'해당 콘텐츠 제공자가.*',
                r'프리미엄 회원을 대상으로.*',
                r'별도로 발행.*제공하는 콘텐츠입니다.*',
                # 날짜/시간 정보 (본문 시작 부분의)
                r'^\d{4}-\d{2}-\d{2}$',
                r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$',
            ]
            
            # 불필요한 단어/구문 목록 (정확히 일치하는 경우)
            unwanted_exact = [
                '속보창', '신문/PDF 구독', 'RSS', '정치·경제', '대통령실/총리실', '정책',
                '국회/정당', '국방/외교', '경제', '일반', '오피니언', '증권·금융',
                '부동산', '기업', '글로벌경제', '사회', '문화·라이프', '뉴스발전소',
                'e스튜디오', '삭제', '닫기', '수정', '비밀번호', '구독', '알림',
                '로그인', '회원가입', '검색', '메뉴', '홈', '뉴스', '더보기',
                '관련뉴스', '최신뉴스', '주요뉴스', '최신포토', '오분류 제보하기',
                '언론사홈 바로가기', '기사 섹션 분류 안내', '출처', '다른기사 보기',
                '다른기사보기', '관련기사', '인기키워드', '기자의 다른기사',
                '스포츠투데이', '아시아경제', 'TV리포트', '엑스포츠뉴스', 'OSEN',
                '뉴스컬처', '스카이데일리', '스포츠조선', '인스타일',
                '디지털뉴스콘텐츠 이용규칙 보기', '해외주식 투자 도우미',
                # 구독 및 추천 안내
                '뉴시스 구독하고메인에서 바로 만나보세요!구독하고 메인에서 만나보세요!',
                '이 기사를 본 이용자들이 함께 많이 본 기사',
                '해당 기사와 유사한 기사',
                '관심 기사 등을 자동 추천합니다',
                '프리미엄콘텐츠는 네이버가 인터넷뉴스 서비스사업자로서 제공',
                '매개하는 기사가 아니고',
                '해당 콘텐츠 제공자가 프리미엄 회원을 대상으로 별도로 발행·제공하는 콘텐츠입니다',
            ]
            
            # 각 줄을 확인하여 불필요한 텍스트 제거
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 불필요한 패턴 확인
                is_unwanted = False
                
                # 정확히 일치하는 불필요한 텍스트 확인
                if line in unwanted_exact:
                    is_unwanted = True
                
                # 패턴 매칭 확인
                if not is_unwanted:
                    for pattern in unwanted_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            is_unwanted = True
                            break
                
                # 너무 짧은 줄 제거 (3자 이하)
                if not is_unwanted and len(line) <= 3:
                    is_unwanted = True
                
                # 숫자만 있는 줄 제거
                if not is_unwanted and re.match(r'^\d+$', line):
                    is_unwanted = True
                
                # URL만 있는 줄 제거
                if not is_unwanted and re.match(r'^https?://', line):
                    is_unwanted = True
                
                # 메뉴처럼 보이는 짧은 텍스트 제거 (· 또는 / 포함된 짧은 텍스트)
                if not is_unwanted and len(line) <= 10 and (re.search(r'[·/]', line) or re.search(r'^[가-힣]{1,3}[··/]', line)):
                    # 단, 실제 본문일 수 있는 긴 문장은 제외
                    if not re.search(r'[가-힣]{4,}', line):
                        is_unwanted = True
                
                # 기사 제목처럼 보이지만 본문이 아닌 것 제거 (대괄호로 시작하는 짧은 줄)
                if not is_unwanted and re.match(r'^\[.*\]\s*$', line) and len(line) < 50:
                    is_unwanted = True
                
                # 다른 기사 링크나 제목으로 보이는 것 제거 (짧고 대괄호나 특수문자 포함)
                if not is_unwanted and len(line) < 30 and (re.search(r'^\[.*\]', line) or re.search(r'^[가-힣]{1,5}…', line)):
                    is_unwanted = True
                
                # 기자 정보나 저작권 정보로 보이는 줄 제거
                if not is_unwanted and (re.search(r'기자\s*$', line) or re.search(r'@.*\.com', line) or 
                                        re.search(r'저작권|Copyright|©', line, re.I)):
                    is_unwanted = True
                
                # 언론사명만 있는 줄 제거
                if not is_unwanted and line in ['스포츠투데이', '아시아경제', 'TV리포트', '엑스포츠뉴스', 
                                                 'OSEN', '뉴스컬처', '스카이데일리', '스포츠조선', '인스타일']:
                    is_unwanted = True
                
                # URL만 있는 줄 제거 (www. 또는 http로 시작)
                if not is_unwanted and (re.match(r'^(www\.|http)', line, re.I)):
                    is_unwanted = True
                
                # 해시태그만 있는 줄 제거
                if not is_unwanted and re.match(r'^#\w+$', line):
                    is_unwanted = True
                
                # "▶다른기사보기" 같은 패턴 제거
                if not is_unwanted and re.search(r'▶.*기사.*보기', line):
                    is_unwanted = True
                
                # "<가장 가까이 만나는..." 같은 저작권 표시 제거
                if not is_unwanted and (re.search(r'<.*가장.*뉴스.*>', line) or 
                                        re.search(r'<.*ⓒ.*>', line) or re.search(r'<.*©.*>', line)):
                    is_unwanted = True
                
                if not is_unwanted:
                    cleaned_lines.append(line)
            
            content = '\n'.join(cleaned_lines)
            
            # 전체 텍스트에서 불필요한 패턴 제거 (여러 줄에 걸친 경우)
            unwanted_text_patterns = [
                r'기사의 섹션 정보는 해당 언론사의 분류를 따르고 있습니다[^\n]*',
                r'언론사는 개별 기사를[^\n]*',
                r'2개 이상 섹션으로 중복 분류할 수 있습니다[^\n]*',
                r'뉴시스 구독하고[^\n]*만나보세요[^\n]*',
                r'구독하고[^\n]*메인에서[^\n]*만나보세요[^\n]*',
                r'이 기사를 본 이용자들이[^\n]*',
                r'함께 많이 본 기사[^\n]*',
                r'해당 기사와 유사한 기사[^\n]*',
                r'관심 기사 등을 자동 추천합니다[^\n]*',
                r'프리미엄콘텐츠는 네이버가[^\n]*',
                r'인터넷뉴스 서비스사업자로서[^\n]*',
                r'제공.*매개하는 기사가 아니고[^\n]*',
                r'해당 콘텐츠 제공자가[^\n]*',
                r'프리미엄 회원을 대상으로[^\n]*',
                r'별도로 발행.*제공하는 콘텐츠입니다[^\n]*',
            ]
            
            for pattern in unwanted_text_patterns:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
            
            # 연속된 공백 제거
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = re.sub(r' {2,}', ' ', content)
            content = content.strip()
            
            # 너무 짧으면 None 반환
            if len(content) < 50:
                return None
            
            return content
        else:
            return None
            
    except requests.exceptions.Timeout:
        print(f"   [WARN] 요청 시간 초과")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   [WARN] 요청 오류: {e}")
        return None
    except Exception as e:
        print(f"   [WARN] 스크래핑 오류: {e}")
        return None

# 카테고리별 확장된 키워드 딕셔너리 (전역 변수로 정의)
CATEGORY_KEYWORDS = {
    "연애": {
        "core": ["연애", "열애", "열애설", "커플", "결혼", "이혼", "데이트", "로맨스",
                 "사랑", "프로포즈", "청혼", "신혼", "재혼", "불륜", "바람", "이별",
                 "재회", "소개팅", "맞선", "혼인", "부부", "연인", "애인", "결별",
                 "파혼", "약혼", "동거", "외도", "썸", "고백", "짝사랑", "애정",
                 "로맨틱", "구혼", "혼례", "결혼식", "신혼부부", "신혼살림"],
        "general": ["신랑", "신부", "웨딩", "혼수", "신혼여행", "교제", "연하남",
                    "연상녀", "돌싱", "미혼", "기혼", "솔로", "커플룩", "커플링",
                    "기념일", "발렌타인", "화이트데이", "연애상담", "권태기", "이상형",
                    "소개", "만남", "교제", "사귀", "헤어", "화해", "재결합"],
        "exclude": ["연애 시뮬레이션", "연애게임", "연애 게임", "게임 출시",
                    "드라마", "영화", "웹툰", "소설", "작품", "출연", "캐스팅",
                    "방송", "예능", "촬영", "시청률", "제작", "연기", "경기",
                    "선수", "팀", "구단", "야구", "축구", "스포츠", "경제", "주식",
                    "금리", "부동산", "기업", "매출", "실적"]
    },
    "경제": {
        "core": ["경제", "금리", "주식", "부동산", "인플레이션", "물가", "환율",
                 "증시", "코스피", "코스닥", "나스닥", "GDP", "경기침체", "불황",
                 "금융위기", "기준금리", "금리인상", "금리인하", "실적발표", "어닝쇼크",
                 "경제성장", "경제지표", "경제정책", "통화정책", "재정정책"],
        "general": ["은행", "금융", "증권", "보험", "펀드", "채권", "투자", "자산",
                    "배당", "시가총액", "IPO", "상장", "ETF", "비트코인", "암호화폐",
                    "기업", "매출", "영업이익", "순이익", "실적", "CEO", "인수합병",
                    "연봉", "최저임금", "고용", "실업", "세금", "수출", "수입",
                    "반도체", "자동차", "스타트업", "벤처", "분기실적", "연간실적",
                    "매출액", "영업손실", "적자", "흑자", "주가", "시총", "공모가",
                    "상장폐지", "유상증자", "무상증자", "액면분할", "경영", "사업",
                    "산업", "시장", "거래", "매매", "계약", "계약금", "계약서"],
        "exclude": ["야구 경제학", "축구 경제학", "스포츠 경제학", "게임 경제",
                   "경기장", "구장", "야구장", "축구장", "경기 결과", "경기 일정",
                   "선수", "감독", "코치", "팀", "구단", "이적료", "계약금", "연봉",
                   "야구", "축구", "농구", "배구", "골프", "테니스", "올림픽", "월드컵",
                   "KBO", "K리그", "프로야구", "프로축구", "MLB", "NBA", "NFL", "EPL",
                   "득점", "골", "홈런", "안타", "승리", "패배", "우승", "MVP"]
    },
    "스포츠": {
        "core": ["스포츠", "야구", "축구", "농구", "배구", "골프", "테니스",
                 "올림픽", "월드컵", "KBO", "K리그", "프로야구", "프로축구",
                 "MLB", "NBA", "NFL", "EPL", "프리미어리그", "경기장", "구장",
                 "야구장", "축구장", "농구장", "배구장", "경기 결과", "경기 일정",
                 "경기 스코어", "경기 하이라이트", "경기 중계", "경기 요약"],
        "general": ["선수", "감독", "코치", "구단", "팀", "이적", "영입", "FA",
                    "경기", "시합", "대회", "우승", "패배", "승리", "득점", "골",
                    "홈런", "안타", "MVP", "올스타", "수영", "육상", "격투기",
                    "UFC", "e스포츠", "롤드컵", "LCK", "라운드", "세트", "이닝",
                    "라인업", "벤치", "교체", "퇴장", "경고", "퇴장", "득점왕",
                    "타율", "방어율", "승률", "득점", "실점", "승점", "리그",
                    "챔피언십", "플레이오프", "준결승", "결승", "우승컵", "트로피"],
        "teams": ["삼성 라이온즈", "두산 베어스", "LG 트윈스", "롯데 자이언츠",
                  "KIA 타이거즈", "SSG 랜더스", "키움 히어로즈", "NC 다이노스",
                  "KT 위즈", "한화 이글스", "삼성", "두산", "롯데", "KIA", "SSG",
                  "키움", "NC", "KT", "한화", "토트넘", "맨유", "맨시티", "첼시",
                  "리버풀", "아스날", "바르셀로나", "레알 마드리드", "바이에른",
                  "기아", "현대", "SK", "LG", "두산", "롯데", "NC", "KT", "한화"],
        "famous_players": ["손흥민", "이강인", "김민재", "황희찬", "류현진",
                           "김하성", "이정후", "오타니", "박세리", "고진영",
                           "박병호", "이정후", "강정호", "추신수", "최지만",
                           "박찬호", "류현진", "추신수", "최지만", "김광현"],
        "exclude": ["스포츠카", "스포츠용품 매출", "스포츠웨어 주가",
                    "스포츠 브랜드 실적", "음악", "노래", "가수", "앨범", "음반",
                    "싱글", "차트", "플레이리스트", "스트리밍", "캐럴", "명곡",
                    "뮤직", "콘서트", "공연", "문화", "예술", "영화", "드라마",
                    "연예", "연예인", "배우", "아이돌", "K-pop", "에세이", "칼럼",
                    "뮤직카우", "발매", "시즌송", "주식", "금리", "부동산", "경제",
                    "증시", "코스피", "코스닥", "은행", "금융", "증권", "보험",
                    "매출", "영업이익", "실적", "기업", "CEO", "인수합병"]
    }
}

def fallback_classify(title, text):
    """키워드 매칭 없을 때 패턴 기반 분류 (개선된 버전)"""
    full_text = f"{title} {text}".lower()
    
    # 재난/사고 키워드 체크 (우선순위 1)
    disaster_keywords = [
        "화재", "사망", "부상", "재난", "사고", "참사", "폭발", "붕괴", "지진", "태풍",
        "홍수", "산사태", "교통사고", "항공사고", "선박사고", "실종", "구조", "소방",
        "경찰", "수사", "검찰", "법원", "재판", "범죄", "정치", "선거", "국회",
        "정당", "정부", "대통령", "총리", "외교", "국방", "전쟁", "테러"
    ]
    
    # 음악/문화 키워드 체크 (스포츠로 분류 방지)
    music_culture_keywords = [
        "음악", "노래", "가수", "앨범", "음반", "싱글", "차트", "플레이리스트",
        "스트리밍", "캐럴", "명곡", "뮤직", "콘서트", "공연", "문화", "예술",
        "영화", "드라마", "연예", "연예인", "배우", "아이돌", "K-pop", "에세이",
        "칼럼", "뮤직카우", "발매", "시즌송", "음악가", "작곡가", "작사가"
    ]
    
    if any(keyword in title or keyword in text for keyword in disaster_keywords):
        return "경제"  # 재난/사고/정치 뉴스는 경제로 분류 (연애 제외)
    
    # 음악/문화 뉴스는 스포츠로 분류하지 않음 (경제로 분류)
    if any(keyword in title or keyword in text for keyword in music_culture_keywords):
        return "경제"  # 음악/문화 뉴스는 경제로 분류 (스포츠 제외)
    
    # 스포츠 강력 패턴 체크 (우선순위 높음)
    sports_strong_patterns = [
        r'경기장|구장|야구장|축구장|농구장|배구장',
        r'경기 결과|경기 일정|경기 스코어|경기 하이라이트',
        r'득점왕|타율|방어율|승률|리그.*순위',
        r'플레이오프|챔피언십|준결승|결승전|우승컵',
        r'홈런|안타|타점|볼넷|삼진|이닝',
        r'골|어시스트|득점|실점|라운드|세트',
        r'KBO|K리그|프로야구|프로축구|MLB|NBA|NFL|EPL'
    ]
    sports_pattern_count = sum(1 for pattern in sports_strong_patterns if re.search(pattern, full_text))
    if sports_pattern_count >= 2:
        # 경제 강력 키워드가 제목에 없을 때만 스포츠로 분류
        economic_strong = ["주식", "금리", "부동산", "증시", "코스피", "코스닥", "매출", "실적", "영업이익"]
        if not any(kw in title for kw in economic_strong):
            return "스포츠"
    
    # 스포츠 점수 패턴 (더 정확한 패턴)
    sports_score_patterns = [
        r'\d+-\d+.*승.*패',  # 야구 스코어
        r'\d+:\d+.*골',  # 축구 스코어
        r'\d+회.*이닝',  # 야구 이닝
        r'\d+라운드',  # 라운드
    ]
    if any(re.search(pattern, full_text) for pattern in sports_score_patterns):
        # 경제 강력 키워드가 없을 때만
        economic_strong = ["주식", "금리", "부동산", "증시", "코스피", "코스닥"]
        if not any(kw in title for kw in economic_strong):
            return "스포츠"
    
    # 금액/퍼센트 패턴 → 경제 (더 엄격하게)
    economic_patterns = [
        r'\d+억|\d+조|\d+원',
        r'\d+%|퍼센트',
        r'주가|시총|상장|IPO|공모가',
        r'금리|기준금리|금리인상|금리인하',
        r'매출|영업이익|순이익|실적|분기실적'
    ]
    economic_pattern_count = sum(1 for pattern in economic_patterns if re.search(pattern, full_text))
    if economic_pattern_count >= 2:
        # 스포츠 강력 키워드가 제목에 없을 때만 경제로 분류
        sports_strong = ["야구", "축구", "농구", "배구", "경기장", "구장", "선수", "팀", "구단"]
        if not any(kw in title for kw in sports_strong):
            return "경제"
    
    # 관계 패턴 → 연애 (단, 재난 키워드가 없을 때만)
    love_patterns = [
        r'함께|동행|만남|사이',
        r'커플|연인|애인|부부',
        r'결혼|이혼|재혼|약혼'
    ]
    if any(re.search(pattern, full_text) for pattern in love_patterns):
        if not any(kw in title or kw in text for kw in disaster_keywords):
            # 스포츠나 경제 강력 키워드가 없을 때만
            sports_strong = ["야구", "축구", "농구", "배구", "경기장", "구장", "선수", "팀"]
            economic_strong = ["주식", "금리", "부동산", "증시", "코스피", "코스닥", "매출", "실적"]
            if not any(kw in title for kw in sports_strong) and not any(kw in title for kw in economic_strong):
                return "연애"
    
    return "연애"  # 최종 기본값 (경제 → 연애로 변경)

def classify_news_category(title, description, content="", search_keyword=""):
    """
    뉴스를 연애/경제/스포츠 중 하나로 분류 (개선된 버전)
    반환: 카테고리명 (기타 없음)
    search_keyword: 검색에 사용된 키워드 (점수가 낮을 때 기본값으로 사용)
    """
    text_title = title.lower()
    text_body = f"{description} {content}".lower()
    full_text = f"{text_title} {text_body}"
    
    # 재난/사고/사회 뉴스 키워드 (연애로 잘못 분류 방지)
    disaster_keywords = [
        "화재", "사망", "부상", "재난", "사고", "참사", "폭발", "붕괴", "지진", "태풍",
        "홍수", "산사태", "교통사고", "항공사고", "선박사고", "실종", "구조", "소방",
        "경찰", "수사", "수사관", "검찰", "법원", "재판", "범죄", "살인", "강도",
        "절도", "사기", "폭행", "성폭력", "아동학대", "가정폭력", "자살", "투신",
        "정치", "선거", "국회", "정당", "정부", "대통령", "총리", "장관", "의원",
        "외교", "국방", "군사", "전쟁", "분쟁", "테러", "테러리스트", "인질",
        "사회", "복지", "교육", "의료", "병원", "환자", "질병", "전염병", "코로나",
        "홍콩", "중국", "일본", "미국", "북한", "러시아", "우크라이나"
    ]
    
    # 재난/사고/사회 뉴스가 연애로 분류되지 않도록 체크
    is_disaster_news = any(keyword in text_title or keyword in text_body for keyword in disaster_keywords)
    
    # 음악/문화 관련 키워드 체크 (스포츠로 잘못 분류 방지)
    music_culture_keywords = [
        "음악", "노래", "가수", "앨범", "음반", "싱글", "차트", "플레이리스트",
        "스트리밍", "캐럴", "명곡", "뮤직", "콘서트", "공연", "문화", "예술",
        "영화", "드라마", "연예", "연예인", "배우", "아이돌", "K-pop", "에세이",
        "칼럼", "뮤직카우", "발매", "시즌송", "음악가", "작곡가", "작사가",
        "프로듀서", "음악회", "오케스트라", "연주", "연주회", "리뷰", "평론"
    ]
    is_music_culture_news = any(keyword in text_title or keyword in text_body for keyword in music_culture_keywords)
    
    scores = {"연애": 0, "경제": 0, "스포츠": 0}
    
    # 0단계: 재난/사고/사회 뉴스는 연애로 분류하지 않음 (연애 점수 대폭 감점)
    if is_disaster_news:
        scores["연애"] -= 100  # 재난 뉴스는 절대 연애로 분류되지 않도록
    
    # 0-1단계: 음악/문화 뉴스는 스포츠로 분류하지 않음 (스포츠 점수 대폭 감점)
    if is_music_culture_news:
        scores["스포츠"] -= 100  # 음악/문화 뉴스는 절대 스포츠로 분류되지 않도록
    
    # 1단계: 유명 선수 체크 (스포츠 우선 - 즉시 반환)
    for player in CATEGORY_KEYWORDS["스포츠"].get("famous_players", []):
        if player in title or player in text_body:
            # 선수 이름이 있으면 스포츠 확정 (단, 경제 키워드가 매우 강하면 제외)
            economic_strong_keywords = ["주식", "금리", "부동산", "증시", "코스피", "코스닥", "매출", "실적", "영업이익"]
            if not any(kw in full_text for kw in economic_strong_keywords):
                return "스포츠"
    
    # 2단계: 강력한 스포츠 패턴 체크 (우선순위 높음)
    sports_strong_patterns = [
        r'\d+-\d+.*승.*패', r'\d+:\d+.*골', r'\d+회.*이닝', r'\d+라운드',
        r'경기장', r'구장', r'야구장', r'축구장', r'농구장', r'배구장',
        r'경기 결과', r'경기 일정', r'경기 스코어', r'경기 하이라이트',
        r'득점왕', r'타율', r'방어율', r'승률', r'리그.*순위',
        r'플레이오프', r'챔피언십', r'준결승', r'결승전', r'우승컵'
    ]
    sports_pattern_count = sum(1 for pattern in sports_strong_patterns if re.search(pattern, full_text))
    if sports_pattern_count >= 2:  # 2개 이상 패턴이면 스포츠 확정
        # 단, 경제 강력 키워드가 없을 때만
        economic_strong = ["주식", "금리", "부동산", "증시", "코스피", "코스닥", "매출", "실적", "영업이익", "기업"]
        if not any(kw in text_title for kw in economic_strong):
            scores["스포츠"] += 50  # 강력한 보너스 점수
    
    # 3단계: 제외 키워드 체크 (강력한 감점)
    for category, keywords in CATEGORY_KEYWORDS.items():
        for exclude in keywords.get("exclude", []):
            if exclude in text_title:
                scores[category] -= 30  # 제목에 제외 키워드가 있으면 강력 감점
            elif exclude in text_body:
                scores[category] -= 15  # 본문에 있으면 중간 감점
    
    # 4단계: 점수 계산 (가중치 개선)
    for category, keywords in CATEGORY_KEYWORDS.items():
        # 제목에서 핵심 키워드 (20점 - 가중치 증가)
        for kw in keywords.get("core", []):
            if kw in text_title:
                scores[category] += 20

        # 제목에서 일반 키워드 (8점)
        for kw in keywords.get("general", []):
            if kw in text_title:
                scores[category] += 8

        # 제목에서 팀명 키워드 (12점 - 가중치 증가)
        for kw in keywords.get("teams", []):
            if kw in text_title:
                scores[category] += 12

        # 본문에서 핵심 키워드 (8점)
        for kw in keywords.get("core", []):
            if kw in text_body and kw not in text_title:
                scores[category] += 8

        # 본문에서 일반 키워드 (3점)
        for kw in keywords.get("general", []):
            if kw in text_body and kw not in text_title:
                scores[category] += 3

        # 본문에서 팀명 키워드 (6점)
        for kw in keywords.get("teams", []):
            if kw in text_body and kw not in text_title:
                scores[category] += 6
    
    # 5단계: 스포츠 특화 패턴 체크 (추가 보너스)
    sports_specific_patterns = [
        (r'(홈런|안타|타점|볼넷|삼진)', 5),  # 야구 용어
        (r'(골|어시스트|득점|실점)', 5),  # 축구 용어
        (r'(라운드|세트|이닝|경기)', 3),  # 경기 단위
        (r'(승리|패배|무승부|우승|준우승)', 4),  # 경기 결과
    ]
    for pattern, bonus in sports_specific_patterns:
        if re.search(pattern, full_text):
            # 경제 강력 키워드가 제목에 없을 때만 보너스
            economic_strong = ["주식", "금리", "부동산", "증시", "코스피", "코스닥"]
            if not any(kw in text_title for kw in economic_strong):
                scores["스포츠"] += bonus
    
    # 6단계: 경제 특화 패턴 체크 (추가 보너스)
    economic_specific_patterns = [
        (r'(\d+억|\d+조|\d+원)', 3),  # 금액 패턴
        (r'(\d+%|퍼센트)', 2),  # 퍼센트
        (r'(주가|시총|상장|IPO|공모가)', 5),  # 주식 관련
        (r'(금리|기준금리|금리인상|금리인하)', 6),  # 금리 관련
        (r'(매출|영업이익|순이익|실적|분기실적)', 4),  # 실적 관련
    ]
    for pattern, bonus in economic_specific_patterns:
        matches = len(re.findall(pattern, full_text))
        if matches >= 2:  # 2개 이상 패턴이면 보너스
            # 스포츠 강력 키워드가 제목에 없을 때만 보너스
            sports_strong = ["야구", "축구", "농구", "배구", "경기장", "구장", "선수", "팀", "구단"]
            if not any(kw in text_title for kw in sports_strong):
                scores["경제"] += bonus
    
    # 7단계: 최고 점수 카테고리 선택 (최소 점수 기준 적용)
    max_score = max(scores.values())

    # 최소 점수 기준: 최소 10점 이상이어야 해당 카테고리로 분류
    if max_score < 10:
        # 검색 키워드가 있으면 해당 키워드의 목표 카테고리 반환
        if search_keyword and search_keyword in KEYWORD_CATEGORY_MAP:
            return KEYWORD_CATEGORY_MAP[search_keyword]
        return fallback_classify(title, text_body)
    
    # 동점 처리: 스포츠 > 경제 > 연애 우선순위
    # 단, 점수 차이가 5점 이내일 때만 우선순위 적용
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_score = sorted_scores[0][1]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    
    # 점수 차이가 5점 이내면 우선순위 적용
    if top_score - second_score <= 5:
        for category in ["스포츠", "경제", "연애"]:
            if scores[category] == top_score:
                return category
    
    # 점수 차이가 크면 최고 점수 카테고리 반환
    return sorted_scores[0][0]

def is_category_related(title, description, category):
    """뉴스가 지정된 카테고리와 관련있는지 확인 (필터링용)"""
    if not category:
        return True  # 카테고리가 지정되지 않으면 모두 통과
    
    if category not in CATEGORY_KEYWORDS:
        return True  # 알 수 없는 카테고리는 모두 통과
    
    keywords = CATEGORY_KEYWORDS[category]
    text = (title + " " + description).lower()
    
    # 키워드가 하나라도 포함되어 있으면 관련 뉴스로 판단
    for keyword in keywords:
        if keyword in text:
            return True
    
    return False

def normalize_text(text):
    """텍스트 정규화 (비교를 위해)"""
    if not text:
        return ""
    # HTML 태그 제거, 공백 정리, 소문자 변환
    text = re.sub(r'<[^>]+>', '', text)  # HTML 태그 제거
    text = re.sub(r'\s+', ' ', text)  # 연속 공백을 하나로
    text = text.strip().lower()
    # 특수문자 제거 (비교를 위해)
    text = re.sub(r'[^\w\s가-힣]', '', text)
    return text

def calculate_similarity(text1, text2):
    """두 텍스트의 유사도 계산 (간단한 방법)"""
    if not text1 or not text2:
        return 0.0
    
    # 정규화
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # 완전 일치
    if norm1 == norm2:
        return 1.0
    
    # 공통 단어 비율 계산
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return 0.0
    
    common_words = words1.intersection(words2)
    total_words = words1.union(words2)
    
    if not total_words:
        return 0.0
    
    similarity = len(common_words) / len(total_words)
    
    # 긴 텍스트의 경우 부분 일치도 고려
    if len(norm1) > 20 and len(norm2) > 20:
        # 한쪽이 다른 쪽에 포함되는 경우
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.8)
    
    return similarity

def is_today_news(pub_date_str):
    """발행일이 오늘인지 확인 (네이버 API pubDate 형식: 'Fri, 05 Dec 2025 10:30:00 +0900')"""
    if not pub_date_str:
        return True  # pubDate 없으면 포함
    try:
        pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z')
        today = datetime.now(timezone.utc).astimezone().date()
        return pub_date.date() == today
    except Exception:
        return True  # 파싱 실패시 포함

def get_db_titles():
    """DB에서 모든 뉴스 제목 가져오기"""
    try:
        from utils.database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT title FROM news")
        titles = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return titles
    except Exception as e:
        print(f"[WARN] DB 제목 로드 실패: {e}")
        return []

def is_duplicate_in_db(new_title, db_titles, threshold=0.75):
    """DB 제목과 유사도 75% 이상이면 중복 판정. (중복여부, 유사도, 매칭제목) 반환"""
    if not db_titles:
        return (False, 0.0, None)
    
    new_normalized = normalize_text(new_title)
    for title in db_titles:
        existing_normalized = normalize_text(title)
        ratio = SequenceMatcher(None, new_normalized, existing_normalized).ratio()
        if ratio >= threshold:
            return (True, ratio, title)
    return (False, 0.0, None)

def load_existing_news(sheet):
    """시트의 기존 뉴스 데이터를 모두 로드하여 캐시에 저장"""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            print("[LIST] 기존 업로드된 뉴스 확인 중...")
            all_values = sheet.get_all_values()
            
            if len(all_values) <= 1:
                print("   기존 뉴스 없음 (새로 시작)")
                return {
                    'links': set(),
                    'titles': [],
                    'normalized_titles': []
                }
            
            # 헤더 행 제외
            existing_links = set()
            existing_titles = []
            existing_normalized_titles = []
            
            for row in all_values[1:]:  # 헤더 제외
                # 링크 저장 (C열, 인덱스 2)
                if len(row) > 2 and row[2] and row[2].strip():
                    existing_links.add(row[2].strip())
                
                # 제목 저장 (A열, 인덱스 0)
                if len(row) > 0 and row[0] and row[0].strip():
                    title = row[0].strip()
                    existing_titles.append(title)
                    existing_normalized_titles.append(normalize_text(title))
            
            print(f"   [OK] 기존 뉴스 {len(existing_links)}개 확인 완료 (링크: {len(existing_links)}개, 제목: {len(existing_titles)}개)")
            return {
                'links': existing_links,
                'titles': existing_titles,
                'normalized_titles': existing_normalized_titles
            }
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"[WARN] API 할당량 초과, {wait_time}초 대기 후 재시도 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[WARN] 기존 뉴스 로드 실패 (API 제한): {e}")
                    return {'links': set(), 'titles': [], 'normalized_titles': []}
            else:
                print(f"[WARN] 기존 뉴스 로드 중 오류: {e}")
                return {'links': set(), 'titles': [], 'normalized_titles': []}
    
    return {'links': set(), 'titles': [], 'normalized_titles': []}

def check_duplicate_in_cache(existing_data, link, title=None):
    """캐시된 기존 뉴스 데이터와 비교하여 중복 확인"""
    if not existing_data:
        return False
    
    # 1. 링크로 중복 체크 (가장 정확)
    if link and link.strip() in existing_data['links']:
        return True
    
    # 2. 제목으로 중복 체크 (링크가 다른 경우 대비)
    if title and title.strip():
        normalized_new_title = normalize_text(title)
        
        # 정규화된 제목이 완전히 동일한 경우
        if normalized_new_title in existing_data['normalized_titles']:
            return True
        
        # 제목 유사도 체크
        for existing_title, normalized_existing_title in zip(existing_data['titles'], existing_data['normalized_titles']):
            similarity = calculate_similarity(normalized_new_title, normalized_existing_title)
            # 유사도가 0.75 이상이면 중복으로 간주
            if similarity >= 0.75:
                return True
    
    return False

def get_chrome_driver():
    """ChromeDriver 초기화 함수"""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # 창을 안 보고 싶으면 이 줄의 주석(#)을 지우세요
    options.add_argument("--start-maximized") # 창 최대화
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("[OK] ChromeDriver 자동 설치 완료")
    except Exception as e:
        error_msg = str(e)
        print(f"[WARN] ChromeDriverManager 오류: {error_msg}")
        if "WinError 193" in error_msg or "올바른 Win32 응용 프로그램이 아닙니다" in error_msg:
            print("   시스템 PATH의 ChromeDriver 사용 시도 중...")
            try:
                driver = webdriver.Chrome(options=options)
                print("[OK] 시스템 PATH의 ChromeDriver 사용 성공")
            except Exception as e2:
                print(f"[ERROR] ChromeDriver 초기화 실패: {e2}")
                print("   Chrome 브라우저를 최신 버전으로 업데이트하거나 ChromeDriver를 수동으로 설치해주세요.")
                return None
    return driver

def login_to_newstown(driver, wait):
    """뉴스타운에 로그인하는 함수"""
    driver.get("http://www.newstown.co.kr/member/login.html")
    
    # 아이디 입력
    user_id_field = wait.until(EC.presence_of_element_located((By.ID, "user_id")))
    user_id_field.clear()
    user_id_field.send_keys(SITE_ID)
    
    # 비번 입력
    driver.find_element(By.ID, "user_pw").send_keys(SITE_PW)
    
    # 로그인 버튼 클릭
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1.5) # 로그인 처리 대기
    return True

def upload_to_newstown(title, content):
    """뉴스타운에 기사를 자동으로 업로드하는 함수 (셀레니움)"""
    
    driver = get_chrome_driver()
    if driver is None:
        return False
    
    wait = WebDriverWait(driver, 15)

    try:
        print(f"\n[START] [뉴스타운 업로드 시작] '{title[:30]}...'")

        # -------------------------------------------------
        # 1. 로그인 단계
        # -------------------------------------------------
        login_to_newstown(driver, wait)

        # -------------------------------------------------
        # 2. 글쓰기 폼 이동
        # -------------------------------------------------
        driver.get("http://www.newstown.co.kr/news/userArticleWriteForm.html")
        
        # -------------------------------------------------
        # 3. 섹션 선택 (1차 섹션 -> 2차 섹션)
        # -------------------------------------------------
        try:
            # 페이지 로드 대기
            wait.until(EC.presence_of_element_located((By.NAME, "sectionCode")))
            time.sleep(1)  # 페이지 완전 로드 대기
            
            # 1차 섹션 드롭다운 찾기 및 선택
            section_element = wait.until(EC.presence_of_element_located((By.NAME, "sectionCode")))
            section_select = Select(section_element)
            section_select.select_by_visible_text("데일리 핫이슈")
            print("[OK] 1차 섹션 선택: 데일리 핫이슈")
            time.sleep(1.5)  # 2차 섹션 옵션이 로드될 때까지 대기
            
            # 2차 섹션 드롭다운 찾기 및 선택
            sub_section_element = wait.until(EC.presence_of_element_located((By.NAME, "subSectionCode")))
            sub_section_select = Select(sub_section_element)
            sub_section_select.select_by_visible_text("연예")
            print("[OK] 2차 섹션 선택: 연예")
            time.sleep(0.5)  # 선택 완료 대기
        except Exception as e:
            print(f"[WARN] 섹션 선택 중 경고: {e}")
            import traceback
            traceback.print_exc()

        # -------------------------------------------------
        # 4. 제목 입력
        # -------------------------------------------------
        driver.find_element(By.ID, "title").send_keys(title)

        # -------------------------------------------------
        # 5. 본문 입력 (CKEditor / iframe 처리)
        # -------------------------------------------------
        print("✍️ 본문 작성 중...")
        
        # iframe 찾기 (에디터는 보통 iframe 안에 숨어있음)
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        driver.switch_to.frame(iframe) # iframe 내부로 진입
        
        body_area = driver.find_element(By.TAG_NAME, "body")
        body_area.clear() # 기존 내용 비우기
        body_area.send_keys(content) # 구글 시트 내용 입력
        
        driver.switch_to.default_content() # 다시 메인 화면으로 복귀

        # -------------------------------------------------
        # 6. 저장 버튼 클릭
        # -------------------------------------------------
        print("[SAVE] 저장 버튼 클릭...")
        save_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        
        # 자바스크립트로 강제 클릭 (오류 방지)
        driver.execute_script("arguments[0].click();", save_btn)
        
        # 저장 완료 대기 (3초)
        time.sleep(3) 
        
        # 성공 여부 확인 (페이지가 이동했거나, 알림창이 떴는지 등)
        print("[OK] 뉴스타운 업로드 완료!")
        return True

    except Exception as e:
        print(f"[ERROR] 뉴스타운 업로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 브라우저 닫기
        driver.quit()

def main():
    print("="*60)
    print("  네이버 뉴스 → 구글 시트 수집기")
    print("="*60)
    print(f"\n[CONNECT] 구글 시트 연결 중...")
    
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        doc = client.open_by_url(SHEET_URL)
        sheet = doc.get_worksheet(0)  # 첫 번째 시트
        print("[OK] 구글 시트 연결 성공!")
        
    except Exception as e:
        print(f"[ERROR] 구글 시트 연결 실패: {e}")
        print("   credentials.json 파일이 같은 폴더에 있는지 확인하세요.")
        return
    
    # ==========================================
    # 1단계: 기존 업로드된 뉴스 확인 (먼저 실행)
    # ==========================================
    existing_news_data = load_existing_news(sheet)
    
    # 실시간 뉴스 수집 (오늘 기준) - 연애, 스포츠
    # 요청한 개수만큼 중복 없는 뉴스를 확보할 때까지 반복 검색
    target_count = sum(KEYWORDS.values())  # 목표 개수
    all_news_items = []
    all_news_links = set()  # 중복 제거를 위한 링크 세트
    searched_keywords = {}  # 각 키워드별 검색 횟수 추적
    total_duplicate_count = 0  # 전체 스프레드시트 중복 개수
    total_already_collected_count = 0  # 전체 이번 검색 중복 개수
    total_not_today_count = 0  # 당일 아닌 뉴스 개수
    total_db_duplicate_count = 0  # DB 중복 개수
    
    # DB에서 기존 제목들 로드 (중복 체크용)
    db_titles = get_db_titles()
    print(f"\n[DB] 기존 DB 뉴스 {len(db_titles)}개 로드 완료")
    
    print(f"\n[SEARCH] 실시간 뉴스 검색 중... (당일 + 인기순)")
    print(f"   목표: 총 {target_count}개 중복 없는 뉴스")
    print(f"   정렬: 인기순(sim) + 당일 뉴스만\n")
    
    # 각 키워드별로 초기 검색 개수 설정 (요청 개수의 2배로 시작하여 중복 없는 뉴스 확보)
    search_multiplier = 2  # 중복을 고려하여 2배로 검색
    max_search_rounds = 5  # 최대 5라운드까지 검색
    
    for round_num in range(1, max_search_rounds + 1):
        if len(all_news_items) >= target_count:
            break
            
        print(f"[ROUND] 검색 라운드 {round_num}/{max_search_rounds} (현재 수집: {len(all_news_items)}/{target_count}개)")
        
        # 각 키워드별로 뉴스 검색
        for keyword, count in KEYWORDS.items():
            if len(all_news_items) >= target_count:
                break
                
            # 필요한 개수만큼 추가 검색 (이미 수집된 개수 고려)
            needed_count = target_count - len(all_news_items)
            search_count = min(count * search_multiplier, 100)  # 네이버 API 최대 100개
            
            if keyword not in searched_keywords:
                searched_keywords[keyword] = 0
            
            # 이미 충분히 검색했으면 스킵
            if searched_keywords[keyword] >= search_count:
                continue
            
            print(f"   '{keyword}' 키워드로 추가 검색 중... (현재: {len(all_news_items)}/{target_count}개)")
            news_result = get_naver_news(keyword, display=search_count, sort='sim')
            
            if news_result and 'items' in news_result:
                new_items_count = 0
                duplicate_count = 0  # 중복된 뉴스 개수
                already_collected_count = 0  # 이미 수집된 뉴스 개수
                not_today_count = 0  # 당일 아닌 뉴스 개수
                db_dup_count = 0  # DB 중복 개수
                
                for item in news_result['items']:
                    if len(all_news_items) >= target_count:
                        break
                        
                    link = item.get('link', '').strip()
                    title = item.get('title', '').replace("<b>", "").replace("</b>", "").replace("&quot;", "\"").replace("&amp;", "&")
                    pub_date = item.get('pubDate', '')
                    
                    # 0단계: 당일 뉴스만 필터링
                    if not is_today_news(pub_date):
                        not_today_count += 1
                        total_not_today_count += 1
                        continue
                    
                    # 1단계: 이미 이번 검색에서 수집된 뉴스와 중복 체크
                    if link and link not in all_news_links:
                        # 2단계: 기존 스프레드시트와 중복 체크
                        if not check_duplicate_in_cache(existing_news_data, link, title):
                            # 3단계: DB 중복 체크 (제목 유사도 75%)
                            is_db_dup, sim_ratio, matched_title = is_duplicate_in_db(title, db_titles, 0.75)
                            if is_db_dup:
                                db_dup_count += 1
                                total_db_duplicate_count += 1
                                print(f"         [DB중복] {title[:30]}... (유사도 {sim_ratio:.0%})")
                                continue
                            
                            item['_search_keyword'] = keyword
                            all_news_items.append(item)
                            all_news_links.add(link)
                            new_items_count += 1
                            print(f"         [신규] {title[:40]}...")
                        else:
                            duplicate_count += 1  # 스프레드시트에 이미 있는 뉴스
                            total_duplicate_count += 1
                    else:
                        already_collected_count += 1  # 이미 이번 검색에서 수집된 뉴스
                        total_already_collected_count += 1
                
                searched_keywords[keyword] += len(news_result['items'])
                print(f"      [OK] {keyword}: {new_items_count}개 신규 수집 (총 {len(all_news_items)}/{target_count}개)")
                if not_today_count > 0:
                    print(f"         [날짜] 당일 아닌 뉴스: {not_today_count}개 제외")
                if db_dup_count > 0:
                    print(f"         [DB] DB 중복: {db_dup_count}개 제외")
                if duplicate_count > 0:
                    print(f"         [시트] 스프레드시트 중복: {duplicate_count}개 제외")
                if already_collected_count > 0:
                    print(f"         [검색] 이번 검색 중복: {already_collected_count}개 제외")
        
        # 목표 개수에 도달했는지 확인
        if len(all_news_items) >= target_count:
            print(f"\n[OK] 목표 개수 달성! 총 {len(all_news_items)}개 중복 없는 뉴스 수집 완료")
            print(f"   [STAT] 중복 필터링 통계:")
            print(f"      - 스프레드시트 중복 제외: {total_duplicate_count}개")
            print(f"      - 이번 검색 중복 제외: {total_already_collected_count}개")
            break
        
        # 다음 라운드를 위해 검색 개수 증가
        search_multiplier += 1
        time.sleep(2)  # API 제한 방지를 위한 대기
    
    # 최종 통계 출력 (목표 개수에 도달하지 못한 경우에도)
    if len(all_news_items) < target_count:
        print(f"\n[WARN] 목표 개수({target_count}개)에 도달하지 못함 (실제: {len(all_news_items)}개)")
        print(f"   [STAT] 중복 필터링 통계:")
        print(f"      - 스프레드시트 중복 제외: {total_duplicate_count}개")
        print(f"      - 이번 검색 중복 제외: {total_already_collected_count}개")
    
    # 목표 개수만큼만 선택
    all_news_items = all_news_items[:target_count]
    
    print(f"\n[STAT] 최종 수집: {len(all_news_items)}개 중복 없는 뉴스")
    
    # news_data 형식으로 변환
    news_data = {'items': all_news_items}
    
    if news_data and 'items' in news_data:
        # ==========================================
        # 2단계: 추가 필터링 (운세, 인물 제한 등)
        # 중복 체크는 이미 1단계에서 완료됨
        # ==========================================
        valid_items = []
        filtered_count = 0
        
        print(f"\n[SEARCH] 추가 필터링 중... (운세 제외, 인물 제한 등)")
        
        # 특정 인물 중심 뉴스 필터링을 위한 카운터
        person_counter = {}  # 인물명: 카운트
        MAX_PERSON_NEWS = 3  # 같은 인물 관련 뉴스는 최대 3개만 허용
        
        for item in news_data['items']:
            title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"").replace("&amp;", "&")
            description = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"").replace("&amp;", "&")
            link = item['link']
            
            # 운세 관련 뉴스 필터링 (제외)
            fortune_keywords = [
                "운세", "별자리", "오늘의 운세", "내일의 운세", "주간 운세", "월간 운세",
                "타로", "사주", "점성술", "점성", "운세 전문", "산수도인",
                "물병자리", "물고기자리", "양자리", "황소자리", "쌍둥이자리", "게자리",
                "사자자리", "처녀자리", "천칭자리", "전갈자리", "사수자리", "염소자리",
                "행운의 시간", "행운의 물건", "행운의 장소", "행운의 색상", "애정운", "재물운"
            ]
            
            title_lower = title.lower()
            desc_lower = description.lower() if description else ""
            combined_text = f"{title_lower} {desc_lower}"
            
            # 운세 키워드가 포함되어 있으면 제외
            is_fortune_news = any(keyword in combined_text for keyword in fortune_keywords)
            if is_fortune_news:
                filtered_count += 1
                print(f"   ⏭️ 운세 관련 뉴스 제외: {title[:50]}...")
                continue
            
            # 카테고리 필터링 (필요한 경우만)
            if CATEGORY and not is_category_related(title, description, CATEGORY):
                filtered_count += 1
                continue
            
            # 특정 인물 중심 뉴스 필터링 (한 인물 관련 뉴스가 너무 많으면 제한)
            # 한국 이름 패턴 (2-4자 한글 이름, 제목에서 반복되는 이름)
            person_names = re.findall(r'[가-힣]{2,4}', title)
            filtered_persons = []
            common_words = ['연애', '경제', '스포츠', '정치', '사회', '문화', '기자', '대통령', '총리', '장관', '회장', '사장', 
                           '뉴스', '기사', '오늘', '내일', '어제', '최근', '이번', '다음', '이전', '현재', '지난', '올해', '작년']
            
            for name in person_names:
                if len(name) >= 2 and name not in common_words:
                    # 제목에서 2번 이상 나오거나, 제목과 본문에 모두 나오는 이름만 (인물일 가능성 높음)
                    title_count = title.count(name)
                    desc_count = description.count(name) if description else 0
                    if title_count >= 2 or (title_count >= 1 and desc_count >= 1):
                        filtered_persons.append(name)
            
            # 특정 인물 관련 뉴스가 너무 많으면 제한
            skip_person_news = False
            for person in filtered_persons:
                if person not in person_counter:
                    person_counter[person] = 0
                person_counter[person] += 1
                
                if person_counter[person] > MAX_PERSON_NEWS:
                    skip_person_news = True
                    filtered_count += 1
                    print(f"   ⏭️ 특정 인물({person}) 관련 뉴스 제한 초과 ({person_counter[person]}개) (건너뜀): {title[:50]}...")
                    break
            
            if skip_person_news:
                continue
            
            # 검색 키워드 정보 유지
            search_keyword = item.get('_search_keyword', '')
            
            valid_items.append({
                'title': title,
                'description': description,
                'link': link,
                '_search_keyword': search_keyword  # 검색 키워드 유지
            })
        
        print(f"[OK] 처리할 뉴스: {len(valid_items)}개 (필터링: {filtered_count}개)")
        
        # 필터링 후에도 목표 개수보다 적으면 추가 검색
        if len(valid_items) < target_count:
            print(f"[WARN] 목표 개수({target_count}개)보다 적습니다. 현재: {len(valid_items)}개")
            print(f"   추가 검색을 통해 목표 개수 확보 중...")
            
            # 추가 검색을 통해 목표 개수만큼 확보
            additional_rounds = 0
            while len(valid_items) < target_count and additional_rounds < 3:
                additional_rounds += 1
                print(f"   추가 검색 라운드 {additional_rounds}...")
                
                for keyword, count in KEYWORDS.items():
                    if len(valid_items) >= target_count:
                        break
                    
                    # 더 많은 뉴스 검색
                    search_count = min(count * 5, 100)
                    news_result = get_naver_news(keyword, display=search_count, sort='sim')
                    
                    if news_result and 'items' in news_result:
                        for item in news_result['items']:
                            if len(valid_items) >= target_count:
                                break
                            
                            link = item.get('link', '').strip()
                            title = item.get('title', '').replace("<b>", "").replace("</b>", "").replace("&quot;", "\"").replace("&amp;", "&")
                            description = item.get('description', '').replace("<b>", "").replace("</b>", "").replace("&quot;", "\"").replace("&amp;", "&")
                            
                            # 이미 valid_items에 있는지 확인
                            if any(v['link'] == link for v in valid_items):
                                continue
                            
                            # 중복 체크
                            if check_duplicate_in_cache(existing_news_data, link, title):
                                continue
                            
                            # 운세 체크
                            title_lower = title.lower()
                            desc_lower = description.lower() if description else ""
                            combined_text = f"{title_lower} {desc_lower}"
                            fortune_keywords = ["운세", "별자리", "타로", "사주", "점성술"]
                            if any(kw in combined_text for kw in fortune_keywords):
                                continue
                            
                            # valid_items에 추가
                            search_keyword = item.get('_search_keyword', keyword)
                            valid_items.append({
                                'title': title,
                                'description': description,
                                'link': link,
                                '_search_keyword': search_keyword
                            })
                
                if len(valid_items) >= target_count:
                    break
                time.sleep(2)
            
            # 목표 개수만큼만 선택
            valid_items = valid_items[:target_count]
            print(f"[OK] 최종 처리할 뉴스: {len(valid_items)}개")
        
        if not valid_items:
            print("처리할 새 뉴스가 없습니다.")
            return
        
        # 병렬로 본문 스크래핑 (속도 개선)
        print(f"\n[DOC] 본문 스크래핑 중... (병렬 처리)")
        news_results = []
        
        def scrape_news_wrapper(item_data):
            """본문 스크래핑 래퍼 함수"""
            title = item_data['title']
            description = item_data['description']
            link = item_data['link']
            search_keyword = item_data.get('_search_keyword', '')  # 검색 키워드 유지
            
            try:
                full_content = scrape_news_content(link)
                if not full_content:
                    full_content = description
                return {
                    'title': title,
                    'description': description,
                    'link': link,
                    'content': full_content,
                    '_search_keyword': search_keyword,  # 검색 키워드 유지
                    'success': True
                }
            except Exception as e:
                return {
                    'title': title,
                    'description': description,
                    'link': link,
                    'content': description,  # 실패 시 요약문 사용
                    '_search_keyword': search_keyword,  # 검색 키워드 유지
                    'success': False,
                    'error': str(e)
                }
        
        # 멀티스레딩으로 병렬 처리 (최대 10개 동시 실행)
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {executor.submit(scrape_news_wrapper, item): item for item in valid_items}
            
            completed = 0
            for future in as_completed(future_to_item):
                completed += 1
                result = future.result()
                news_results.append(result)
                status = "[OK]" if result['success'] else "[WARN]"
                print(f"   [{completed}/{len(valid_items)}] {status} {result['title'][:30]}...")
        
        # 카테고리 분류 및 카테고리별 그룹화
        print(f"\n[STAT] 카테고리 분류 중... (목표: {target_count}개)")
        category_mismatch_count = 0  # 카테고리 불일치로 제외된 뉴스 수
        
        # 카테고리별로 뉴스 그룹화
        news_by_category = {"연애": [], "스포츠": []}
        if ENABLE_ECONOMY_CATEGORY:
            news_by_category["경제"] = []

        skipped_mismatch_count = 0  # 카테고리 불일치로 건너뛴 뉴스 수
        
        for result in news_results:
            # 카테고리 자동 분류 (분류 함수로 실제 카테고리 확인)
            search_keyword = result.get('_search_keyword', '')
            
            # 1. 분류 함수로 실제 카테고리 확인 (검색 키워드 전달)
            actual_category = classify_news_category(result['title'], result['description'], result['content'], search_keyword)

            # 2. 검색 키워드에서 목표 카테고리 확인
            target_category = KEYWORD_CATEGORY_MAP.get(search_keyword, None)

            # 3. 목표 카테고리와 실제 카테고리 검증
            # 허용 카테고리 목록 (경제 카테고리 활성화 여부에 따라)
            allowed_categories = ["연애", "스포츠"]
            if ENABLE_ECONOMY_CATEGORY:
                allowed_categories.append("경제")

            if target_category:
                # 목표 카테고리가 있는 경우
                if actual_category != target_category:
                    if SKIP_MISMATCHED_CATEGORY:
                        # 불일치 시 건너뛰기
                        skipped_mismatch_count += 1
                        print(f"[SKIP] 건너뛰기: {result['title'][:35]}... (목표={target_category}, 실제={actual_category})")
                        continue
                    else:
                        # 경고만 출력하고 저장 (기존 동작)
                        category_mismatch_count += 1
                        print(f"[WARN] 카테고리 불일치 (저장 진행): {result['title'][:40]}...")
                        print(f"   목표={target_category}, 실제={actual_category}")
                category = target_category
            else:
                # 목표 카테고리가 없으면 실제 카테고리 사용
                if actual_category in allowed_categories:
                    category = actual_category
                else:
                    # 키워드에서 추론
                    if search_keyword:
                        if any(kw in search_keyword for kw in ["연애", "연예", "커플", "결혼", "데이트"]):
                            category = "연애"
                        elif any(kw in search_keyword for kw in ["스포츠", "야구", "축구", "농구", "손흥민", "이강인", "K리그", "프로야구"]):
                            category = "스포츠"
                        elif ENABLE_ECONOMY_CATEGORY and any(kw in search_keyword for kw in ["주식", "부동산", "금리", "환율", "경제", "금융", "투자", "코스피"]):
                            category = "경제"
                        else:
                            category = "연애"  # 기본값
                    else:
                        category = "연애"  # 기본값

            # 카테고리별로 그룹화
            if category in news_by_category:
                news_by_category[category].append(result)
        
        # 모든 뉴스를 하나의 리스트로 합치기
        all_news_for_shuffle = []
        for cat in news_by_category.keys():
            all_news_for_shuffle.extend(news_by_category[cat])

        # 건너뛴 뉴스 통계 출력
        if skipped_mismatch_count > 0:
            print(f"\n[SKIP] 카테고리 불일치로 건너뛴 뉴스: {skipped_mismatch_count}개")

        # 랜덤하게 섞기
        print(f"\n[SHUFFLE] 업로드 순서 랜덤 섞는 중... (완전 랜덤)")
        random.shuffle(all_news_for_shuffle)

        # 목표 개수만큼만 선택
        shuffled_news_results = all_news_for_shuffle[:target_count]

        # 카테고리별 통계 계산
        shuffle_stats = {"연애": 0, "스포츠": 0}
        if ENABLE_ECONOMY_CATEGORY:
            shuffle_stats["경제"] = 0
        for r in shuffled_news_results:
            kw = r.get('_search_keyword', '')
            cat = KEYWORD_CATEGORY_MAP.get(kw, classify_news_category(r['title'], r.get('description', ''), r.get('content', ''), kw))
            if cat in shuffle_stats:
                shuffle_stats[cat] += 1

        print(f"   [OK] 섞기 완료: 총 {len(shuffled_news_results)}개")
        print(f"      - 연애: {shuffle_stats['연애']}개")
        print(f"      - 스포츠: {shuffle_stats['스포츠']}개")
        if ENABLE_ECONOMY_CATEGORY:
            print(f"      - 경제: {shuffle_stats['경제']}개")

        # 카테고리 분류 및 데이터 준비 (배치 저장)
        print(f"\n[STAT] 데이터 준비 중... (목표: {target_count}개)")
        count = 0
        category_stats = {"연애": 0, "스포츠": 0}
        if ENABLE_ECONOMY_CATEGORY:
            category_stats["경제"] = 0
        rows_to_save = []  # 배치 저장을 위한 데이터 리스트

        for idx, result in enumerate(shuffled_news_results, 1):
            # 목표 개수에 도달했으면 중단
            if count >= target_count:
                print(f"\n[OK] 목표 개수({target_count}개) 달성! 저장 중단")
                break
            # 카테고리 자동 분류 (분류 함수로 실제 카테고리 확인)
            search_keyword = result.get('_search_keyword', '')

            # 1. 분류 함수로 실제 카테고리 확인 (검색 키워드 전달)
            actual_category = classify_news_category(result['title'], result['description'], result['content'], search_keyword)

            # 2. 검색 키워드에서 목표 카테고리 확인
            target_category = KEYWORD_CATEGORY_MAP.get(search_keyword, None)

            # 3. 카테고리 결정 (이미 필터링된 데이터이므로 간소화)
            # 허용 카테고리 목록
            allowed_categories = ["연애", "스포츠"]
            if ENABLE_ECONOMY_CATEGORY:
                allowed_categories.append("경제")

            if target_category:
                category = target_category
            elif actual_category in allowed_categories:
                category = actual_category
            else:
                # 키워드에서 추론
                if any(kw in search_keyword for kw in ["연애", "연예", "커플", "결혼", "데이트"]):
                    category = "연애"
                elif any(kw in search_keyword for kw in ["스포츠", "야구", "축구", "농구", "손흥민", "이강인", "K리그", "프로야구"]):
                    category = "스포츠"
                elif ENABLE_ECONOMY_CATEGORY and any(kw in search_keyword for kw in ["주식", "부동산", "금리", "환율", "경제", "금융", "투자", "코스피"]):
                    category = "경제"
                else:
                    category = "연애"  # 기본값
            
            # 카테고리 통계 업데이트 (연애/스포츠만)
            if category in category_stats:
                category_stats[category] = category_stats.get(category, 0) + 1
            
            # 데이터 수집 (나중에 배치 저장)
            rows_to_save.append([
                result['title'],      # A열: 제목
                result['content'],    # B열: 본문
                result['link'],       # C열: 링크
                category              # D열: 카테고리
            ])
            count += 1
            print(f"[OK] [{category}] {idx}/{len(news_results)} 준비 완료: {result['title'][:30]}...")

        # 배치 저장 (API 호출 최소화)
        print(f"\n[UPLOAD] 구글 시트 배치 저장 중... (총 {len(rows_to_save)}개)")

        if rows_to_save:
            BATCH_SIZE = 10  # 한 번에 10개씩 저장
            saved_count = 0

            for batch_start in range(0, len(rows_to_save), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(rows_to_save))
                batch = rows_to_save[batch_start:batch_end]
                batch_num = (batch_start // BATCH_SIZE) + 1
                total_batches = (len(rows_to_save) + BATCH_SIZE - 1) // BATCH_SIZE

                retry_count = 0
                max_retries = 5

                while retry_count < max_retries:
                    try:
                        # 배치 저장 (append_rows 사용)
                        sheet.append_rows(batch, value_input_option='RAW')
                        saved_count += len(batch)
                        print(f"   [OK] 배치 {batch_num}/{total_batches} 저장 완료 ({len(batch)}개, 총 {saved_count}/{len(rows_to_save)}개)")
                        
                        # 데이터베이스에도 저장
                        try:
                            from utils.database import save_news
                            for row in batch:
                                save_news(
                                    title=row[0],
                                    content=row[1],
                                    link=row[2],
                                    category=row[3] if len(row) > 3 else "미분류"
                                )
                        except Exception as db_err:
                            print(f"   [WARN] DB 저장 실패: {db_err}")

                        # 배치 간 딜레이 (5초)
                        if batch_end < len(rows_to_save):
                            print(f"   ⏳ 5초 대기 중... (API 제한 방지)")
                            time.sleep(5)
                        break

                    except Exception as e:
                        error_msg = str(e)
                        retry_count += 1

                        if "429" in error_msg or "quota" in error_msg.lower():
                            wait_time = 30 * retry_count  # 지수 백오프 (30, 60, 90, 120, 150초)
                            print(f"   [WARN] API 할당량 초과, {wait_time}초 대기 후 재시도... ({retry_count}/{max_retries})")
                            time.sleep(wait_time)
                        elif "403" in error_msg or "permission" in error_msg.lower():
                            print(f"   [ERROR] 권한 오류! 서비스 계정에 시트 공유 필요")
                            print(f"   [EMAIL] 이메일: storium@swift-radar-467217-p0.iam.gserviceaccount.com")
                            break
                        else:
                            wait_time = 10 * retry_count
                            print(f"   [WARN] 저장 오류: {error_msg[:50]}...")
                            print(f"   {wait_time}초 대기 후 재시도... ({retry_count}/{max_retries})")
                            time.sleep(wait_time)

                if retry_count >= max_retries:
                    print(f"   [ERROR] 배치 {batch_num} 저장 실패 (최대 재시도 횟수 초과)")

            count = saved_count

        print(f"\n" + "="*60)
        print(f" [완료] 수집 완료 요약")
        print("="*60)
        print(f" 목표: {target_count}개 / 저장: {count}개")
        if count < target_count:
            print(f" [경고] 목표 미달성 ({target_count - count}개 부족)")
        print(f" 총 검색 결과: {len(all_news_items)}개")

        # 카테고리별 통계
        print(f"\n [카테고리별 저장 현황]")
        for cat, num in category_stats.items():
            print(f"    - {cat}: {num}개")

        # 건너뛰기/불일치 통계
        print(f"\n [품질 관리 통계]")
        if SKIP_MISMATCHED_CATEGORY:
            print(f"    - 건너뛴 뉴스 (카테고리 불일치): {skipped_mismatch_count}개")
        else:
            print(f"    - 카테고리 불일치 경고: {category_mismatch_count}개 (저장됨)")

        # 설정 현황
        print(f"\n [현재 설정]")
        print(f"    - 불일치 건너뛰기: {'활성화' if SKIP_MISMATCHED_CATEGORY else '비활성화'}")
        print(f"    - 경제 카테고리: {'활성화' if ENABLE_ECONOMY_CATEGORY else '비활성화'}")
        print("="*60)
    else:
        print("[ERROR] 네이버 검색 결과가 없습니다.")

if __name__ == "__main__":
    main()

