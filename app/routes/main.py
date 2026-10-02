import os
import sys
import logging
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from dotenv import load_dotenv
from app.services.supabase_client import get_supabase_client, get_supabase_admin_client

# 로깅 설정
logger = logging.getLogger(__name__)

# .env 파일에서 환경 변수 로드
load_dotenv()

# 'main' 블루프린트 생성
bp = Blueprint("main", __name__)


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

    # NEW / BEST / 오늘출발 뱃지 지정
    badge = ""
    if category_name in ("NEW", "신상품"):
        badge = "NEW"
    elif category_name in ("BEST", "베스트"):
        badge = "BEST"
    elif category_name in ("오늘출발", "당일발송"):
        badge = "오늘출발"

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


@bp.route("/api/reviews", methods=["POST"])
def api_create_review():
    """
    상품 사진 후기 등록 API:
    - 로그인한 회원이 작성하거나, 비로그인 시 기본 작성자 계정으로 후기 등록
    - 등록 즉시 리뷰 작성 축하 적립금 500원 추가 지급!
    """
    data = request.get_json() or {}
    product_id = data.get("product_id")
    rating = int(data.get("rating") or 5)
    content = (data.get("content") or "").strip()
    image_url = (data.get("image_url") or "").strip()

    if not product_id or not content:
        return jsonify({"success": False, "message": "상품 정보와 후기 내용을 입력해 주세요."}), 400

    try:
        admin_supabase = get_supabase_admin_client()
        if not admin_supabase:
            return jsonify({"success": False, "message": "서버 인증 설정이 올바르지 않습니다."}), 500

        # 작성자 user_id 결정 (로그인 유저 또는 서포터 계정)
        user_id = session.get("user_id")
        user_name = session.get("user_name") or "구매고객"

        if not user_id:
            reviewer_email = "reviewer@vibefashion.com"
            users = admin_supabase.auth.admin.list_users()
            author_user = next((u for u in users if u.email == reviewer_email), None)
            if not author_user:
                author_user = admin_supabase.auth.admin.create_user({
                    "email": reviewer_email,
                    "password": "ReviewerPassword2026!",
                    "email_confirm": True,
                    "user_metadata": {"full_name": "구매고객"}
                }).user
            user_id = author_user.id

        # reviews 테이블에 등록
        review_data = {
            "product_id": product_id,
            "user_id": user_id,
            "rating": rating,
            "content": content,
            "image_url": image_url or "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=800&q=80"
        }
        ins_res = admin_supabase.table("reviews").insert(review_data).execute()

        # 로그인 사용자라면 리뷰 작성 적립금 500원 추가 적립
        if "user_id" in session:
            current_points = int(session.get("user_points", 2000)) + 500
            session["user_points"] = current_points
            try:
                admin_supabase.auth.admin.update_user_by_id(
                    session["user_id"],
                    {"user_metadata": {"points": current_points, "full_name": session.get("user_name")}}
                )
            except Exception as ue:
                logger.warning(f"Failed to update user points: {ue}")

        return jsonify({
            "success": True,
            "message": "소중한 사진 후기가 등록되었습니다! (포토 후기 적립금 +500P 적립)",
            "review": ins_res.data[0] if ins_res.data else None
        })

    except Exception as e:
        logger.error(f"리뷰 등록 실패: {e}")
        return jsonify({"success": False, "message": f"후기 등록에 실패했습니다: {e}"}), 500


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
                # 상품 옵션 조회 (Day 5 색상/사이즈 조합 옵션 포함)
                options_res = (
                    supabase.table("product_options")
                    .select("*")
                    .eq("product_id", product_id)
                    .order("id")
                    .execute()
                )
                options = options_res.data or []

                # 색상(color) 목록 DISTINCT 추출 (NULL 제외)
                distinct_colors = []
                seen_colors = set()
                for opt in options:
                    c = opt.get("color")
                    if c and c not in seen_colors:
                        seen_colors.add(c)
                        distinct_colors.append(c)

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
                    "colors": distinct_colors,
                }

                # 상품 사진 후기(Reviews) 목록 조회
                reviews_res = (
                    supabase.table("reviews")
                    .select("*, profiles(full_name, avatar_url)")
                    .eq("product_id", product_id)
                    .order("created_at", desc=True)
                    .execute()
                )
                reviews_data = reviews_res.data or []
                product_reviews = []
                for r in reviews_data:
                    prof = r.get("profiles") or {}
                    author = prof.get("full_name") or "구매고객"
                    # 작성일자 YYYY.MM.DD 포맷팅
                    raw_date = r.get("created_at", "")[:10].replace("-", ".")
                    product_reviews.append({
                        "id": r.get("id"),
                        "rating": r.get("rating") or 5,
                        "content": r.get("content") or "",
                        "image_url": r.get("image_url") or "",
                        "author_name": author,
                        "created_at": raw_date or "2026.09.28"
                    })

                # 평균 평점 계산
                if product_reviews:
                    avg_rating = round(sum(r["rating"] for r in product_reviews) / len(product_reviews), 1)
                else:
                    avg_rating = 5.0

                product["reviews"] = product_reviews
                product["review_count"] = len(product_reviews)
                product["avg_rating"] = avg_rating
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


# ==============================================================
# 색상별 사이즈/재고 목록 조회 API (GET /api/products/<product_id>/options?color=...)
# ==============================================================
@bp.route("/api/products/<product_id>/options")
def api_product_options_by_color(product_id: str):
    """
    선택된 색상(color)에 해당하는 사이즈(size) 및 재고(stock) 목록을 반환합니다.
    """
    color = (request.args.get("color") or "").strip()
    if not color:
        return jsonify({"sizes": []})

    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({"sizes": [], "error": "데이터베이스 연결 실패"}), 500

        res = (
            supabase.table("product_options")
            .select("id, color, size, stock, additional_price")
            .eq("product_id", product_id)
            .eq("color", color)
            .order("id")
            .execute()
        )
        sizes = res.data or []
        return jsonify({"sizes": sizes})
    except Exception as e:
        logger.error(f"색상별 사이즈 조회 실패: {e}")
        return jsonify({"sizes": [], "error": str(e)}), 500


# ==============================================================
# 색상별 사이즈 및 재고 조회 API (GET /api/products/<product_id>/sizes?color=...)
# ==============================================================
@bp.route("/api/products/<product_id>/sizes")
def api_product_sizes_by_color(product_id: str):
    """
    선택된 색상(color)에 해당하는 사이즈(size) 및 재고(stock) 목록을 반환합니다.
    응답: [{"id": "opt_id", "size": "S", "stock": 3}, {"id": "opt_id2", "size": "M", "stock": 0}, ...]
    """
    color = (request.args.get("color") or "").strip()
    if not color:
        return jsonify([])
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify([]), 500
        
        res = (
            supabase.table("product_options")
            .select("id, size, stock")
            .eq("product_id", product_id)
            .eq("color", color)
            .order("id")
            .execute()
        )
        
        options = res.data or []
        
        # 응답 형식 정리: [{"id": "opt_id", "size": "S", "stock": 3}, ...]
        result = [
            {
                "id": item.get("id"),
                "size": item.get("size"),
                "stock": int(item.get("stock") or 0)
            }
            for item in options
        ]
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"색상별 사이즈 조회 실패: {e}")
        return jsonify([]), 500


# ==============================================================
# 장바구니 담기 API (POST /cart/add)
# ==============================================================
@bp.route("/cart/add", methods=["POST"])
def cart_add():
    """
    장바구니 담기 처리:
    - 요청 body: product_option_id, quantity
    - 비로그인 시: /auth/login 으로 리다이렉트
    - 재고 검증: stock < quantity 이면 "재고가 부족합니다(현재 N개)" 에러
    - carts 테이블에 upsert (기존 수량에 누적)
    - 누적 수량이 재고를 초과하는 경우 에러 처리
    - 성공 시 JSON 반환: {"success": true, "message": "장바구니에 담겼습니다"}
    """
    user_id = session.get("user_id")

    # 로그인 검증: 비로그인 시 /auth/login 으로 리다이렉트 (JSON 또는 302 리다이렉트)
    if not user_id:
        if request.is_json:
            return jsonify({
                "success": False,
                "message": "로그인이 필요한 서비스입니다.",
                "redirect": url_for("auth.login")
            }), 401
        return redirect(url_for("auth.login"))

    # 요청 데이터 파싱 (JSON 또는 form)
    if request.is_json:
        data = request.get_json() or {}
        option_id = data.get("product_option_id")
        quantity = data.get("quantity")
    else:
        option_id = request.form.get("product_option_id")
        quantity = request.form.get("quantity")

    try:
        quantity = int(quantity or 1)
    except (ValueError, TypeError):
        quantity = 1

    if not option_id or quantity <= 0:
        return jsonify({"success": False, "message": "올바른 옵션과 수량을 선택해 주세요."}), 400

    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return jsonify({"success": False, "message": "서버 연결에 실패했습니다."}), 500

    try:
        # 1. 해당 옵션의 현재 재고(stock) 및 상품 ID 조회
        opt_res = (
            admin_sb.table("product_options")
            .select("id, product_id, stock, color, size")
            .eq("id", option_id)
            .maybe_single()
            .execute()
        )
        option = opt_res.data if opt_res else None

        if not option:
            return jsonify({"success": False, "message": "선택하신 옵션을 찾을 수 없습니다."}), 404

        current_stock = int(option.get("stock") or 0)
        product_id = option.get("product_id")

        # 2. 1차 재고 검증: 요청 수량이 현재 재고보다 많은 경우
        if current_stock < quantity:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다(현재 {current_stock}개)"
            }), 400

        # 3. 기존 장바구니에 담긴 동일 옵션 수량 확인
        cart_res = (
            admin_sb.table("carts")
            .select("id, quantity")
            .eq("user_id", user_id)
            .eq("product_id", product_id)
            .eq("option_id", option_id)
            .maybe_single()
            .execute()
        )
        existing_cart = cart_res.data if cart_res else None
        existing_qty = int(existing_cart.get("quantity") or 0) if existing_cart else 0

        total_new_qty = existing_qty + quantity

        # 4. 2차 재고 검증: 누적 수량이 재고를 초과하는 경우
        if total_new_qty > current_stock:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다(현재 {current_stock}개)"
            }), 400

        # 5. carts 테이블에 저장 (upsert: user_id, product_id, option_id 중복 시 수량 업데이트)
        upsert_payload = {
            "user_id": user_id,
            "product_id": product_id,
            "option_id": option_id,
            "quantity": total_new_qty
        }
        admin_sb.table("carts").upsert(
            upsert_payload,
            on_conflict="user_id,product_id,option_id"
        ).execute()

        # 전체 장바구니 항목 개수 조회 (헤더 배지 갱신용)
        count_res = admin_sb.table("carts").select("quantity").eq("user_id", user_id).execute()
        cart_total_count = sum(int(item.get("quantity") or 0) for item in (count_res.data or []))

        return jsonify({
            "success": True,
            "message": "장바구니에 담겼습니다",
            "cart_count": cart_total_count
        })

    except Exception as e:
        logger.error(f"장바구니 담기 실패: {e}")
        return jsonify({"success": False, "message": f"장바구니 담기 중 오류가 발생했습니다: {str(e)}"}), 500


# ==============================================================
# 장바구니 수량 변경 API (PATCH /cart/<cart_id>)
# ==============================================================
@bp.route("/cart/<int:cart_id>", methods=["PATCH"])
def cart_update_quantity(cart_id: int):
    """
    장바구니 수량 변경:
    - 요청 body: quantity (변경할 새 수량)
    - 본인 소유의 장바구니 아이템인지 확인 (다른 사용자 cart_id 접근 차단)
    - quantity가 1 미만이면 에러
    - 변경하려는 quantity가 해당 옵션의 stock을 초과하면 "재고가 부족합니다(현재 N개)" 에러
    - 성공 시 UPDATE 후 새 소계(subtotal) 반환
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다.",
            "redirect": url_for("auth.login")
        }), 401

    data = request.get_json() or {}
    try:
        new_quantity = int(data.get("quantity"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "올바른 수량을 입력해 주세요."}), 400

    # 1. quantity가 1 미만인 경우 에러
    if new_quantity < 1:
        return jsonify({"success": False, "message": "수량은 최소 1개 이상이어야 합니다."}), 400

    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return jsonify({"success": False, "message": "서버 연결에 실패했습니다."}), 500

    try:
        # 2. 장바구니 아이템 조회 (옵션 및 상품 가격 정보 조인)
        cart_res = (
            admin_sb.table("carts")
            .select("id, user_id, product_id, option_id, quantity, product_options(id, stock, additional_price), products(id, price, discount_rate)")
            .eq("id", cart_id)
            .maybe_single()
            .execute()
        )
        cart_item = cart_res.data if cart_res else None

        if not cart_item:
            return jsonify({"success": False, "message": "장바구니 항목을 찾을 수 없습니다."}), 404

        # 3. 본인 소유 확인 (다른 사용자의 cart_id 접근 차단)
        if cart_item.get("user_id") != user_id:
            return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

        # 옵션 및 재고 정보 확인
        option_data = cart_item.get("product_options") or {}
        current_stock = int(option_data.get("stock") or 0)

        # 4. 재고 초과 검증
        if new_quantity > current_stock:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다(현재 {current_stock}개)"
            }), 400

        # 5. 수량 UPDATE
        update_res = (
            admin_sb.table("carts")
            .update({"quantity": new_quantity})
            .eq("id", cart_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not update_res.data:
            return jsonify({"success": False, "message": "수량 변경에 실패했습니다."}), 500

        # 6. 새 소계(subtotal) 계산
        product_data = cart_item.get("products") or {}
        raw_price = float(product_data.get("price") or 0)
        discount_rate = float(product_data.get("discount_rate") or 0)
        additional_price = float(option_data.get("additional_price") or 0)

        # 실제 단가 계산 (할인 적용가 + 추가 옵션가)
        if discount_rate > 0:
            unit_price = round(raw_price * (1 - discount_rate / 100)) + additional_price
        else:
            unit_price = raw_price + additional_price

        subtotal = int(unit_price * new_quantity)

        # 전체 장바구니 수량 합계 조회
        total_items_res = admin_sb.table("carts").select("quantity").eq("user_id", user_id).execute()
        cart_total_count = sum(int(item.get("quantity") or 0) for item in (total_items_res.data or []))

        return jsonify({
            "success": True,
            "message": "수량이 변경되었습니다.",
            "cart_id": cart_id,
            "quantity": new_quantity,
            "unit_price": int(unit_price),
            "subtotal": subtotal,
            "formatted_subtotal": f"{subtotal:,}원",
            "cart_count": cart_total_count
        })

    except Exception as e:
        logger.error(f"장바구니 수량 변경 실패: {e}")
        return jsonify({"success": False, "message": f"수량 변경 중 오류가 발생했습니다: {str(e)}"}), 500


# ==============================================================
# 장바구니 페이지 (GET /carts, GET /cart)
# ==============================================================
@bp.route("/cart")
@bp.route("/carts")
def view_cart():
    """
    장바구니 페이지: 사용자의 모든 장바구니 아이템 조회 및 표시
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return render_template("cart.html", cart_items=[], cart_total=0, cart_total_count=0)

    try:
        # carts 테이블에서 해당 사용자의 모든 아이템 조회 (상품 + 옵션 정보 조인)
        cart_res = (
            admin_sb.table("carts")
            .select(
                "id, quantity, products(id, name, discount_rate, price, product_images(image_url, is_thumbnail)), product_options(id, color, size, additional_price, stock)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        raw_items = cart_res.data or []

        cart_items = []
        cart_total = 0

        for item in raw_items:
            product = item.get("products") or {}
            option = item.get("product_options") or {}
            quantity = int(item.get("quantity") or 0)

            # 상품 이미지
            product_images = product.get("product_images") or []
            thumbnail_url = None
            for img in product_images:
                if img.get("is_thumbnail"):
                    thumbnail_url = img.get("image_url")
                    break
            if not thumbnail_url and product_images:
                thumbnail_url = product_images[0].get("image_url")
            if not thumbnail_url:
                thumbnail_url = "https://picsum.photos/seed/vibe-product/300/350"

            # 가격 계산
            raw_price = float(product.get("price") or 0)
            discount_rate = float(product.get("discount_rate") or 0)
            additional_price = float(option.get("additional_price") or 0)

            if discount_rate > 0:
                unit_price = round(raw_price * (1 - discount_rate / 100)) + additional_price
            else:
                unit_price = raw_price + additional_price

            subtotal = int(unit_price * quantity)
            cart_total += subtotal

            cart_items.append({
                "id": item.get("id"),
                "product_id": product.get("id"),
                "product_name": product.get("name", "상품명 없음"),
                "color": option.get("color", "-"),
                "size": option.get("size", "-"),
                "quantity": quantity,
                "unit_price": int(unit_price),
                "subtotal": subtotal,
                "formatted_subtotal": f"{subtotal:,}원",
                "formatted_unit_price": f"{int(unit_price):,}원",
                "thumbnail_url": thumbnail_url,
                "stock": int(option.get("stock") or 0)
            })

        cart_total_count = sum(item["quantity"] for item in cart_items)

        return render_template(
            "cart.html",
            cart_items=cart_items,
            cart_total=cart_total,
            formatted_cart_total=f"{cart_total:,}원",
            cart_total_count=cart_total_count
        )

    except Exception as e:
        logger.error(f"장바구니 조회 실패: {e}")
        return render_template("cart.html", cart_items=[], cart_total=0, cart_total_count=0)


# ==============================================================
# 장바구니 아이템 삭제 (DELETE /cart/<cart_id>)
# ==============================================================
@bp.route("/cart/<int:cart_id>", methods=["DELETE"])
def delete_cart_item(cart_id: int):
    """
    장바구니 아이템 삭제:
    - 본인 소유 확인 후 삭제
    - 성공 시 삭제된 아이템 ID 및 남은 총 수량 반환
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다.",
            "redirect": url_for("auth.login")
        }), 401

    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return jsonify({"success": False, "message": "서버 연결에 실패했습니다."}), 500

    try:
        # 1. 장바구니 아이템 조회
        cart_res = (
            admin_sb.table("carts")
            .select("id, user_id, quantity")
            .eq("id", cart_id)
            .maybe_single()
            .execute()
        )
        cart_item = cart_res.data if cart_res else None

        if not cart_item:
            return jsonify({"success": False, "message": "장바구니 항목을 찾을 수 없습니다."}), 404

        # 2. 본인 소유 확인
        if cart_item.get("user_id") != user_id:
            return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

        # 3. 아이템 삭제
        delete_res = (
            admin_sb.table("carts")
            .delete()
            .eq("id", cart_id)
            .eq("user_id", user_id)
            .execute()
        )

        # 4. 남은 장바구니 아이템 수량 합계 조회 및 총액 계산
        remaining_res = (
            admin_sb.table("carts")
            .select(
                "id, quantity, products(id, price, discount_rate), product_options(id, additional_price)"
            )
            .eq("user_id", user_id)
            .execute()
        )
        remaining_items = remaining_res.data or []
        
        cart_total_count = 0
        cart_total_amount = 0
        
        for item in remaining_items:
            qty = int(item.get("quantity") or 0)
            cart_total_count += qty
            
            # 가격 계산
            product = item.get("products") or {}
            option = item.get("product_options") or {}
            
            raw_price = float(product.get("price") or 0)
            discount_rate = float(product.get("discount_rate") or 0)
            additional_price = float(option.get("additional_price") or 0)
            
            # 실제 단가 계산 (할인 적용 + 추가 옵션가)
            if discount_rate > 0:
                unit_price = round(raw_price * (1 - discount_rate / 100)) + additional_price
            else:
                unit_price = raw_price + additional_price
            
            cart_total_amount += int(unit_price * qty)

        return jsonify({
            "success": True,
            "message": "장바구니에서 삭제되었습니다.",
            "cart_id": cart_id,
            "cart_count": cart_total_count,
            "cart_total_amount": cart_total_amount,
            "formatted_cart_total": f"{cart_total_amount:,}원"
        })

    except Exception as e:
        logger.error(f"장바구니 아이템 삭제 실패: {e}")
        return jsonify({"success": False, "message": f"삭제 중 오류가 발생했습니다: {str(e)}"}), 500


# ==============================================================
# 환경 변수 디버그 엔드포인트 (DEBUG ONLY - 배포 후 제거)
# ==============================================================
@bp.route("/_debug/env")
def debug_env():
    """
    환경 변수가 제대로 로드되었는지 확인하는 테스트 엔드포인트
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    return jsonify({
        "SUPABASE_URL": f"{supabase_url[:30]}..." if supabase_url else "NOT SET",
        "SUPABASE_ANON_KEY": f"{supabase_anon_key[:30]}..." if supabase_anon_key else "NOT SET",
        "SUPABASE_SERVICE_KEY": f"{supabase_service_key[:30]}..." if supabase_service_key else "NOT SET",
        "SECRET_KEY": f"{secret_key[:20]}..." if secret_key else "NOT SET",
        "status": "✅ All set!" if all([supabase_url, supabase_anon_key, supabase_service_key, secret_key]) else "❌ Missing vars"
    })


# ==============================================================
# Supabase 연결 테스트 엔드포인트 (DEBUG ONLY)
# ==============================================================
@bp.route("/_debug/supabase")
def debug_supabase():
    """
    Supabase 클라이언트가 실제로 작동하는지 테스트
    """
    try:
        # Admin 클라이언트로 products 테이블 조회 시도
        admin_sb = get_supabase_admin_client()
        if not admin_sb:
            return jsonify({
                "status": "❌ Failed",
                "message": "Supabase admin client initialization failed"
            }), 500
        
        # products 테이블에서 1개 항목만 조회
        res = admin_sb.table("products").select("id, name").limit(1).execute()
        
        return jsonify({
            "status": "✅ Connected",
            "message": "Supabase connection successful",
            "sample_data": res.data if res.data else "No data in products table",
            "response_count": len(res.data) if res.data else 0
        })
    
    except Exception as e:
        error_msg = str(e)
        return jsonify({
            "status": "❌ Error",
            "message": "Supabase connection failed",
            "error": error_msg,
            "error_type": type(e).__name__
        }), 500


# ==============================================================
# 주문서 페이지 (GET /order/checkout)
# ==============================================================
@bp.route("/order/checkout", methods=["GET"])
def checkout():
    """
    주문서 페이지:
    - 로그인 필수, 비로그인 시 로그인 페이지로 리다이렉트
    - 장바구니 비어있으면 /cart 리다이렉트
    - 장바구니에 품절(stock=0) 아이템이 하나라도 있으면 /cart로 리다이렉트하고 "품절된 상품이 있어 주문할 수 없습니다" 안내
    - 장바구니 아이템 목록 표시 (수정 불가)
    - 배송지 입력 폼 (이름, 010-0000-0000 형식 전화번호, 5자 이상 주소, 메모)
    - "마이페이지에 저장된 기본 배송지 불러오기" 지원 (profiles 테이블 조회)
    - 결제 금액 요약 (상품금액 + 배송비 = 최종금액)
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login", next=request.path))
    
    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        flash("서버 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.", "danger")
        return redirect(url_for("main.view_cart"))
    
    try:
        # 장바구니 조회
        cart_res = (
            admin_sb.table("carts")
            .select(
                "id, quantity, products(id, name, price, discount_rate, product_images(image_url, is_thumbnail)), product_options(id, color, size, additional_price, stock)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        raw_items = cart_res.data or []
        
        # 1. 장바구니 비어있는지 확인
        if not raw_items:
            flash("장바구니가 비어 있습니다.", "warning")
            return redirect(url_for("main.view_cart", warning="장바구니가 비어 있습니다."))
        
        cart_items = []
        cart_total = 0
        out_of_stock = False
        out_of_stock_item_names = []
        
        for item in raw_items:
            product = item.get("products") or {}
            option = item.get("product_options") or {}
            quantity = int(item.get("quantity") or 0)
            stock = int(option.get("stock") or 0)
            
            # 2. 품절(stock=0) 확인
            if stock <= 0:
                out_of_stock = True
                out_of_stock_item_names.append(f"{product.get('name', '상품')}({option.get('color', '')}/{option.get('size', '')})")
            
            # 상품 이미지
            product_images = product.get("product_images") or []
            thumbnail_url = None
            for img in product_images:
                if img.get("is_thumbnail"):
                    thumbnail_url = img.get("image_url")
                    break
            if not thumbnail_url and product_images:
                thumbnail_url = product_images[0].get("image_url")
            if not thumbnail_url:
                thumbnail_url = "https://picsum.photos/seed/vibe-product/300/350"
            
            # 단가 계산 (할인 적용가 + 추가 옵션가)
            raw_price = float(product.get("price") or 0)
            discount_rate = float(product.get("discount_rate") or 0)
            additional_price = float(option.get("additional_price") or 0)
            
            if discount_rate > 0:
                unit_price = round(raw_price * (1 - discount_rate / 100)) + additional_price
            else:
                unit_price = raw_price + additional_price
            
            subtotal = int(unit_price * quantity)
            cart_total += subtotal
            
            cart_items.append({
                "id": item.get("id"),
                "product_name": product.get("name"),
                "product_id": product.get("id"),
                "color": option.get("color"),
                "size": option.get("size"),
                "quantity": quantity,
                "unit_price": int(unit_price),
                "formatted_unit_price": f"{int(unit_price):,}원",
                "subtotal": subtotal,
                "formatted_subtotal": f"{subtotal:,}원",
                "thumbnail_url": thumbnail_url,
                "stock": stock
            })
        
        # 품절 상품이 하나라도 있으면 /cart 로 리다이렉트하고 안내
        if out_of_stock:
            error_message = "품절된 상품이 있어 주문할 수 없습니다."
            flash(error_message, "danger")
            return redirect(url_for("main.view_cart", error=error_message))
        
        # 배송비 (3,000원 고정)
        shipping_fee = 3000
        final_amount = cart_total + shipping_fee
        
        # profiles 테이블에서 기본 배송지 정보 조회
        user_info = {
            "full_name": session.get("user_name", ""),
            "phone": "",
            "address": ""
        }
        try:
            profile_res = admin_sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
            if profile_res and profile_res.data:
                p_data = profile_res.data
                user_info["full_name"] = p_data.get("full_name") or user_info["full_name"]
                user_info["phone"] = p_data.get("phone") or ""
                user_info["address"] = p_data.get("address") or ""
            
            # auth metadata 보완
            u_res = admin_sb.auth.admin.get_user_by_id(user_id)
            if u_res and u_res.user and u_res.user.user_metadata:
                meta = u_res.user.user_metadata
                if not user_info["full_name"] and meta.get("full_name"):
                    user_info["full_name"] = meta.get("full_name")
                if not user_info["phone"] and meta.get("phone"):
                    user_info["phone"] = meta.get("phone")
                if not user_info["address"] and meta.get("address"):
                    user_info["address"] = meta.get("address")
        except Exception as pe:
            logger.warning(f"배송지 프로필 조회 경고: {pe}")
        
        return render_template(
            "checkout.html",
            cart_items=cart_items,
            cart_total=cart_total,
            formatted_cart_total=f"{cart_total:,}원",
            shipping_fee=shipping_fee,
            formatted_shipping_fee=f"{shipping_fee:,}원",
            final_amount=final_amount,
            formatted_final_amount=f"{final_amount:,}원",
            user_full_name=user_info.get("full_name", ""),
            user_phone=user_info.get("phone", ""),
            user_address=user_info.get("address", "")
        )
    
    except Exception as e:
        logger.error(f"주문서 페이지 로드 실패: {e}")
        flash(f"주문서 불러오기 중 오류가 발생했습니다: {str(e)}", "danger")
        return redirect(url_for("main.view_cart"))


# ==============================================================
# 기본 배송지 조회 API (GET /api/user/default-address)
# ==============================================================
@bp.route("/api/user/default-address")
def api_get_default_address():
    """
    profiles 테이블에서 로그인 사용자의 기본 배송지(이름, 휴대폰, 주소)를 조회합니다.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return jsonify({"success": False, "message": "데이터베이스 연결 실패"}), 500

    try:
        user_info = {
            "full_name": session.get("user_name", ""),
            "phone": "",
            "address": ""
        }
        
        # 1. profiles 테이블 조회
        res = admin_sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
        if res and res.data:
            p_data = res.data
            user_info["full_name"] = p_data.get("full_name") or user_info["full_name"]
            user_info["phone"] = p_data.get("phone") or ""
            user_info["address"] = p_data.get("address") or ""

        # 2. auth.users 메타데이터 보완
        try:
            u_res = admin_sb.auth.admin.get_user_by_id(user_id)
            if u_res and u_res.user and u_res.user.user_metadata:
                meta = u_res.user.user_metadata
                if not user_info["full_name"] and meta.get("full_name"):
                    user_info["full_name"] = meta.get("full_name")
                if not user_info["phone"] and meta.get("phone"):
                    user_info["phone"] = meta.get("phone")
                if not user_info["address"] and meta.get("address"):
                    user_info["address"] = meta.get("address")
        except Exception:
            pass

        return jsonify({
            "success": True,
            "data": user_info
        })
    except Exception as e:
        logger.error(f"기본 배송지 조회 실패: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================================================
# 주문 생성 (POST /order/create)
# ==============================================================
@bp.route("/order/create", methods=["POST"])
def create_order():
    """
    주문 생성:
    - 배송지 정보 검증 (010-0000-0000 형식, 주소 5자 이상 등)
    - 품절 아이템 재확인
    - orders 테이블에 주문 레코드 생성 (더미 결제 완료 상태 PAID)
    - order_items 테이블에 주문 상세 생성
    - 장바구니 항목 삭제
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
    
    data = request.get_json() or {}
    
    # 1. 필수 필드 검증
    recipient_name = data.get("recipient_name", "").strip()
    recipient_phone = data.get("recipient_phone", "").strip()
    shipping_address = data.get("shipping_address", "").strip()
    shipping_memo = data.get("shipping_memo", "").strip()
    
    if not recipient_name or len(recipient_name) < 2:
        return jsonify({"success": False, "message": "수령인 이름을 2자 이상 입력해주세요."}), 400
    
    # 휴대폰 번호 검증: 010-0000-0000 패턴
    import re
    if not re.match(r'^010-\d{4}-\d{4}$', recipient_phone):
        return jsonify({"success": False, "message": "휴대폰 번호는 010-0000-0000 형식으로 입력해주세요."}), 400
    
    # 주소 검증: 최소 5자 이상
    if not shipping_address or len(shipping_address) < 5:
        return jsonify({"success": False, "message": "배송 주소는 5자 이상 입력해주세요."}), 400
    
    admin_sb = get_supabase_admin_client()
    if not admin_sb:
        return jsonify({"success": False, "message": "서버 연결에 실패했습니다."}), 500
    
    try:
        # 2. 장바구니 조회 및 재고 확인
        cart_res = (
            admin_sb.table("carts")
            .select(
                "id, quantity, product_id, option_id, products(id, name, price, discount_rate), product_options(id, color, size, additional_price, stock)"
            )
            .eq("user_id", user_id)
            .execute()
        )
        cart_items = cart_res.data or []
        
        if not cart_items:
            return jsonify({"success": False, "message": "장바구니가 비어있습니다."}), 400
        
        # 재고 부족 / 품절 검사
        for item in cart_items:
            opt = item.get("product_options") or {}
            qty = int(item.get("quantity") or 0)
            stock = int(opt.get("stock") or 0)
            if stock <= 0:
                prod = item.get("products") or {}
                return jsonify({
                    "success": False,
                    "message": f"품절된 상품이 있어 주문할 수 없습니다: {prod.get('name', '')} ({opt.get('color', '')}/{opt.get('size', '')})"
                }), 400
            if qty > stock:
                prod = item.get("products") or {}
                return jsonify({
                    "success": False,
                    "message": f"재고가 부족합니다: {prod.get('name', '')} (현재 재고: {stock}개)"
                }), 400

        # 3. 총액 계산
        total_amount = 0
        order_items_data = []
        
        for item in cart_items:
            quantity = int(item.get("quantity") or 0)
            product = item.get("products") or {}
            option = item.get("product_options") or {}
            
            raw_price = float(product.get("price") or 0)
            discount_rate = float(product.get("discount_rate") or 0)
            additional_price = float(option.get("additional_price") or 0)
            
            if discount_rate > 0:
                unit_price = round(raw_price * (1 - discount_rate / 100)) + additional_price
            else:
                unit_price = raw_price + additional_price
            
            item_total = int(unit_price * quantity)
            total_amount += item_total
            
            order_items_data.append({
                "product_id": product.get("id"),
                "option_id": option.get("id"),
                "quantity": quantity,
                "unit_price": int(unit_price),
                "item_total": item_total
            })
        
        # 주문번호 생성 (ORD-YYYYMMDD-랜덤)
        from datetime import datetime
        import uuid
        now_str = datetime.now().strftime("%Y%m%d")
        order_number = f"ORD-{now_str}-{uuid.uuid4().hex[:6].upper()}"
        
        # 배송비 (3,000원)
        shipping_fee = 3000
        final_amount = total_amount + shipping_fee
        
        # 4. orders 테이블에 주문 생성 (더미 결제 → 바로 결제 완료 PAID)
        order_res = admin_sb.table("orders").insert({
            "order_number": order_number,
            "user_id": user_id,
            "total_amount": total_amount,
            "discount_amount": 0,
            "final_amount": final_amount,
            "status": "PAID",
            "recipient_name": recipient_name,
            "recipient_phone": recipient_phone,
            "shipping_address": shipping_address,
            "shipping_memo": shipping_memo if shipping_memo else None,
            "payment_method": "DUMMY",
            "paid_at": "now()"
        }).execute()
        
        order_id = order_res.data[0].get("id") if order_res.data else None
        
        if not order_id:
            return jsonify({"success": False, "message": "주문 생성에 실패했습니다."}), 500
        
        # 5. order_items 테이블에 상세 항목 생성 & 옵션 재고(stock) 차감
        for item in order_items_data:
            admin_sb.table("order_items").insert({
                "order_id": order_id,
                "product_id": item["product_id"],
                "option_id": item["option_id"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "item_total": item["item_total"]
            }).execute()

            # 재고 차감 시도
            try:
                curr_opt = admin_sb.table("product_options").select("stock").eq("id", item["option_id"]).maybe_single().execute()
                if curr_opt and curr_opt.data:
                    c_stock = int(curr_opt.data.get("stock") or 0)
                    new_stock = max(0, c_stock - item["quantity"])
                    admin_sb.table("product_options").update({"stock": new_stock}).eq("id", item["option_id"]).execute()
            except Exception as se:
                logger.warning(f"재고 차감 처리 경고: {se}")
        
        # 6. 장바구니 비우기
        for cart_item in cart_items:
            admin_sb.table("carts").delete().eq("id", cart_item.get("id")).execute()
        
        return jsonify({
            "success": True,
            "message": "주문이 성공적으로 완료되었습니다!",
            "order_number": order_number,
            "order_id": order_id,
            "final_amount": final_amount,
            "formatted_final_amount": f"{final_amount:,}원",
            "recipient_name": recipient_name,
            "shipping_address": shipping_address
        })
    
    except Exception as e:
        logger.error(f"주문 생성 실패: {e}")
        return jsonify({"success": False, "message": f"주문 생성 중 오류가 발생했습니다: {str(e)}"}), 500
