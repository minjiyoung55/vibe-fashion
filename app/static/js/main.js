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
});
