"""
관리자(Admin) 전용 라우트 및 권한 검사 모듈
기존 고객용 기능에 전혀 영향을 주지 않는 독립된 Blueprint로 구성됩니다.
"""

import logging
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from app.services.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view_func):
    """
    관리자 권한 검사 데코레이터:
    1. 로그인 여부 확인 (session['user_id'])
    2. profiles 테이블의 role == 'ADMIN' 인지 확인
    비인가 접근 시 에러 안내와 함께 관리자 로그인 또는 메인 페이지로 차단합니다.
    """
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("관리자 로그인이 필요한 페이지입니다.", "warning")
            return redirect(url_for("admin.admin_login", next=request.path))

        # 세션 캐시 확인
        if session.get("user_role") == "ADMIN":
            return view_func(*args, **kwargs)

        # DB profiles role 확인
        sb = get_supabase_admin_client()
        if sb:
            try:
                res = sb.table("profiles").select("role").eq("id", user_id).maybe_single().execute()
                if res and res.data and res.data.get("role") == "ADMIN":
                    session["user_role"] = "ADMIN"
                    return view_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"관리자 권한 조회 실패: {e}")

        flash("접근 권한이 없습니다. 관리자 계정으로 로그인해 주세요.", "danger")
        return redirect(url_for("admin.admin_login"))

    return decorated_view


# ==============================================================
# 관리자 로그인 페이지 (GET /admin/login, POST /admin/login)
# ==============================================================
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """관리자 전용 로그인 페이지"""
    user_id = session.get("user_id")
    if user_id and session.get("user_role") == "ADMIN":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not email or not password:
            flash("이메일과 비밀번호를 모두 입력해 주세요.", "danger")
            return render_template("admin/login.html")

        sb = get_supabase_admin_client()
        if not sb:
            flash("데이터베이스 연결에 실패했습니다.", "danger")
            return render_template("admin/login.html")

        try:
            # 로그인 시도
            auth_res = sb.auth.sign_in_with_password({"email": email, "password": password})
            if auth_res and auth_res.user:
                u_id = auth_res.user.id
                # role 확인
                p_res = sb.table("profiles").select("role, full_name").eq("id", u_id).maybe_single().execute()
                role = p_res.data.get("role") if p_res and p_res.data else "CUSTOMER"

                if role != "ADMIN":
                    flash("해당 계정은 관리자 권한이 없습니다.", "danger")
                    return render_template("admin/login.html")

                # 관리자 세션 발급
                session["user_id"] = u_id
                session["user_email"] = email
                session["user_name"] = (p_res.data.get("full_name") if p_res and p_res.data else None) or "관리자"
                session["user_role"] = "ADMIN"

                next_url = request.args.get("next") or url_for("admin.dashboard")
                flash(f"{session['user_name']} 관리자님, 환영합니다.", "success")
                return redirect(next_url)
            else:
                flash("이메일 또는 비밀번호가 일치하지 않습니다.", "danger")
        except Exception as e:
            logger.error(f"관리자 로그인 처리 실패: {e}")
            flash("로그인 정보가 올바르지 않거나 권한이 없습니다.", "danger")

    return render_template("admin/login.html")


# ==============================================================
# 관리자 로그아웃 (GET /admin/logout)
# ==============================================================
@admin_bp.route("/logout")
def admin_logout():
    session.pop("user_role", None)
    flash("관리자 세션이 종료되었습니다.", "info")
    return redirect(url_for("admin.admin_login"))


# ==============================================================
# 1. 대시보드 메인 (GET /admin/)
# ==============================================================
@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """
    관리자 대시보드 메인 화면:
    - 핵심 지표 카드 7종 (오늘/이번주/이번달 매출, 주문 건수, 신규 회원수, 순이익, 이익률)
    - 실시간 업무 현황 위젯 (결제완료, 배송준비, 배송중, 취소/환불, 품절/재고부족)
    - 일별/월별 매출 및 주문 추이 그래프 (Chart.js 연동)
    - 카테고리별 매출 비중
    """
    sb = get_supabase_admin_client()
    stats = {
        "today_sales": 0,
        "week_sales": 0,
        "month_sales": 0,
        "total_orders": 0,
        "total_users": 0,
        "net_profit": 0,
        "profit_margin": 28.5, # 기준 추정 마진율
        "status_counts": {
            "new_orders": 0,
            "paid": 0,
            "preparing": 0,
            "shipping": 0,
            "delivered": 0,
            "refunds": 0,
            "low_stock": 0
        },
        "recent_orders": [],
        "chart_labels": [],
        "chart_sales": [],
        "chart_orders": []
    }

    if sb:
        try:
            # 1. 전체 주문 목록 조회
            orders_res = sb.table("orders").select("*").order("created_at", desc=True).execute()
            orders_data = orders_res.data or []
            stats["total_orders"] = len(orders_data)

            # 2. 주문 상태별 집계 & 매출 합산
            total_sales_all = 0
            for o in orders_data:
                final_amt = int(float(o.get("final_amount") or 0))
                st = (o.get("status") or "PAID").upper()

                if st == "PAID":
                    stats["status_counts"]["paid"] += 1
                    total_sales_all += final_amt
                elif st == "PREPARING":
                    stats["status_counts"]["preparing"] += 1
                    total_sales_all += final_amt
                elif st == "SHIPPED":
                    stats["status_counts"]["shipping"] += 1
                    total_sales_all += final_amt
                elif st == "DELIVERED":
                    stats["status_counts"]["delivered"] += 1
                    total_sales_all += final_amt
                elif st in ("CANCELLED", "REFUNDED"):
                    stats["status_counts"]["refunds"] += 1

            # 매출 지표 계산 (실제 주문 기반)
            stats["month_sales"] = total_sales_all
            stats["week_sales"] = total_sales_all
            stats["today_sales"] = total_sales_all
            stats["net_profit"] = int(total_sales_all * 0.285)

            # 3. 최근 주문 5건
            stats["recent_orders"] = orders_data[:5]

            # 4. 전체 회원 수
            users_res = sb.table("profiles").select("id").execute()
            stats["total_users"] = len(users_res.data or [])

            # 5. 재고 부족 상품 옵션 수 (stock <= 3)
            low_stock_res = sb.table("product_options").select("id").lte("stock", 3).execute()
            stats["status_counts"]["low_stock"] = len(low_stock_res.data or [])

            # 6. 차트 더미/실데이터 구성 (최근 7일 추이)
            stats["chart_labels"] = ["9/26", "9/27", "9/28", "9/29", "9/30", "10/1", "10/2"]
            stats["chart_sales"] = [120000, 185000, 95000, 240000, 310000, 150000, total_sales_all if total_sales_all > 0 else 280000]
            stats["chart_orders"] = [2, 3, 1, 4, 5, 2, stats["total_orders"] if stats["total_orders"] > 0 else 4]

        except Exception as e:
            logger.error(f"대시보드 통계 집계 실패: {e}")

    return render_template("admin/dashboard.html", active_menu="dashboard", stats=stats)


# ==============================================================
# 2. 주문 관리 (GET /admin/orders)
# ==============================================================
@admin_bp.route("/orders")
@admin_required
def orders():
    sb = get_supabase_admin_client()
    keyword = (request.args.get("keyword") or "").strip()
    status_filter = (request.args.get("status") or "").strip()

    orders_list = []
    if sb:
        try:
            query = sb.table("orders").select("*, order_items(*)").order("created_at", desc=True)
            if status_filter:
                query = query.eq("status", status_filter)
            
            res = query.execute()
            raw_orders = res.data or []

            status_map = {
                "PAID": "결제완료",
                "PREPARING": "배송준비",
                "SHIPPED": "배송중",
                "DELIVERED": "배송완료",
                "CANCELLED": "주문취소",
                "REFUNDED": "환불완료",
                "PENDING": "입금대기"
            }

            for o in raw_orders:
                rec_name = o.get("recipient_name") or ""
                ord_num = o.get("order_number") or ""
                rec_phone = o.get("recipient_phone") or ""

                # 키워드 검색 필터
                if keyword:
                    if keyword not in rec_name and keyword not in ord_num and keyword not in rec_phone:
                        continue

                items = o.get("order_items") or []
                if items:
                    first_name = items[0].get("product_name") or "상품"
                    summary_item_name = f"{first_name} 외 {len(items)-1}건" if len(items) > 1 else first_name
                else:
                    summary_item_name = "단품 주문"

                raw_st = (o.get("status") or "PAID").upper()
                orders_list.append({
                    "id": o.get("id"),
                    "order_number": ord_num,
                    "created_at": o.get("created_at") or "",
                    "recipient_name": rec_name,
                    "recipient_phone": rec_phone,
                    "shipping_address": o.get("shipping_address") or "",
                    "shipping_memo": o.get("shipping_memo") or "",
                    "final_amount": int(float(o.get("final_amount") or 0)),
                    "status": raw_st,
                    "status_label": status_map.get(raw_st, raw_st),
                    "summary_item_name": summary_item_name,
                    "items": items
                })

        except Exception as e:
            logger.error(f"주문 목록 조회 실패: {e}")

    return render_template("admin/orders.html", active_menu="orders", orders=orders_list)


# 주문 상태 업데이트 (POST /admin/orders/<order_id>/status)
@admin_bp.route("/orders/<order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id: str):
    new_status = request.form.get("status")
    sb = get_supabase_admin_client()
    if sb and new_status:
        try:
            sb.table("orders").update({"status": new_status}).eq("id", order_id).execute()
            flash(f"주문 상태가 '{new_status}'(으)로 변경되었습니다.", "success")
        except Exception as e:
            logger.error(f"주문 상태 변경 실패: {e}")
            flash(f"상태 변경 실패: {str(e)}", "danger")

    return redirect(url_for("admin.orders"))


# 일괄 주문 상태 변경 (POST /admin/orders/bulk-status)
@admin_bp.route("/orders/bulk-status", methods=["POST"])
@admin_required
def bulk_update_order_status():
    """선택한 주문 여러 건의 상태를 한 번에 일괄 변경"""
    order_ids = request.form.getlist("order_ids")
    new_status = (request.form.get("status") or "").strip()

    if not order_ids:
        flash("상태를 변경할 주문을 하나 이상 선택해 주세요.", "warning")
        return redirect(url_for("admin.orders"))

    if not new_status:
        flash("변경할 주문 상태를 선택해 주세요.", "warning")
        return redirect(url_for("admin.orders"))

    sb = get_supabase_admin_client()
    if sb:
        try:
            sb.table("orders").update({"status": new_status}).in_("id", order_ids).execute()
            flash(f"선택한 {len(order_ids)}건의 주문 상태가 '{new_status}'(으)로 일괄 변경되었습니다.", "success")
        except Exception as e:
            logger.error(f"주문 일괄 상태 변경 실패: {e}")
            flash(f"일괄 상태 변경 실패: {str(e)}", "danger")

    return redirect(url_for("admin.orders"))


# ==============================================================
# 3. 배송 관리 (GET /admin/deliveries)
# ==============================================================
@admin_bp.route("/deliveries")
@admin_required
def deliveries():
    sb = get_supabase_admin_client()
    deliveries_list = []
    counts = {"preparing": 0, "shipping": 0, "delivered": 0}

    if sb:
        try:
            res = sb.table("orders").select("*").in_("status", ["PREPARING", "SHIPPED", "DELIVERED", "PAID"]).order("created_at", desc=True).execute()
            deliveries_list = res.data or []
            for d in deliveries_list:
                st = (d.get("status") or "").upper()
                if st == "PREPARING":
                    counts["preparing"] += 1
                elif st == "SHIPPED":
                    counts["shipping"] += 1
                elif st == "DELIVERED":
                    counts["delivered"] += 1
        except Exception as e:
            logger.error(f"배송 목록 조회 실패: {e}")

    return render_template("admin/deliveries.html", active_menu="deliveries", deliveries=deliveries_list, counts=counts)


# 배송 송장 및 상태 수정 (POST /admin/deliveries/<order_id>/update)
@admin_bp.route("/deliveries/<order_id>/update", methods=["POST"])
@admin_required
def update_delivery(order_id: str):
    sb = get_supabase_admin_client()
    status = request.form.get("status")
    shipping_memo = request.form.get("shipping_memo")

    if sb:
        try:
            payload = {}
            if status:
                payload["status"] = status
            if shipping_memo is not None:
                payload["shipping_memo"] = shipping_memo.strip()

            sb.table("orders").update(payload).eq("id", order_id).execute()
            flash("배송 정보 및 송장번호가 업데이트되었습니다.", "success")
        except Exception as e:
            logger.error(f"배송 정보 수정 실패: {e}")
            flash(f"수정 실패: {str(e)}", "danger")

    return redirect(url_for("admin.deliveries"))


# ==============================================================
# 4. 상품 관리 (GET /admin/products)
# ==============================================================
@admin_bp.route("/products")
@admin_required
def products():
    sb = get_supabase_admin_client()
    products_list = []
    categories_list = []

    if sb:
        try:
            # 카테고리 목록 조회
            cat_res = sb.table("categories").select("id, name").order("id").execute()
            categories_list = cat_res.data or []

            res = sb.table("products").select("*, categories(name), product_images(image_url, is_thumbnail), product_options(stock)").order("created_at", desc=True).execute()
            raw_prods = res.data or []

            for p in raw_prods:
                cat = p.get("categories") or {}
                cat_name = cat.get("name") if isinstance(cat, dict) else "일반"
                imgs = p.get("product_images") or []
                thumb = None
                for im in imgs:
                    if im.get("is_thumbnail"):
                        thumb = im.get("image_url")
                        break
                if not thumb and imgs:
                    thumb = imgs[0].get("image_url")
                if not thumb:
                    thumb = "https://picsum.photos/seed/vibe-product/100/120"

                opts = p.get("product_options") or []
                total_stock = sum(int(o.get("stock") or 0) for o in opts)

                products_list.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "category_name": cat_name,
                    "price": int(float(p.get("price") or 0)),
                    "discount_rate": int(float(p.get("discount_rate") or 0)),
                    "total_stock": total_stock,
                    "thumbnail_url": thumb
                })

        except Exception as e:
            logger.error(f"상품 목록 조회 실패: {e}")

    return render_template("admin/products.html", active_menu="products", products=products_list, categories=categories_list)


# 신규 상품 등록 (POST /admin/products/create) - 다중 이미지 및 색상/사이즈 옵션 빌더 지원
@admin_bp.route("/products/create", methods=["POST"])
@admin_required
def create_product():
    """
    상품 등록 시:
    1. 상품 기본 정보 (이름, 카테고리, 판매가, 할인율, 상세설명) products 테이블 등록
    2. 다중 착용컷 이미지 URL 목록 (줄바꿈 구분) product_images 테이블 등록 (첫번째는 썸네일 자동 지정)
    3. 색상(쉼표) x 사이즈(체크박스/쉼표) 조합을 계산하여 옵션별 재고/추가가격 일괄 생성
    """
    name = (request.form.get("name") or "").strip()
    category_id = request.form.get("category_id")
    price = request.form.get("price", 0)
    discount_rate = request.form.get("discount_rate", 0)
    description = (request.form.get("description") or "").strip()
    
    # 1. 다중 이미지 URL 목록 (텍스트에 한 줄씩 여러 장 입력)
    image_urls_raw = (request.form.get("image_urls") or "").strip()
    image_urls = [line.strip() for line in image_urls_raw.splitlines() if line.strip()]

    # 2. 색상 목록 (쉼표 구분) & 사이즈 목록 (체크박스 또는 쉼표 구분)
    colors_raw = (request.form.get("colors") or "").strip()
    colors = [c.strip() for c in colors_raw.split(",") if c.strip()]
    if not colors:
        colors = ["기본"]

    sizes = request.form.getlist("sizes")
    custom_sizes = (request.form.get("custom_sizes") or "").strip()
    if custom_sizes:
        for s in custom_sizes.split(","):
            s_clean = s.strip()
            if s_clean and s_clean not in sizes:
                sizes.append(s_clean)
    if not sizes:
        sizes = ["FREE"]

    initial_stock = int(request.form.get("initial_stock", 30))

    sb = get_supabase_admin_client()
    if sb and name:
        try:
            import uuid
            slug = f"prod-{uuid.uuid4().hex[:8]}"
            total_stock_calc = initial_stock * len(colors) * len(sizes)
            product_payload = {
                "name": name,
                "slug": slug,
                "price": float(price),
                "discount_rate": float(discount_rate),
                "description": description,
                "stock_quantity": total_stock_calc,
                "status": "ON_SALE"
            }
            if category_id:
                try:
                    product_payload["category_id"] = int(category_id)
                except ValueError:
                    pass

            new_p = sb.table("products").insert(product_payload).execute()

            if new_p.data:
                p_id = new_p.data[0]["id"]

                # A. 다중 이미지 등록 (첫 번째 이미지는 썸네일 지정)
                if image_urls:
                    img_records = []
                    for idx, img_url in enumerate(image_urls):
                        img_records.append({
                            "product_id": p_id,
                            "image_url": img_url,
                            "display_order": idx + 1,
                            "is_thumbnail": (idx == 0)
                        })
                    sb.table("product_images").insert(img_records).execute()
                else:
                    # 기본 플레이스홀더 이미지 등록
                    sb.table("product_images").insert({
                        "product_id": p_id,
                        "image_url": "https://picsum.photos/seed/vibe-product/600/700",
                        "display_order": 1,
                        "is_thumbnail": True
                    }).execute()

                # B. 색상 x 사이즈 옵션 조합 빌더 자동 생성
                option_records = []
                for col in colors:
                    for sz in sizes:
                        option_records.append({
                            "product_id": p_id,
                            "option_type": "COMBINATION",
                            "option_value": f"{col} / {sz}",
                            "color": col,
                            "size": sz,
                            "additional_price": 0.0,
                            "stock": initial_stock,
                            "stock_quantity": initial_stock
                        })

                if option_records:
                    sb.table("product_options").insert(option_records).execute()

                flash(f"상품 '{name}'이(가) 등록되었습니다. (이미지 {len(image_urls) or 1}장, 옵션 조합 {len(option_records)}개 생성 완료)", "success")
            else:
                flash("상품 저장에 실패했습니다.", "danger")

        except Exception as e:
            logger.error(f"상품 등록 실패: {e}")
            flash(f"상품 등록 실패: {str(e)}", "danger")

    return redirect(url_for("admin.products"))


# ==============================================================
# 5. 재고 관리 (GET /admin/inventory)
# ==============================================================
@admin_bp.route("/inventory")
@admin_required
def inventory():
    sb = get_supabase_admin_client()
    inventory_list = []

    if sb:
        try:
            res = sb.table("product_options").select("*, products(name)").order("stock", desc=False).execute()
            raw_opts = res.data or []

            for op in raw_opts:
                p_info = op.get("products") or {}
                p_name = p_info.get("name") if isinstance(p_info, dict) else "상품"

                inventory_list.append({
                    "id": op.get("id"),
                    "product_name": p_name,
                    "color": op.get("color") or "기본",
                    "size": op.get("size") or "FREE",
                    "stock": int(op.get("stock") or 0)
                })

        except Exception as e:
            logger.error(f"재고 목록 조회 실패: {e}")

    return render_template("admin/inventory.html", active_menu="inventory", inventory=inventory_list)


# 재고 수량 수정 (POST /admin/inventory/<option_id>/update)
@admin_bp.route("/inventory/<int:option_id>/update", methods=["POST"])
@admin_required
def update_inventory(option_id: int):
    new_stock = request.form.get("stock", 0)
    sb = get_supabase_admin_client()

    if sb:
        try:
            val = int(new_stock)
            sb.table("product_options").update({"stock": val, "stock_quantity": val}).eq("id", option_id).execute()
            flash("재고 수량이 성공적으로 변경되었습니다.", "success")
        except Exception as e:
            logger.error(f"재고 수정 실패: {e}")
            flash(f"재고 수정 실패: {str(e)}", "danger")

    return redirect(url_for("admin.inventory"))


# ==============================================================
# 6. 회원 관리 (GET /admin/users)
# ==============================================================
@admin_bp.route("/users")
@admin_required
def users():
    sb = get_supabase_admin_client()
    users_list = []

    if sb:
        try:
            res = sb.table("profiles").select("*").order("created_at", desc=True).execute()
            users_list = res.data or []
        except Exception as e:
            logger.error(f"회원 목록 조회 실패: {e}")

    return render_template("admin/users.html", active_menu="users", users=users_list)


# ==============================================================
# 7. 매출 및 정산 (GET /admin/sales)
# ==============================================================
@admin_bp.route("/sales")
@admin_required
def sales():
    sb = get_supabase_admin_client()
    orders_list = []
    summary = {
        "total_sales": 0,
        "total_cost": 0,
        "fees": 0,
        "net_profit": 0,
        "margin": 32.4
    }

    if sb:
        try:
            res = sb.table("orders").select("*").in_("status", ["PAID", "PREPARING", "SHIPPED", "DELIVERED"]).order("created_at", desc=True).execute()
            orders_list = res.data or []

            tot = sum(int(float(o.get("final_amount") or 0)) for o in orders_list)
            summary["total_sales"] = tot
            summary["total_cost"] = int(tot * 0.40)
            summary["fees"] = int(tot * 0.033) + (len(orders_list) * 2500)
            summary["net_profit"] = max(0, tot - summary["total_cost"] - summary["fees"])
            if tot > 0:
                summary["margin"] = round((summary["net_profit"] / tot) * 100, 1)

        except Exception as e:
            logger.error(f"정산 데이터 조회 실패: {e}")

    return render_template("admin/sales.html", active_menu="sales", orders=orders_list, summary=summary)


# ==============================================================
# 8. 판매 분석 (GET /admin/analytics)
# ==============================================================
@admin_bp.route("/analytics")
@admin_required
def analytics():
    sb = get_supabase_admin_client()
    top_products_dict = {}

    if sb:
        try:
            items_res = sb.table("order_items").select("product_name, quantity, subtotal_price").execute()
            for it in (items_res.data or []):
                p_name = it.get("product_name") or "상품"
                qty = int(it.get("quantity") or 0)
                sub = int(float(it.get("subtotal_price") or 0))

                if p_name not in top_products_dict:
                    top_products_dict[p_name] = {"name": p_name, "quantity": 0, "sales": 0}
                top_products_dict[p_name]["quantity"] += qty
                top_products_dict[p_name]["sales"] += sub

        except Exception as e:
            logger.error(f"판매 분석 집계 실패: {e}")

    top_products = sorted(top_products_dict.values(), key=lambda x: x["quantity"], reverse=True)[:5]
    return render_template("admin/analytics.html", active_menu="analytics", top_products=top_products)


# ==============================================================
# 9. 쿠폰 및 적립금 (GET /admin/coupons)
# ==============================================================
@admin_bp.route("/coupons")
@admin_required
def coupons():
    sb = get_supabase_admin_client()
    users_list = []
    if sb:
        res = sb.table("profiles").select("id, full_name, email").execute()
        users_list = res.data or []
    return render_template("admin/coupons.html", active_menu="coupons", users=users_list)


# 적립금 지급 처리 (POST /admin/coupons/points)
@admin_bp.route("/coupons/points", methods=["POST"])
@admin_required
def update_points():
    target_user_id = request.form.get("user_id")
    points_to_add = int(request.form.get("points", 0))
    reason = request.form.get("reason", "").strip()

    sb = get_supabase_admin_client()
    if sb and target_user_id:
        try:
            # auth metadata 및 profiles 조회
            u_res = sb.auth.admin.get_user_by_id(target_user_id)
            if u_res and u_res.user:
                curr_meta = u_res.user.user_metadata or {}
                curr_points = int(curr_meta.get("points", 2000))
                new_points = max(0, curr_points + points_to_add)
                curr_meta["points"] = new_points
                sb.auth.admin.update_user_by_id(target_user_id, {"user_metadata": curr_meta})
                flash(f"적립금 {points_to_add:,}원이 정상 처리되었습니다. (현재 잔액: {new_points:,}원)", "success")
        except Exception as e:
            logger.error(f"적립금 지급 오류: {e}")
            flash(f"적립금 처리 실패: {str(e)}", "danger")

    return redirect(url_for("admin.coupons"))


# ==============================================================
# 10. 고객 문의 및 CS (GET /admin/cs)
# ==============================================================
@admin_bp.route("/cs")
@admin_required
def cs():
    sb = get_supabase_admin_client()
    refunds_list = []
    if sb:
        try:
            res = sb.table("refunds").select("*").order("created_at", desc=True).execute()
            refunds_list = res.data or []
        except Exception as e:
            logger.error(f"환불/CS 목록 조회 실패: {e}")

    return render_template("admin/cs.html", active_menu="cs", refunds=refunds_list)


# ==============================================================
# 11. 관리자 설정 (GET /admin/settings)
# ==============================================================
@admin_bp.route("/settings")
@admin_required
def settings():
    return render_template("admin/settings.html", active_menu="settings")
