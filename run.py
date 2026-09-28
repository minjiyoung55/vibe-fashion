"""
VIBE FASHION 웹 애플리케이션 진입점 (Entry Point)

실행 방법:
    1. 가상환경 활성화 후 라이브러리 설치:
       pip install -r requirements.txt
    2. 개발 서버 실행:
       python run.py
    3. 브라우저 접속:
       http://127.0.0.1:5000
"""

import os
from app import create_app

# 앱 팩토리 패턴을 통해 Flask 인스턴스를 생성합니다.
app = create_app()

if __name__ == "__main__":
    # 환경변수에서 포트를 가져오거나 기본값 5000 사용
    port = int(os.getenv("PORT", 5000))
    
    # debug=True 모드로 개발 서버 실행 (코드 수정 시 자동 새로고침)
    print("=" * 50)
    print(f"✨ VIBE FASHION 쇼핑몰 서버가 시작되었습니다!")
    print(f"👉 접속 주소: http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=port, debug=True)
