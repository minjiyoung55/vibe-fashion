import os
import logging
from functools import wraps
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)
from app.services.supabase_client import get_supabase_client, get_supabase_admin_client

# 로깅 설정
logger = logging.getLogger(__name__)

# 'auth' 블루프린트 생성
bp = Blueprint("auth", __name__, url_prefix="/auth")


def get_site_url() -> str:
    """사이트 기본 URL을 환경 변수 또는 현재 요청(Host)에서 읽어옵니다. (Azure HTTPS 강제)"""
    env_url = os.getenv("SITE_URL")
    if env_url:
        return env_url.rstrip("/")
    if request and request.host_url:
        url = request.host_url.rstrip("/")
        # Azure App Service 환경에서는 리버스 프록시 뒤에 있으므로 https로 변환
        if "azurewebsites.net" in url and url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        return url
    return "http://localhost:5000"


def login_required(view_func):
    """
    Flask session에서 'user_id'를 확인하는 로그인 필수 데코레이터입니다.
    비로그인 상태일 경우 로그인 페이지로 리다이렉트합니다.
    """
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", error="로그인이 필요한 서비스입니다."))
        return view_func(*args, **kwargs)
    return decorated_view


# ==============================================================
# [1] GET/POST /auth/login - 로그인 폼 + 처리
# 이메일 미인증 시 error=email_not_confirmed
# ==============================================================
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # 이미 로그인된 상태라면 마이페이지 또는 메인으로 이동
        if session.get("user_id"):
            return redirect(url_for("auth.mypage"))
        return render_template("auth/login.html")

    # POST 처리
    email = (request.form.get("email") or "").strip()
    password = (request.form.get("password") or "").strip()

    if not email or not password:
        return redirect(url_for("auth.login", error="이메일과 비밀번호를 모두 입력해 주세요."))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.login", error="인증 서버 연결에 실패했습니다."))

    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not res.user:
            return redirect(url_for("auth.login", error="이메일 또는 비밀번호가 일치하지 않습니다."))

        user = res.user
        metadata = user.user_metadata or {}
        points = metadata.get("points", 2000)
        full_name = metadata.get("full_name") or email.split("@")[0]

        # Flask 세션에 사용자 정보 저장
        session["user_id"] = user.id
        session["user_email"] = user.email or email
        session["user_name"] = full_name
        session["user_points"] = points
        if res.session and getattr(res.session, "access_token", None):
            session["access_token"] = res.session.access_token

        return redirect(url_for("auth.mypage", message="로그인되었습니다."))

    except Exception as e:
        err_msg = str(e).lower()
        logger.error(f"로그인 처리 실패: {e}")

        # 이메일 미인증 에러 감지 (Supabase 반환 메시지: Email not confirmed 등)
        if "email not confirmed" in err_msg or "email_not_confirmed" in err_msg:
            return redirect(url_for("auth.login", error="email_not_confirmed"))

        if "invalid login credentials" in err_msg or "invalid_grant" in err_msg:
            return redirect(url_for("auth.login", error="이메일 또는 비밀번호가 올바르지 않습니다."))

        return redirect(url_for("auth.login", error="로그인 중 오류가 발생했습니다. 다시 시도해 주세요."))


# ==============================================================
# [2] GET/POST /auth/signup - 회원가입 폼 + 처리
# 가입 성공 시 /auth/signup-complete 페이지 이동
# ==============================================================
@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("auth.mypage"))
        return render_template("auth/signup.html")

    # POST 처리
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = (request.form.get("password") or "").strip()
    password_confirm = (request.form.get("password_confirm") or "").strip()

    if not full_name or not email or not password:
        return redirect(url_for("auth.signup", error="모든 필수 입력값을 작성해 주세요."))

    if len(password) < 6:
        return redirect(url_for("auth.signup", error="비밀번호는 최소 6자 이상이어야 합니다."))

    if password != password_confirm:
        return redirect(url_for("auth.signup", error="비밀번호와 비밀번호 확인이 일치하지 않습니다."))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.signup", error="인증 서버 연결에 실패했습니다."))

    site_url = get_site_url()
    redirect_to = f"{site_url}/auth/confirm"

    try:
        # Supabase Python 클라이언트로 회원가입 진행 (이메일 인증 링크 포함 발송)
        res = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": redirect_to,
                "data": {
                    "full_name": full_name,
                    "points": 2000
                }
            }
        })

        if not res.user:
            return redirect(url_for("auth.signup", error="회원가입 요청 처리에 실패했습니다."))

        # 이메일 인증이 필요한 경우 signup-complete 페이지로 이동
        return redirect(url_for("auth.signup_complete", email=email))

    except Exception as e:
        err_msg = str(e).lower()
        logger.error(f"회원가입 처리 실패: {e}")

        if "already registered" in err_msg or "already exists" in err_msg:
            return redirect(url_for("auth.signup", error="이미 가입된 이메일 주소입니다. 로그인해 주세요."))

        return redirect(url_for("auth.signup", error=f"회원가입 중 오류가 발생했습니다: {str(e)}"))


# ==============================================================
# [3] GET /auth/signup-complete - "인증 메일을 보냈습니다" 안내
# ==============================================================
@bp.route("/signup-complete", methods=["GET"])
def signup_complete():
    email = request.args.get("email", "")
    return render_template("auth/signup_complete.html", email=email)


# ==============================================================
# [4] GET /auth/confirm - 이메일 인증 링크 클릭 처리
# verify_otp / exchange_code_for_session 호출 → 성공 시 Flask session 저장 → /mypage
# ==============================================================
@bp.route("/confirm", methods=["GET"])
def confirm():
    """
    이메일 인증 링크 클릭 시 수신되는 토큰을 검증합니다.
    Supabase 이메일 템플릿의 링크 유형에 따라 code (PKCE) 또는 token_hash가 전달됩니다.
    검증에 성공하면 세션에 로그인 정보를 저장하고 /mypage로 이동합니다.
    """
    code = request.args.get("code")
    token_hash = request.args.get("token_hash") or request.args.get("token")
    otp_type = request.args.get("type", "signup")

    # 비밀번호 재설정 링크로 들어온 경우 새 비밀번호 설정 페이지로 리다이렉트
    if otp_type in ("recovery", "reset"):
        return redirect(url_for("auth.reset_password", code=code, token_hash=token_hash, type=otp_type))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.login", error="인증 서버 연결에 실패했습니다."))

    if not code and not token_hash:
        return redirect(url_for("auth.login", error="유효하지 않거나 만료된 인증 링크입니다."))

    try:
        # PKCE flow: code가 넘어온 경우
        if code:
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
        else:
            # Token Hash flow: verify_otp 호출
            res = supabase.auth.verify_otp({
                "token_hash": token_hash,
                "type": otp_type
            })

        if not res.user:
            return redirect(url_for("auth.login", error="인증 처리에 실패했습니다. 다시 시도해 주세요."))

        user = res.user
        metadata = user.user_metadata or {}
        full_name = metadata.get("full_name") or (user.email.split("@")[0] if user.email else "고객")
        points = metadata.get("points", 2000)

        # Flask 세션에 사용자 정보 저장
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_name"] = full_name
        session["user_points"] = points
        if res.session and getattr(res.session, "access_token", None):
            session["access_token"] = res.session.access_token

        return redirect(url_for("auth.mypage", message="이메일 인증이 완료되었습니다! 신규 회원 적립금 2,000원이 지급되었습니다."))

    except Exception as e:
        logger.error(f"이메일 인증 실패: {e}")
        return redirect(url_for("auth.login", error="인증 링크가 만료되었거나 이미 사용되었습니다. 로그인해 주세요."))


# ==============================================================
# [5] GET/POST /auth/forgot-password - 비밀번호 재설정 메일 발송
# ==============================================================
@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html")

    email = (request.form.get("email") or "").strip()
    if not email:
        return redirect(url_for("auth.forgot_password", error="이메일 주소를 입력해 주세요."))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.forgot_password", error="인증 서버 연결에 실패했습니다."))

    site_url = get_site_url()
    redirect_to = f"{site_url}/auth/reset-password"

    try:
        supabase.auth.reset_password_email(
            email,
            options={"redirect_to": redirect_to}
        )
        return redirect(url_for("auth.forgot_password", message="비밀번호 재설정 메일을 발송했습니다. 메일함을 확인해 주세요. (스팸 메일함도 확인 바랍니다)"))

    except Exception as e:
        err_msg = str(e).lower()
        logger.error(f"비밀번호 재설정 메일 발송 실패: {e}")
        if "rate limit" in err_msg or "over_email_send_rate_limit" in err_msg:
            return redirect(url_for("auth.forgot_password", error="이메일 발송 제한(Rate Limit)을 초과했습니다. 잠시 후(약 1시간 이내) 다시 시도해 주시거나 Supabase 대시보드 설정을 확인해 주세요."))
        return redirect(url_for("auth.forgot_password", error=f"메일 발송 중 오류가 발생했습니다: {str(e)}"))


# ==============================================================
# [6] GET/POST /auth/reset-password - 새 비밀번호 설정
# ==============================================================
@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        code = request.args.get("code")
        token_hash = request.args.get("token_hash") or request.args.get("token")
        otp_type = request.args.get("type", "recovery")

        # GET 요청에 code 또는 token_hash가 넘어온 경우 즉시 세션 수립
        if code or token_hash:
            supabase = get_supabase_client()
            if supabase:
                try:
                    if code:
                        res = supabase.auth.exchange_code_for_session({"auth_code": code})
                    else:
                        res = supabase.auth.verify_otp({
                            "token_hash": token_hash,
                            "type": otp_type
                        })
                    if res.user:
                        session["user_id"] = res.user.id
                        session["user_email"] = res.user.email
                        if res.session and getattr(res.session, "access_token", None):
                            session["access_token"] = res.session.access_token
                except Exception as e:
                    logger.warning(f"비밀번호 재설정 토큰 사전 검증 실패: {e}")

        return render_template("auth/reset_password.html")

    # POST 처리
    password = (request.form.get("password") or "").strip()
    password_confirm = (request.form.get("password_confirm") or "").strip()
    form_access_token = (request.form.get("access_token") or "").strip()

    if not password:
        return redirect(url_for("auth.reset_password", error="새 비밀번호를 입력해 주세요."))

    if len(password) < 6:
        return redirect(url_for("auth.reset_password", error="비밀번호는 최소 6자 이상이어야 합니다."))

    if password != password_confirm:
        return redirect(url_for("auth.reset_password", error="비밀번호와 비밀번호 확인이 일치하지 않습니다."))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.reset_password", error="인증 서버 연결에 실패했습니다."))

    # 세션 또는 폼에서 access_token 확인
    token_to_use = form_access_token or session.get("access_token")

    try:
        # access_token이 있으면 Supabase 인증 컨텍스트 설정
        if token_to_use:
            try:
                supabase.auth.set_session(token_to_use, "")
            except Exception:
                pass

        # 새 비밀번호로 사용자 정보 업데이트
        update_res = supabase.auth.update_user({
            "password": password
        })

        if not update_res.user:
            return redirect(url_for("auth.reset_password", error="비밀번호 재설정에 실패했습니다."))

        # 세션 초기화 후 로그인 페이지로 안내
        session.clear()
        return redirect(url_for("auth.login", message="비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해 주세요."))

    except Exception as e:
        logger.error(f"비밀번호 변경 실패: {e}")
        return redirect(url_for("auth.reset_password", error="비밀번호 재설정 중 오류가 발생했습니다. 재설정 메일을 다시 요청해 주세요."))


# ==============================================================
# [7] GET /auth/kakao - 카카오 로그인 시작 (Supabase OAuth)
# ==============================================================
@bp.route("/kakao", methods=["GET"])
def kakao_login():
    """
    카카오 OAuth 로그인 페이지로 리다이렉트합니다.
    권한 없는 account_email을 제외하고 profile_nickname과 profile_image만 요청하여
    KOE205 에러 없이 카카오 로그인이 즉시 성공하도록 처리합니다.
    """
    import urllib.parse

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.login", error="인증 서버 연결에 실패했습니다."))

    site_url = get_site_url()
    redirect_to = f"{site_url}/auth/callback"

    try:
        # Supabase OAuth Provider 호출 (세션 및 code_verifier 생성)
        oauth_res = supabase.auth.sign_in_with_oauth({
            "provider": "kakao",
            "options": {
                "redirect_to": redirect_to
            }
        })

        # PKCE flow: 클라이언트 메모리에 생성된 code_verifier를 Flask 세션에 보관
        try:
            storage_key = f"{supabase.auth._storage_key}-code-verifier"
            code_verifier = supabase.auth._storage.get_item(storage_key)
            if code_verifier:
                session["oauth_code_verifier"] = code_verifier
        except Exception as se:
            logger.warning(f"code_verifier 세션 저장 경고: {se}")

        if oauth_res and getattr(oauth_res, "url", None):
            # 카카오 앱에서 권한 없는 account_email을 제외하고 닉네임과 프로필만 명시적 지정
            target_url = oauth_res.url
            if "scope=" not in target_url and "scopes=" not in target_url:
                target_url += "&scope=" + urllib.parse.quote("profile_nickname profile_image")
            return redirect(target_url)

        return redirect(url_for("auth.login", error="카카오 로그인 연결 URL 생성에 실패했습니다."))

    except Exception as e:
        logger.error(f"카카오 로그인 시작 실패: {e}")
        return redirect(url_for("auth.login", error=f"카카오 로그인 중 오류가 발생했습니다: {str(e)}"))


# ==============================================================
# [8] GET /auth/callback - OAuth 및 이메일 인증 콜백 처리
# ==============================================================
@bp.route("/callback", methods=["GET"])
def auth_callback():
    """
    카카오 로그인 또는 소셜 로그인 완료 후 리턴되는 콜백을 처리합니다.
    URL 파라미터로 code(PKCE)가 전달됩니다.
    """
    code = request.args.get("code")
    error = request.args.get("error")
    error_description = request.args.get("error_description")

    if error:
        logger.error(f"소셜 로그인 오류: {error} - {error_description}")
        return redirect(url_for("auth.login", error=f"소셜 로그인 실패: {error_description or error}"))

    if not code:
        return redirect(url_for("auth.login", error="인증 코드가 전달되지 않았습니다."))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for("auth.login", error="인증 서버 연결에 실패했습니다."))

    try:
        # Flask 세션에 보관해 두었던 code_verifier 복원
        code_verifier = session.pop("oauth_code_verifier", None)

        exchange_params = {"auth_code": code}
        if code_verifier:
            exchange_params["code_verifier"] = code_verifier

        # code를 session으로 교환
        res = supabase.auth.exchange_code_for_session(exchange_params)
        if not res.user:
            return redirect(url_for("auth.login", error="카카오 로그인 인증 처리에 실패했습니다."))

        user = res.user
        metadata = user.user_metadata or {}
        email = user.email or metadata.get("email") or f"kakao_{user.id[:8]}@vibefashion.com"
        full_name = metadata.get("full_name") or metadata.get("name") or metadata.get("preferred_username") or "카카오회원"
        points = metadata.get("points", 2000)

        # Flask 세션에 사용자 정보 저장
        session["user_id"] = user.id
        session["user_email"] = email
        session["user_name"] = full_name
        session["user_points"] = points
        if res.session and getattr(res.session, "access_token", None):
            session["access_token"] = res.session.access_token

        # profiles 테이블 동기화 (오류 무시)
        try:
            admin_sb = get_supabase_admin_client()
            if admin_sb:
                admin_sb.table("profiles").upsert({
                    "id": user.id,
                    "email": email,
                    "full_name": full_name,
                    "role": "CUSTOMER",
                    "customer_grade": "BRONZE",
                    "total_order_amount": 0
                }).execute()
        except Exception as pe:
            logger.warning(f"소셜 로그인 프로필 동기화 경고: {pe}")

        return redirect(url_for("auth.mypage", message=f"카카오 계정({full_name}님)으로 로그인되었습니다."))

    except Exception as e:
        logger.error(f"카카오 콜백 처리 실패: {e}")
        return redirect(url_for("auth.login", error="카카오 로그인 세션 처리에 실패했습니다. 다시 시도해 주세요."))


# ==============================================================
# 마이페이지 및 로그아웃 라우트
# ==============================================================
@bp.route("/mypage", methods=["GET"])
@login_required
def mypage():
    """로그인된 사용자만 접근 가능한 마이페이지입니다."""
    return render_template("mypage.html")


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    """로그아웃 처리 후 로그인 페이지로 이동합니다."""
    session.clear()
    return redirect(url_for("auth.login", message="로그아웃되었습니다."))
