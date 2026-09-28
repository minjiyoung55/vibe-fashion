import os
import sys
import logging
from flask import Blueprint, render_template
from dotenv import load_dotenv
from supabase import create_client, Client

# 로깅 설정
logger = logging.getLogger(__name__)

# .env 파일에서 환경 변수 로드
load_dotenv()

# 'main' 블루프린트 생성
bp = Blueprint("main", __name__)


def get_supabase_client() -> Client | None:
    """
    .env 환경 변수(SUPABASE_URL, SUPABASE_ANON_KEY)를 읽어
    supabase-py 클라이언트를 초기화합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        print("[Supabase Error] SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.", file=sys.stderr)
        logger.error("SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.")
        return None

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"[Supabase Error] Supabase 클라이언트 연결 실패: {e}", file=sys.stderr)
        logger.error(f"Supabase 클라이언트 생성 실패: {e}")
        return None


@bp.route("/")
def index():
    """
    쇼핑몰 메인 페이지 라우트입니다.
    Supabase products 테이블에서 is_active=true, is_featured=true인 상품 최대 4개를 조회하여 템플릿에 전달합니다.
    연결 실패 또는 오류 시 빈 리스트로 안전하게 대체하여 앱이 중단되지 않도록 합니다.
    """
    products = []

    try:
        supabase = get_supabase_client()
        if supabase:
            # is_active=True, is_featured=True 조건으로 최대 4개 상품 조회
            try:
                query = (
                    supabase.table("products")
                    .select("*, product_images(image_url, is_thumbnail), categories(name)")
                    .eq("is_active", True)
                    .eq("is_featured", True)
                    .limit(4)
                )
                response = query.execute()
                raw_products = response.data or []
            except Exception as q_err:
                # DB에 is_active 컬럼이 없는 경우 대비한 fallback
                print(f"[Supabase Notice] is_active 쿼리 실패, is_featured 조건으로 재시도: {q_err}", file=sys.stderr)
                query = (
                    supabase.table("products")
                    .select("*, product_images(image_url, is_thumbnail), categories(name)")
                    .eq("is_featured", True)
                    .limit(4)
                )
                response = query.execute()
                raw_products = response.data or []

            # 데이터 가공: 가격 포맷팅('{:,}원') 및 thumbnail_url 추출
            for item in raw_products:
                # 썸네일 이미지 추출 (직접 thumbnail_url 컬럼 -> product_images 연관 테이블 -> 기본 이미지)
                thumbnail_url = item.get("thumbnail_url")
                if not thumbnail_url:
                    images = item.get("product_images") or []
                    for img in images:
                        if img.get("is_thumbnail"):
                            thumbnail_url = img.get("image_url")
                            break
                    if not thumbnail_url and images:
                        thumbnail_url = images[0].get("image_url")
                if not thumbnail_url:
                    thumbnail_url = "https://picsum.photos/seed/vibe-product/600/700"

                # 가격 포맷팅 (예: 19,900원)
                raw_price = item.get("price") or 0
                try:
                    formatted_price = f"{int(float(raw_price)):,}원"
                except (ValueError, TypeError):
                    formatted_price = f"{raw_price}원"

                category_info = item.get("categories") or {}
                category_name = category_info.get("name") if isinstance(category_info, dict) else ""

                products.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description") or "",
                    "price": formatted_price,
                    "thumbnail_url": thumbnail_url,
                    "category": category_name,
                })
    except Exception as e:
        # Supabase 연결 실패 또는 오류 시 터미널 에러 로그 출력 및 빈 리스트 대체
        print(f"[Supabase Error] 상품 목록 조회 실패: {e}", file=sys.stderr)
        logger.error(f"Supabase 상품 목록 조회 실패: {e}")
        products = []

    return render_template("index.html", products=products)


