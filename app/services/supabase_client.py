import os
import sys
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# .env 로드
load_dotenv()


def get_supabase_client() -> Client | None:
    """
    일반 사용자용 supabase-py 클라이언트를 생성합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.")
        return None

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Supabase 클라이언트 생성 실패: {e}")
        return None


def get_supabase_admin_client() -> Client | None:
    """
    관리자 권한용 supabase-py 클라이언트를 생성합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not service_key:
        return None

    try:
        return create_client(supabase_url, service_key)
    except Exception as e:
        logger.error(f"Supabase Admin 클라이언트 생성 실패: {e}")
        return None
