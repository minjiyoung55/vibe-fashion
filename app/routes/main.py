import os
import sys
import logging
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
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


def get_supabase_admin_client() -> Client | None:
    """
    .env 환경 변수(SUPABASE_URL, SUPABASE_SERVICE_KEY)를 읽어
    회원 생성 및 관리자 권한용 supabase-py 클라이언트를 초기화합니다.
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


def _process_product_item(item: dict) -> dict:
    """상품 딕셔너리 데이터를 템플릿 표시용 데이터로 변환합니다."""
    images = item.get("product_images") or []
    images.sort(key=lambda x: x.get("display_order", 0))

    thumbnail_url = item.get("thumbnail_url")
    if not thumbnail_url:
        for img in images:
            if img.get("is_thumbnail"):
                thumbnail_url = img.get("image_url")
                break
        if not thumbnail_url and images:
            thumbnail_url = images[0].get("image_url")
    if not thumbnail_url:
        thumbnail_url = "https://picsum.photos/seed/vibe-product/600/700"

    raw_price = float(item.get("price") or 0)
    discount_rate = float(item.get("discount_rate") or 0)
    if discount_rate > 0:
        real_price = raw_price * (1 - discount_rate / 100)
        formatted_price = f"{int(round(real_price)):,}원"
        formatted_original_price = f"{int(raw_price):,}원"
    else:
        formatted_price = f"{int(raw_price):,}원"
        formatted_original_price = formatted_price

    category_info = item.get("categories") or {}
    category_name = category_info.get("name") if isinstance(category_info, dict) else ""

    # NEW / BEST 뱃지 지정
    badge = ""
    if category_name in ("NEW", "신상품"):
        badge = "NEW"
    elif category_name in ("BEST", "베스트"):
        badge = "BEST"

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "description": item.get("description") or "",
        "raw_price": int(raw_price),
        "price": formatted_price,
        "formatted_price": formatted_price,
        "formatted_original_price": formatted_original_price,
        "discount_rate": discount_rate,
        "thumbnail_url": thumbnail_url,
        "category": category_name,
        "badge": badge,
        "images": images,
    }


@bp.route("/")
def index():
    """
    쇼핑몰 메인 페이지 라우트입니다.
    Supabase products 테이블에서 추천 상품 및 카테고리별 목록을 조회합니다.
    """
    products = []
    categories = []

    try:
        supabase = get_supabase_client()
        if supabase:
            # 1. 활성화된 카테고리 목록 조회
            try:
                cat_res = supabase.table("categories").select("*").eq("is_active", True).order("id").execute()
                categories = cat_res.data or []
            except Exception as e:
                logger.error(f"카테고리 목록 조회 실패: {e}")

            # 2. 추천 상품 조회 (is_featured=True, 최대 12개)
            query = (
                supabase.table("products")
                .select("*, product_images(image_url, is_thumbnail, display_order), categories(name, slug)")
                .eq("is_featured", True)
                .order("created_at", desc=False)
                .limit(12)
            )
            response = query.execute()
            raw_products = response.data or []

            for item in raw_products:
                products.append(_process_product_item(item))
    except Exception as e:
        print(f"[Supabase Error] 상품 목록 조회 실패: {e}", file=sys.stderr)
        logger.error(f"Supabase 상품 목록 조회 실패: {e}")
        products = []

    return render_template("index.html", products=products, categories=categories, current_category=None)


@bp.route("/category/<slug>")
def category_products(slug: str):
    """
    카테고리별 상품 목록 페이지 라우트입니다. (new, best 등)
    """
    products = []
    categories = []
    target_category = None

    try:
        supabase = get_supabase_client()
        if supabase:
            # 1. 카테고리 목록 조회
            cat_res = supabase.table("categories").select("*").eq("is_active", True).order("id").execute()
            categories = cat_res.data or []

            # 2. 선택된 카테고리 정보 조회
            for c in categories:
                if c.get("slug") == slug:
                    target_category = c
                    break

            if target_category:
                # 3. 해당 카테고리에 속한 상품 조회
                p_res = (
                    supabase.table("products")
                    .select("*, product_images(image_url, is_thumbnail, display_order), categories(name, slug)")
                    .eq("category_id", target_category["id"])
                    .order("created_at", desc=True)
                    .execute()
                )
                for item in p_res.data or []:
                    products.append(_process_product_item(item))
    except Exception as e:
        logger.error(f"카테고리 상품 목록 조회 실패: {e}")

    return render_template(
        "index.html",
        products=products,
        categories=categories,
        current_category=target_category,
    )


@bp.route("/api/chat", methods=["POST"])
def chat_api():
    """
    실시간 고객 문의 챗봇 API입니다.
    사용자의 질문 키워드를 분석하여 친절하고 정확한 자동 응답을 반환합니다.
    """
    from flask import request, jsonify

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"reply": "문의 내용을 입력해 주세요."}), 400

    msg_lower = message.lower()

    # 1. 배송 / 배송비 문의
    if any(k in msg_lower for k in ["배송", "택배", "언제 와", "출고", "도착"]):
        reply = (
            "🚚 **배송 안내입니다!**\n"
            "- 평일 오후 2시 이전 결제 완료 시 **당일 출고**됩니다.\n"
            "- 기본 배송비는 3,000원이며, **50,000원 이상 구매 시 무료 배송** 혜택을 드립니다.\n"
            "- 출고 후 평균 1~2영업일 내에 받아보실 수 있습니다."
        )
    # 2. 반품 / 교환 / 환불 문의
    elif any(k in msg_lower for k in ["반품", "교환", "환불", "취소"]):
        reply = (
            "🔄 **반품 및 교환 안내입니다!**\n"
            "- 상품 수령 후 **7일 이내**에 고객센터 또는 마이페이지를 통해 신청 가능합니다.\n"
            "- 단순 변심의 경우 왕복 배송비 6,000원이 부과될 수 있습니다.\n"
            "- 착용 흔적, 라벨/택 훼손이 없는 상태에서 가능합니다."
        )
    # 3. 상품 추천 / 신상품 / 베스트 문의
    elif any(k in msg_lower for k in ["추천", "베스트", "인기", "신상품", "신상", "new", "best", "어떤게 좋아"]):
        reply = (
            "✨ **MD 추천 아이템을 소개해 드려요!**\n"
            "- **BEST**: 우아한 실루엣의 '플로럴 미디 원피스'와 '클래식 하얀색 진주목걸이'가 큰 사랑을 받고 있어요.\n"
            "- **NEW**: 올 시즌 신상 '클래식 V넥 니트 베스트'와 '빈티지 레오파드 호피 안경'을 확인해 보세요!"
        )
    # 4. 사이즈 / 소재 / 세탁 문의
    elif any(k in msg_lower for k in ["사이즈", "치수", "소재", "원단", "세탁"]):
        reply = (
            "📏 **사이즈 & 관리 안내입니다!**\n"
            "- 각 상품 상세페이지 하단에서 실측 사이즈표를 확인하실 수 있습니다.\n"
            "- 니트나 원피스는 첫 세탁 시 드라이클리닝을 권장합니다.\n"
            "- 특정 상품의 상세 치수가 궁금하시면 상품명을 알려주세요!"
        )
    # 5. 고객센터 운영 시간 / 전화번호 문의
    elif any(k in msg_lower for k in ["고객센터", "전화", "연락처", "상담원", "시간", "운영"]):
        reply = (
            "📞 **고객센터 운영 안내입니다!**\n"
            "- 운영 시간: 평일 10:00 ~ 18:00 (점심시간 12:30 ~ 13:30 / 주말 및 공휴일 휴무)\n"
            "- 대표 전화: 1588-0000\n"
            "- 이메일: support@vibefashion.com"
        )
    # 6. 할인 / 쿠폰 / 이벤트 문의
    elif any(k in msg_lower for k in ["할인", "쿠폰", "이벤트", "적립금", "포인트", "세일", "회원가입"]):
        reply = (
            "🎁 **회원가입 특별 혜택 안내입니다!**\n"
            "- 지금 무료 회원가입을 하시면 **적립금 2,000원**을 즉시 지급해 드립니다!\n"
            "- 상단 [회원가입] 버튼을 눌러 이메일과 비밀번호만 입력하면 3초 만에 가입 완료!\n"
            "- 이달의 추천 아이템 컬렉션에서 적립금과 함께 알뜰하게 쇼핑해 보세요."
        )
    # 기본 안내 응답
    else:
        reply = (
            f"문의해 주셔서 감사합니다! 😊\n"
            f"입력하신 내용('{message}')에 대해 담당 상담원 연결이 필요하신가요?\n\n"
            f"👉 **빠른 답변 키워드**: [적립금/회원가입], [배송], [반품/교환], [추천 상품], [고객센터]\n"
            f"더 구체적인 도움이 필요하시면 언제든 남겨주세요!"
        )

    return jsonify({"reply": reply})


# ==============================================================
# 회원가입 / 로그인 / 로그아웃 인증 라우트 (적립금 2,000원 지급)
# ==============================================================

@bp.route("/api/signup", methods=["POST"])
def api_signup():
    """
    회원가입 API:
    - 신규 회원 등록 시 축하 적립금 2,000원(points: 2000)을 자동으로 지급합니다.
    - 가입 즉시 세션 로그인 처리하여 바로 적립금을 확인할 수 있도록 합니다.
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    full_name = (data.get("full_name") or "").strip() or email.split("@")[0]

    if not email or not password:
        return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해 주세요."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "비밀번호는 최소 6자 이상이어야 합니다."}), 400

    try:
        admin_supabase = get_supabase_admin_client()
        if not admin_supabase:
            return jsonify({"success": False, "message": "서버 인증 설정이 올바르지 않습니다."}), 500

        INITIAL_WELCOME_POINTS = 2000

        # Supabase 관리자 API로 이메일 즉시 인증 완료된 사용자 생성 (적립금 2,000원 부여)
        user_res = admin_supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name,
                "points": INITIAL_WELCOME_POINTS
            }
        })

        if not user_res.user:
            return jsonify({"success": False, "message": "회원가입 처리에 실패했습니다."}), 400

        user = user_res.user

        # profiles 테이블에도 기본 정보 동기화 (오류 무시)
        try:
            admin_supabase.table("profiles").upsert({
                "id": user.id,
                "email": email,
                "full_name": full_name,
                "role": "CUSTOMER",
                "customer_grade": "BRONZE",
                "total_order_amount": 0
            }).execute()
        except Exception as pe:
            logger.warning(f"Profile upsert warning: {pe}")

        # 세션에 로그인 정보 저장
        session["user_id"] = user.id
        session["user_email"] = email
        session["user_name"] = full_name
        session["user_points"] = INITIAL_WELCOME_POINTS

        return jsonify({
            "success": True,
            "message": f"🎉 회원가입을 축하합니다! 신규 회원 축하 적립금 {INITIAL_WELCOME_POINTS:,}원이 지급되었습니다.",
            "points": INITIAL_WELCOME_POINTS,
            "user": {
                "id": user.id,
                "email": email,
                "full_name": full_name,
                "points": INITIAL_WELCOME_POINTS
            }
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"회원가입 에러: {error_msg}")
        if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            return jsonify({"success": False, "message": "이미 등록된 이메일 주소입니다. 로그인을 이용해 주세요."}), 400
        return jsonify({"success": False, "message": f"회원가입 중 오류가 발생했습니다: {error_msg}"}), 500


@bp.route("/api/login", methods=["POST"])
def api_login():
    """회원 로그인 API: 로그인 성공 시 세션에 유저 정보와 적립금을 저장합니다."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "이메일과 비밀번호를 입력해 주세요."}), 400

    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({"success": False, "message": "서버 연결에 실패했습니다."}), 500

        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not res.user:
            return jsonify({"success": False, "message": "이메일 또는 비밀번호가 일치하지 않습니다."}), 400

        user = res.user
        metadata = user.user_metadata or {}
        points = metadata.get("points", 2000)
        full_name = metadata.get("full_name") or email.split("@")[0]

        session["user_id"] = user.id
        session["user_email"] = email
        session["user_name"] = full_name
        session["user_points"] = points

        return jsonify({
            "success": True,
            "message": f"환영합니다, {full_name}님! (보유 적립금: {points:,}원)",
            "points": points,
            "user": {
                "id": user.id,
                "email": email,
                "full_name": full_name,
                "points": points
            }
        })

    except Exception as e:
        logger.error(f"로그인 에러: {e}")
        return jsonify({"success": False, "message": "이메일 또는 비밀번호가 올바르지 않습니다."}), 400


@bp.route("/api/logout", methods=["POST"])
def api_logout():
    """로그아웃 API: 세션을 초기화합니다."""
    session.clear()
    return jsonify({"success": True, "message": "로그아웃되었습니다."})


@bp.route("/api/me", methods=["GET"])
def api_me():
    """현재 로그인된 회원 정보 및 적립금을 조회합니다."""
    if "user_id" in session:
        return jsonify({
            "is_logged_in": True,
            "user": {
                "id": session.get("user_id"),
                "email": session.get("user_email"),
                "name": session.get("user_name"),
                "points": session.get("user_points", 2000)
            }
        })
    return jsonify({"is_logged_in": False})


@bp.route("/products/<product_id>")
def product_detail(product_id: str):
    """
    상품 상세 페이지 라우트입니다.
    상품 ID를 기반으로 Supabase에서 상품 상세 정보, 옵션, 이미지를 조회하여 표시합니다.
    """
    product = None

    try:
        supabase = get_supabase_client()
        if supabase:
            # 상품 정보 조회 (카테고리 및 관련 이미지 포함)
            response = (
                supabase.table("products")
                .select("*, categories(name), product_images(image_url, display_order, is_thumbnail)")
                .eq("id", product_id)
                .single()
                .execute()
            )
            item = response.data

            if item:
                # 상품 옵션 조회
                options_res = (
                    supabase.table("product_options")
                    .select("*")
                    .eq("product_id", product_id)
                    .execute()
                )
                options = options_res.data or []

                # 이미지 목록 정리 (display_order 기준 정렬)
                images = item.get("product_images") or []
                images.sort(key=lambda x: x.get("display_order", 0))

                thumbnail_url = item.get("thumbnail_url")
                if not thumbnail_url:
                    for img in images:
                        if img.get("is_thumbnail"):
                            thumbnail_url = img.get("image_url")
                            break
                    if not thumbnail_url and images:
                        thumbnail_url = images[0].get("image_url")
                if not thumbnail_url:
                    thumbnail_url = "https://picsum.photos/seed/vibe-product/600/700"

                # 가격 및 할인율 계산
                raw_price = float(item.get("price") or 0)
                discount_rate = float(item.get("discount_rate") or 0)
                if discount_rate > 0:
                    real_price = raw_price * (1 - discount_rate / 100)
                    formatted_price = f"{int(round(real_price)):,}원"
                    formatted_original_price = f"{int(raw_price):,}원"
                else:
                    formatted_price = f"{int(raw_price):,}원"
                    formatted_original_price = formatted_price

                category_info = item.get("categories") or {}
                category_name = category_info.get("name") if isinstance(category_info, dict) else ""

                product = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description") or "",
                    "raw_price": int(raw_price),
                    "formatted_price": formatted_price,
                    "formatted_original_price": formatted_original_price,
                    "discount_rate": discount_rate,
                    "thumbnail_url": thumbnail_url,
                    "category": category_name,
                    "images": images,
                    "options": options,
                }
    except Exception as e:
        print(f"[Supabase Error] 상품 상세 조회 실패: {e}", file=sys.stderr)
        logger.error(f"상품 상세 조회 실패: {e}")

    if not product:
        # 상품을 찾을 수 없는 경우
        return render_template(
            "index.html",
            products=[],
            error_message="요청하신 상품을 찾을 수 없습니다."
        ), 404

    return render_template("product_detail.html", product=product)


