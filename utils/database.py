# -*- coding: utf-8 -*-
"""
데이터베이스 유틸리티 모듈
PostgreSQL 데이터베이스 연결 및 뉴스 데이터 관리
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import List, Dict, Optional, Any

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    """데이터베이스 연결 반환"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    return psycopg2.connect(DATABASE_URL)

def init_database():
    """데이터베이스 테이블 초기화"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            link TEXT UNIQUE,
            category VARCHAR(50),
            search_keyword VARCHAR(100),
            source VARCHAR(100),
            ai_title TEXT,
            ai_content TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            prompt_text TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_status ON news(status)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at DESC)
    """)
    
    conn.commit()
    cur.close()
    conn.close()

def save_news(title: str, content: str, link: str, category: str, source: str = "네이버뉴스", search_keyword: str = None) -> Optional[int]:
    """뉴스 저장
    
    Args:
        title: 뉴스 제목
        content: 뉴스 본문
        link: 뉴스 링크
        category: 대분류 카테고리 (연애/경제/스포츠)
        source: 출처
        search_keyword: 검색에 사용된 키워드
    """
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO news (title, content, link, category, search_keyword, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (link) DO NOTHING
            RETURNING id
        """, (title, content, link, category, search_keyword, source))
        
        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        print(f"[DB ERROR] 뉴스 저장 실패: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_news_list(category: str = None, status: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
    """뉴스 목록 조회"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = "SELECT * FROM news WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = %s"
        params.append(category)
    if status:
        query += " AND status = %s"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cur.execute(query, params)
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def get_news_count(category: str = None, status: str = None) -> int:
    """뉴스 개수 조회"""
    conn = get_connection()
    cur = conn.cursor()
    
    query = "SELECT COUNT(*) FROM news WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = %s"
        params.append(category)
    if status:
        query += " AND status = %s"
        params.append(status)
    
    cur.execute(query, params)
    count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return count

def update_news_status(news_id: int, status: str):
    """뉴스 상태 업데이트"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE news SET status = %s, uploaded_at = CASE WHEN %s = 'uploaded' THEN CURRENT_TIMESTAMP ELSE uploaded_at END
        WHERE id = %s
    """, (status, status, news_id))
    
    conn.commit()
    cur.close()
    conn.close()

def save_prompt(name: str, category: str, prompt_text: str) -> int:
    """프롬프트 저장"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO prompts (name, category, prompt_text)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (name, category, prompt_text))
    
    result = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    return result

def get_prompts(category: str = None, active_only: bool = True) -> List[Dict]:
    """프롬프트 목록 조회"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = "SELECT * FROM prompts WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = %s"
        params.append(category)
    if active_only:
        query += " AND is_active = TRUE"
    
    query += " ORDER BY created_at DESC"
    
    cur.execute(query, params)
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def update_prompt(prompt_id: int, name: str = None, prompt_text: str = None, is_active: bool = None):
    """프롬프트 업데이트"""
    conn = get_connection()
    cur = conn.cursor()
    
    updates = []
    params = []
    
    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if prompt_text is not None:
        updates.append("prompt_text = %s")
        params.append(prompt_text)
    if is_active is not None:
        updates.append("is_active = %s")
        params.append(is_active)
    
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(prompt_id)
        
        cur.execute(f"""
            UPDATE prompts SET {', '.join(updates)}
            WHERE id = %s
        """, params)
        
        conn.commit()
    
    cur.close()
    conn.close()

def delete_prompt(prompt_id: int):
    """프롬프트 삭제"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM prompts WHERE id = %s", (prompt_id,))
    
    conn.commit()
    cur.close()
    conn.close()

def get_news_stats() -> Dict[str, Any]:
    """뉴스 통계 조회"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as uploaded,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
        FROM news
    """)
    stats = dict(cur.fetchone())
    
    cur.execute("""
        SELECT category, COUNT(*) as count 
        FROM news 
        GROUP BY category 
        ORDER BY count DESC
    """)
    stats['by_category'] = [dict(row) for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return stats
