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

    # 디버깅: 환경 변수 로깅 (자세한 정보)
    if not supabase_url:
        logger.error("❌ SUPABASE_URL 환경 변수가 설정되지 않았습니다!")
    else:
        logger.info(f"✅ SUPABASE_URL 로드됨: {supabase_url[:50]}...")
        logger.info(f"   URL 길이: {len(supabase_url)} chars")
    
    if not service_key:
        logger.error("❌ SUPABASE_SERVICE_KEY 또는 SUPABASE_ANON_KEY가 설정되지 않았습니다!")
    else:
        logger.info(f"✅ Service Key 로드됨: {service_key[:50]}...")
        logger.info(f"   Key 길이: {len(service_key)} chars")
        # JWT 토큰 형식 확인 (3개 부분으로 나뉘어야 함)
        key_parts = service_key.split('.')
        logger.info(f"   JWT 부분 수: {len(key_parts)} (정상: 3)")

    if not supabase_url or not service_key:
        return None

    try:
        logger.info(f"🔄 create_client() 호출 중... URL: {supabase_url}, Key length: {len(service_key)}")
        client = create_client(supabase_url, service_key)
        logger.info("✅ Supabase Admin 클라이언트 생성 성공")
        return client
    except Exception as e:
        logger.error(f"❌ Supabase Admin 클라이언트 생성 실패: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        logger.error(f"   URL를 다시 확인: {supabase_url}")
        logger.error(f"   Key 길이를 다시 확인: {len(service_key) if service_key else 'None'}")
        return None
