import os
from flask import Flask
from dotenv import load_dotenv

# .env 파일의 환경 변수를 미리 로드합니다.
load_dotenv()


def create_app(test_config=None):
    """
    [앱 팩토리 함수]
    Flask 인스턴스를 생성하고 초기 설정을 진행하는 팩토리 함수입니다.
    초보자 팁:
    - 앱 팩토리 패턴을 사용하면 여러 설정(개발/테스트/배포)으로
      앱 인스턴스를 유연하게 생성할 수 있어 유지보수가 쉬워집니다.
    """
    # Flask 애플리케이션 객체 생성
    app = Flask(__name__, instance_relative_config=True)

    # 기본 설정 등록
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-default"),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
    )

    # 테스트 설정이 주어졌다면 덮어쓰기
    if test_config is not None:
        app.config.from_mapping(test_config)

    # instance 폴더가 없으면 생성 (필요 시 파일 저장 등 대비)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Blueprint(경로/라우트 분리) 등록
    from app.routes import main, auth

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)

    # 최상위 /mypage 및 /mypage/change-password 직접 접근 지원
    app.add_url_rule("/mypage", endpoint="mypage_root", view_func=auth.mypage, methods=["GET", "POST"])
    app.add_url_rule("/mypage/change-password", endpoint="change_password_root", view_func=auth.change_password, methods=["POST"])

    # 템플릿 전역 변수 컨텍스트 프로세서 (로그인 사용자의 실시간 장바구니 개수 주입)
    @app.context_processor
    def inject_cart_count():
        from flask import session
        user_id = session.get("user_id")
        if not user_id:
            return {"user_cart_count": 0}
        try:
            from app.services.supabase_client import get_supabase_admin_client
            sb = get_supabase_admin_client()
            if sb:
                res = sb.table("carts").select("quantity").eq("user_id", user_id).execute()
                count = sum(int(item.get("quantity") or 0) for item in (res.data or []))
                return {"user_cart_count": count}
        except Exception:
            pass
        return {"user_cart_count": 0}

    return app
