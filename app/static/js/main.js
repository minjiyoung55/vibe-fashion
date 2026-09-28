/**
 * VIBE FASHION 메인 스크립트
 * 초보자를 위해 알기 쉬운 바닐라 자바스크립트로 작성되었습니다.
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. 필요한 DOM 요소 선택
    const cartCountBadge = document.getElementById("cartCountBadge");
    const cartToastElement = document.getElementById("cartToast");
    const toastMessage = document.getElementById("toastMessage");
    const addToCartButtons = document.querySelectorAll(".add-to-cart-btn");

    // Bootstrap 토스트 인스턴스 생성
    let cartToast = null;
    if (cartToastElement && window.bootstrap) {
        cartToast = new bootstrap.Toast(cartToastElement, { delay: 2500 });
    }

    // 2. 브라우저 로컬스토리지에서 기존 장바구니 수량 가져오기
    let cartCount = parseInt(localStorage.getItem("vibe_cart_count") || "0", 10);
    if (cartCountBadge) {
        cartCountBadge.textContent = cartCount;
    }

    // 3. '장바구니 담기' 버튼 클릭 이벤트 리스너 등록
    addToCartButtons.forEach((button) => {
        button.addEventListener("click", (event) => {
            const productName = button.getAttribute("data-name");
            const productPrice = Number(button.getAttribute("data-price")).toLocaleString();

            // 장바구니 개수 증가 및 로컬스토리지 저장
            cartCount += 1;
            localStorage.setItem("vibe_cart_count", cartCount);

            // 네비게이션 바 뱃지 업데이트 및 애니메이션
            if (cartCountBadge) {
                cartCountBadge.textContent = cartCount;
                cartCountBadge.classList.add("badge-bounce");
                setTimeout(() => {
                    cartCountBadge.classList.remove("badge-bounce");
                }, 300);
            }

            // 토스트 알림 메시지 띄우기
            if (cartToast && toastMessage) {
                toastMessage.innerHTML = `<strong>${productName}</strong> (${productPrice}원) 상품이 장바구니에 담겼습니다! 🛒`;
                cartToast.show();
            }
        });
    });

    // 4. 네비게이션 바 '장바구니' 버튼 클릭 시 안내
    const cartBtn = document.getElementById("cartBtn");
    if (cartBtn) {
        cartBtn.addEventListener("click", () => {
            alert(`현재 장바구니에 ${cartCount}개의 상품이 담겨 있습니다.`);
        });
    }

    // 5. 실시간 고객 문의 채팅 위젯 로직
    const chatWidgetBtn = document.getElementById("chatWidgetBtn");
    const chatWindow = document.getElementById("chatWindow");
    const chatCloseBtn = document.getElementById("chatCloseBtn");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const chatMessages = document.getElementById("chatMessages");
    const quickTags = document.querySelectorAll(".chat-quick-tag");

    // 채팅창 열기/닫기 토글
    if (chatWidgetBtn && chatWindow) {
        chatWidgetBtn.addEventListener("click", () => {
            chatWindow.classList.toggle("show");
            if (chatWindow.classList.contains("show") && chatInput) {
                chatInput.focus();
            }
        });
    }

    if (chatCloseBtn && chatWindow) {
        chatCloseBtn.addEventListener("click", () => {
            chatWindow.classList.remove("show");
        });
    }

    // 메시지 화면 추가 함수
    const appendChatMessage = (sender, text) => {
        if (!chatMessages) return;
        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-msg ${sender}`;
        
        // 텍스트 내 줄바꿈 및 볼드 마크다운 간이 변환
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\n/g, "<br>");
        msgDiv.innerHTML = formatted;

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    // 서버로 메시지 전송 및 응답 처리
    const sendUserMessage = async (text) => {
        const query = (text || "").trim();
        if (!query) return;

        appendChatMessage("user", query);
        if (chatInput) chatInput.value = "";

        // 봇 타이핑 대기 표시
        const loadingDiv = document.createElement("div");
        loadingDiv.className = "chat-msg bot text-muted";
        loadingDiv.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 답변을 작성 중입니다...';
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: query }),
            });

            const data = await response.json();
            loadingDiv.remove();

            if (data && data.reply) {
                appendChatMessage("bot", data.reply);
            } else {
                appendChatMessage("bot", "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
            }
        } catch (err) {
            loadingDiv.remove();
            appendChatMessage("bot", "서버와의 연결이 원활하지 않습니다. 네트워크 상태를 확인해 주세요.");
        }
    };

    // 폼 제출 이벤트
    if (chatForm && chatInput) {
        chatForm.addEventListener("submit", (e) => {
            e.preventDefault();
            sendUserMessage(chatInput.value);
        });
    }

    // 빠른 질문 태그 클릭 이벤트
    quickTags.forEach((tag) => {
        tag.addEventListener("click", () => {
            const text = tag.getAttribute("data-text");
            if (text) {
                sendUserMessage(text);
            }
        });
    });
});
