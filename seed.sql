-- =====================================================
-- VIBE-FASHION 쇼핑몰 초기 시드 데이터 (Seed Data)
-- Supabase SQL Editor 실행용
-- =====================================================

do $$
declare
    v_top_id bigint;
    v_bottom_id bigint;
    v_outer_id bigint;
    v_dress_id bigint;
    v_acc_id bigint;
    v_bag_id bigint;
    v_shoes_id bigint;

    v_prod_crop_id uuid := '11111111-1111-1111-1111-111111111111'::uuid;
    v_prod_pants_id uuid := '22222222-2222-2222-2222-222222222222'::uuid;
    v_prod_jacket_id uuid := '33333333-3333-3333-3333-333333333333'::uuid;
    v_prod_dress_id uuid := '44444444-4444-4444-4444-444444444444'::uuid;
    v_prod_necklace_id uuid := '55555555-5555-5555-5555-555555555555'::uuid;
    v_prod_heels_id uuid := '66666666-6666-6666-6666-666666666666'::uuid;
    v_prod_vest_id uuid := '77777777-7777-7777-7777-777777777777'::uuid;
    v_prod_glasses_id uuid := '88888888-8888-8888-8888-888888888888'::uuid;
begin

    -- =====================================================
    -- 1. 카테고리 7종 등록 (중복 방지 on conflict)
    -- =====================================================
    insert into public.categories (name, slug, description, is_active)
    values
        ('상의', 'top', '티셔츠, 셔츠, 니트, 맨투맨 등', true),
        ('하의', 'bottom', '청바지, 슬랙스, 스커트, 반바지 등', true),
        ('아우터', 'outer', '자켓, 코트, 패딩, 가디건 등', true),
        ('원피스/세트', 'dress', '미니/미디 원피스, 셋업 수트 등', true),
        ('액세서리', 'acc', '목걸이, 반지, 벨트, 모자 등', true),
        ('가방', 'bag', '숄더백, 토트백, 백팩, 크로스백 등', true),
        ('신발', 'shoes', '스니커즈, 로퍼, 부츠, 샌들 등', true)
    on conflict (slug) do update
    set name = excluded.name, description = excluded.description;

    -- 등록된 카테고리 ID 조회
    select id into v_top_id from public.categories where slug = 'top';
    select id into v_bottom_id from public.categories where slug = 'bottom';
    select id into v_outer_id from public.categories where slug = 'outer';
    select id into v_dress_id from public.categories where slug = 'dress';
    select id into v_acc_id from public.categories where slug = 'acc';
    select id into v_bag_id from public.categories where slug = 'bag';
    select id into v_shoes_id from public.categories where slug = 'shoes';

    -- =====================================================
    -- 2. 샘플 상품 4종 등록
    -- 참고: 베이직 크롭 티셔츠의 원래 정가는 29,900원, 할인가가 19,900원 (약 33.44% 할인)
    -- =====================================================
    insert into public.products (
        id, category_id, name, slug, description,
        price, discount_rate, stock_quantity, status, is_featured
    )
    values
        (
            v_prod_crop_id,
            v_top_id,
            '베이직 크롭 티셔츠',
            'basic-crop-tshirt',
            '트렌디한 기장감과 부드러운 코튼 원단으로 일상에서 편안하게 착용할 수 있는 베이직 크롭 티셔츠입니다.',
            29900.00,
            33.44, -- 29,900원에서 할인 적용 시 약 19,900원
            300,
            'ON_SALE',
            true
        ),
        (
            v_prod_pants_id,
            v_bottom_id,
            '와이드 데님 팬츠',
            'wide-denim-pants',
            '체형 커버에 탁월한 세련된 와이드 핏 데님 팬츠입니다. 다양한 상의와 매치하기 좋습니다.',
            39900.00,
            0,
            150,
            'ON_SALE',
            true
        ),
        (
            v_prod_jacket_id,
            v_outer_id,
            '오버핏 코튼 자켓',
            'overfit-cotton-jacket',
            '간절기에 가볍게 걸치기 좋은 내추럴 무드의 오버핏 코튼 자켓입니다.',
            59900.00,
            0,
            80,
            'ON_SALE',
            false
        ),
        (
            v_prod_dress_id,
            v_dress_id,
            '플로럴 미디 원피스',
            'floral-midi-dress',
            '화사한 플라워 패턴과 여성스러운 실루엣이 돋보이는 미디 기장 원피스입니다.',
            45900.00,
            0,
            100,
            'ON_SALE',
            true
        ),
        (
            v_prod_necklace_id,
            v_acc_id,
            '클래식 하얀색 진주목걸이',
            'classic-white-pearl-necklace',
            '은은하고 고급스러운 광택감으로 어떤 룩에도 우아한 포인트를 주는 하얀색 진주목걸이입니다.',
            25000.00,
            0,
            80,
            'ON_SALE',
            true
        ),
        (
            v_prod_heels_id,
            v_shoes_id,
            '슬림라인 에나멜 스틸레토 힐',
            'slim-line-enamel-stiletto-heels',
            '날렵한 포인티드 토와 세련된 힐 라인으로 레그라인을 슬림하고 우아하게 연출해주는 에나멜 스틸레토 힐입니다.',
            48000.00,
            0,
            50,
            'ON_SALE',
            true
        ),
        (
            v_prod_vest_id,
            v_top_id,
            '클래식 V넥 니트 베스트',
            'classic-v-neck-knit-vest',
            '탄탄한 짜임의 케이블 니트 조직감과 여유로운 핏으로 셔츠나 티셔츠 위에 클래식하게 레이어드하기 좋은 V넥 니트 베스트입니다.',
            34900.00,
            0,
            60,
            'ON_SALE',
            true
        ),
        (
            v_prod_glasses_id,
            v_acc_id,
            '빈티지 레오파드 호피 안경',
            'vintage-leopard-pattern-glasses',
            '감각적인 타원형 쉐입과 레트로한 호피 패턴 프레임으로 지적이고 스타일리시한 무드를 완성해주는 데일리 안경입니다.',
            28000.00,
            0,
            45,
            'ON_SALE',
            true
        )
    on conflict (id) do update
    set
        category_id = excluded.category_id,
        name = excluded.name,
        price = excluded.price,
        discount_rate = excluded.discount_rate,
        stock_quantity = excluded.stock_quantity,
        status = excluded.status,
        is_featured = excluded.is_featured;

    -- =====================================================
    -- 3. 첫 번째 상품(베이직 크롭 티셔츠) 옵션 9종
    -- (블랙 / 화이트 / 베이지) × (S / M / L)
    -- =====================================================
    delete from public.product_options where product_id = v_prod_crop_id;

    insert into public.product_options (product_id, option_type, option_value, additional_price, stock_quantity)
    values
        (v_prod_crop_id, 'COLOR / SIZE', '블랙 / S', 0, 35),
        (v_prod_crop_id, 'COLOR / SIZE', '블랙 / M', 0, 40),
        (v_prod_crop_id, 'COLOR / SIZE', '블랙 / L', 0, 25),
        (v_prod_crop_id, 'COLOR / SIZE', '화이트 / S', 0, 35),
        (v_prod_crop_id, 'COLOR / SIZE', '화이트 / M', 0, 40),
        (v_prod_crop_id, 'COLOR / SIZE', '화이트 / L', 0, 25),
        (v_prod_crop_id, 'COLOR / SIZE', '베이지 / S', 0, 35),
        (v_prod_crop_id, 'COLOR / SIZE', '베이지 / M', 0, 40),
        (v_prod_crop_id, 'COLOR / SIZE', '베이지 / L', 0, 25);

    -- =====================================================
    -- 4. 상품 썸네일 및 대표 이미지 등록
    -- =====================================================
    delete from public.product_images where product_id in (
        v_prod_crop_id, v_prod_pants_id, v_prod_jacket_id, v_prod_dress_id, 
        v_prod_necklace_id, v_prod_heels_id, v_prod_vest_id, v_prod_glasses_id
    );

    insert into public.product_images (product_id, image_url, display_order, is_thumbnail)
    values
        -- 1) 베이직 크롭 티셔츠 (티셔츠/상의 패션 이미지)
        (v_prod_crop_id, 'https://axokmzyhxgbrdaysjmlu.supabase.co/storage/v1/object/public/product-images/crop_tshirt.jpg', 1, true),
        (v_prod_crop_id, 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=800&q=80', 2, false),
        -- 2) 와이드 데님 팬츠 (청바지/데님 팬츠 패션 이미지)
        (v_prod_pants_id, 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=800&q=80', 1, true),
        (v_prod_pants_id, 'https://images.unsplash.com/photo-1582552938357-32b906df40cb?auto=format&fit=crop&w=800&q=80', 2, false),
        -- 3) 오버핏 코튼 자켓 (자켓/아우터 패션 이미지)
        (v_prod_jacket_id, 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=800&q=80', 1, true),
        -- 4) 플로럴 미디 원피스 (원피스/드레스 패션 이미지)
        (v_prod_dress_id, 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=800&q=80', 1, true),
        -- 5) 클래식 하얀색 진주목걸이 (진주 목걸이/액세서리 패션 이미지)
        (v_prod_necklace_id, 'https://axokmzyhxgbrdaysjmlu.supabase.co/storage/v1/object/public/product-images/pearl_necklace.png', 1, true),
        -- 6) 슬림라인 에나멜 스틸레토 힐 (신발 패션 이미지)
        (v_prod_heels_id, 'https://axokmzyhxgbrdaysjmlu.supabase.co/storage/v1/object/public/product-images/stiletto_heels.png', 1, true),
        -- 7) 클래식 V넥 니트 베스트 (상의 패션 이미지)
        (v_prod_vest_id, 'https://axokmzyhxgbrdaysjmlu.supabase.co/storage/v1/object/public/product-images/knit_vest.png', 1, true),
        -- 8) 빈티지 레오파드 호피 안경 (액세서리 패션 이미지)
        (v_prod_glasses_id, 'https://axokmzyhxgbrdaysjmlu.supabase.co/storage/v1/object/public/product-images/leopard_glasses.png', 1, true);

end $$;

-- =====================================================
-- 5. 삽입 결과 검증 쿼리
-- =====================================================
select 
    c.name as 카테고리,
    p.name as 상품명,
    p.price as 정가,
    p.discount_rate as "할인율(%)",
    round(p.price * (1 - p.discount_rate / 100)) as 실판매가,
    count(distinct o.id) as 옵션수,
    count(distinct i.id) as 이미지수
from public.products p
join public.categories c on p.category_id = c.id
left join public.product_options o on p.id = o.product_id
left join public.product_images i on p.id = i.product_id
group by c.name, p.name, p.price, p.discount_rate
order by p.price desc;
