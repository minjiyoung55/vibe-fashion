-- =====================================================
-- VIBE-FASHION 쇼핑몰 데이터베이스 스키마
-- Supabase SQL Editor 실행용
-- =====================================================

-- 0. 확장 기능 활성화
create extension if not exists "uuid-ossp";

-- =====================================================
-- 1. 공통 트리거 함수 (updated_at 자동 갱신)
-- =====================================================

create or replace function public.update_updated_at_column()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- =====================================================
-- 2. profiles (사용자 프로필)
-- auth.users와 1:1 연결
-- =====================================================

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique,
    full_name text,
    avatar_url text,
    phone text,
    role text default 'CUSTOMER' check (role in ('CUSTOMER', 'ADMIN')),
    customer_grade text default 'BRONZE' check (
        customer_grade in ('BRONZE', 'SILVER', 'GOLD', 'VIP')
    ),
    total_order_amount numeric(12, 2) default 0 check (total_order_amount >= 0),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 3. categories (상품 카테고리)
-- =====================================================

create table if not exists public.categories (
    id bigserial primary key,
    name text not null,
    slug text not null unique,
    description text,
    parent_id bigint references public.categories(id) on delete set null,
    is_active boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_categories_updated_at on public.categories;
create trigger trg_categories_updated_at
before update on public.categories
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 4. products (상품)
-- =====================================================

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    category_id bigint references public.categories(id) on delete set null,
    name text not null,
    slug text unique,
    description text,
    price numeric(12, 2) not null check (price >= 0),
    discount_rate numeric(5, 2) default 0 check (discount_rate between 0 and 100),
    stock_quantity integer not null default 0 check (stock_quantity >= 0),
    status text default 'ON_SALE' check (status in ('ON_SALE', 'OUT_OF_STOCK', 'HIDDEN')),
    is_active boolean default true,
    is_featured boolean default false,
    thumbnail_url text,
    view_count integer default 0 check (view_count >= 0),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_products_updated_at on public.products;
create trigger trg_products_updated_at
before update on public.products
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 5. product_options (상품 옵션: 사이즈, 컬러 등)
-- =====================================================

create table if not exists public.product_options (
    id bigserial primary key,
    product_id uuid not null references public.products(id) on delete cascade,
    option_type text not null, -- 예: 'COLOR', 'SIZE'
    option_value text not null, -- 예: 'BLACK', 'XL'
    additional_price numeric(12, 2) default 0,
    stock_quantity integer not null default 0 check (stock_quantity >= 0),
    created_at timestamptz default now()
);

-- =====================================================
-- 6. product_images (상품 이미지)
-- =====================================================

create table if not exists public.product_images (
    id bigserial primary key,
    product_id uuid not null references public.products(id) on delete cascade,
    image_url text not null,
    display_order integer default 0,
    is_thumbnail boolean default false,
    created_at timestamptz default now()
);

-- =====================================================
-- 7. carts (장바구니)
-- =====================================================

create table if not exists public.carts (
    id bigserial primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete cascade,
    option_id bigint references public.product_options(id) on delete set null,
    quantity integer not null default 1 check (quantity > 0),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (user_id, product_id, option_id)
);

drop trigger if exists trg_carts_updated_at on public.carts;
create trigger trg_carts_updated_at
before update on public.carts
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 8. orders (주문)
-- =====================================================

create table if not exists public.orders (
    id uuid primary key default gen_random_uuid(),
    order_number text not null unique,
    user_id uuid not null references public.profiles(id) on delete restrict,
    total_amount numeric(12, 2) not null check (total_amount >= 0),
    discount_amount numeric(12, 2) default 0 check (discount_amount >= 0),
    final_amount numeric(12, 2) not null check (final_amount >= 0),
    status text default 'PENDING' check (
        status in ('PENDING', 'PAID', 'PREPARING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED')
    ),
    recipient_name text not null,
    recipient_phone text not null,
    shipping_address text not null,
    shipping_memo text,
    payment_method text not null,
    payment_key text,
    paid_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_orders_updated_at on public.orders;
create trigger trg_orders_updated_at
before update on public.orders
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 9. order_items (주문 상세 항목)
-- =====================================================

create table if not exists public.order_items (
    id bigserial primary key,
    order_id uuid not null references public.orders(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    option_id bigint references public.product_options(id) on delete set null,
    product_name text not null,
    option_description text,
    unit_price numeric(12, 2) not null check (unit_price >= 0),
    quantity integer not null check (quantity > 0),
    subtotal_price numeric(12, 2) not null check (subtotal_price >= 0),
    created_at timestamptz default now()
);

-- =====================================================
-- 10. refunds (환불 / 취소)
-- =====================================================

create table if not exists public.refunds (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references public.orders(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    reason text not null,
    refund_amount numeric(12, 2) not null check (refund_amount >= 0),
    status text default 'REQUESTED' check (
        status in ('REQUESTED', 'APPROVED', 'REJECTED', 'COMPLETED')
    ),
    admin_memo text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_refunds_updated_at on public.refunds;
create trigger trg_refunds_updated_at
before update on public.refunds
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 11. notifications (알림)
-- =====================================================

create table if not exists public.notifications (
    id bigserial primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    title text not null,
    message text not null,
    link_url text,
    is_read boolean default false,
    created_at timestamptz default now()
);

-- =====================================================
-- 12. reviews (상품 리뷰)
-- =====================================================

create table if not exists public.reviews (
    id bigserial primary key,
    product_id uuid not null references public.products(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    order_item_id bigint references public.order_items(id) on delete set null,
    rating integer not null check (rating between 1 and 5),
    content text not null,
    image_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

drop trigger if exists trg_reviews_updated_at on public.reviews;
create trigger trg_reviews_updated_at
before update on public.reviews
for each row
execute function public.update_updated_at_column();

-- =====================================================
-- 13. 소셜/일반 회원가입 시 프로필 자동 생성 트리거 함수
-- =====================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
    v_full_name text;
    v_avatar_url text;
begin
    -- OAuth 제공자(Google, Kakao 등) 및 일반 메타데이터 대응
    v_full_name := coalesce(
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'name',
        new.raw_user_meta_data->>'user_name',
        split_part(new.email, '@', 1)
    );

    v_avatar_url := coalesce(
        new.raw_user_meta_data->>'avatar_url',
        new.raw_user_meta_data->>'picture'
    );

    insert into public.profiles (
        id,
        email,
        full_name,
        avatar_url,
        phone,
        customer_grade,
        total_order_amount
    )
    values (
        new.id,
        new.email,
        v_full_name,
        v_avatar_url,
        new.phone,
        'BRONZE',
        0
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        avatar_url = coalesce(public.profiles.avatar_url, excluded.avatar_url),
        phone = coalesce(public.profiles.phone, excluded.phone),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();

-- =====================================================
-- 14. 고객 등급 및 누적 결제금액 자동 업데이트 함수 & 트리거
-- 등급 기준:
-- VIP: 1,000,000원 이상
-- GOLD: 500,000원 이상 ~ 1,000,000원 미만
-- SILVER: 200,000원 이상 ~ 500,000원 미만
-- BRONZE: 200,000원 미만
-- =====================================================

create or replace function public.update_customer_grade(target_user_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_total_paid numeric(12, 2);
    v_new_grade text;
begin
    -- 정상 결제 및 배송 완료 건에 대한 누적 결제액 합산 (취소/환불 제외)
    select coalesce(sum(final_amount), 0)
    into v_total_paid
    from public.orders
    where user_id = target_user_id
      and status in ('PAID', 'PREPARING', 'SHIPPED', 'DELIVERED');

    if v_total_paid >= 1000000 then
        v_new_grade := 'VIP';
    elsif v_total_paid >= 500000 then
        v_new_grade := 'GOLD';
    elsif v_total_paid >= 200000 then
        v_new_grade := 'SILVER';
    else
        v_new_grade := 'BRONZE';
    end if;

    update public.profiles
    set
        total_order_amount = v_total_paid,
        customer_grade = v_new_grade,
        updated_at = now()
    where id = target_user_id;
end;
$$;

-- 주문 상태 변경/생성 시 고객 등급 갱신 트리거 함수
create or replace function public.trg_fn_sync_customer_grade_on_order()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    if (tg_op = 'INSERT') then
        perform public.update_customer_grade(new.user_id);
    elsif (tg_op = 'UPDATE') then
        if (old.status is distinct from new.status) or (old.final_amount is distinct from new.final_amount) then
            perform public.update_customer_grade(new.user_id);
        end if;
    elsif (tg_op = 'DELETE') then
        perform public.update_customer_grade(old.user_id);
    end if;
    return null;
end;
$$;

drop trigger if exists trg_sync_customer_grade on public.orders;
create trigger trg_sync_customer_grade
after insert or update or delete on public.orders
for each row
execute function public.trg_fn_sync_customer_grade_on_order();

-- =====================================================
-- 15. 인덱스 설정 (성능 최적화)
-- =====================================================

create index if not exists idx_products_category on public.products(category_id);
create index if not exists idx_products_status on public.products(status);
create index if not exists idx_product_images_product on public.product_images(product_id);
create index if not exists idx_product_options_product on public.product_options(product_id);
create index if not exists idx_carts_user on public.carts(user_id);
create index if not exists idx_orders_user on public.orders(user_id);
create index if not exists idx_orders_status on public.orders(status);
create index if not exists idx_order_items_order on public.order_items(order_id);
create index if not exists idx_reviews_product on public.reviews(product_id);
create index if not exists idx_notifications_user on public.notifications(user_id, is_read);

-- =====================================================
-- 16. Row Level Security (RLS) 정책
-- =====================================================

alter table public.profiles enable row level security;
alter table public.categories enable row level security;
alter table public.products enable row level security;
alter table public.product_options enable row level security;
alter table public.product_images enable row level security;
alter table public.carts enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.refunds enable row level security;
alter table public.notifications enable row level security;
alter table public.reviews enable row level security;

-- 16-1. profiles 정책
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
for select using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
for update using (auth.uid() = id);

-- 16-2. categories / products / options / images (모두 조회 가능)
drop policy if exists "categories_select_all" on public.categories;
create policy "categories_select_all" on public.categories
for select using (true);

drop policy if exists "products_select_active" on public.products;
create policy "products_select_active" on public.products
for select using (status in ('ON_SALE', 'OUT_OF_STOCK'));

drop policy if exists "product_options_select_all" on public.product_options;
create policy "product_options_select_all" on public.product_options
for select using (true);

drop policy if exists "product_images_select_all" on public.product_images;
create policy "product_images_select_all" on public.product_images
for select using (true);

-- 16-3. carts (본인 장바구니만 관리)
drop policy if exists "carts_select_own" on public.carts;
create policy "carts_select_own" on public.carts
for select using (auth.uid() = user_id);

drop policy if exists "carts_insert_own" on public.carts;
create policy "carts_insert_own" on public.carts
for insert with check (auth.uid() = user_id);

drop policy if exists "carts_update_own" on public.carts;
create policy "carts_update_own" on public.carts
for update using (auth.uid() = user_id);

drop policy if exists "carts_delete_own" on public.carts;
create policy "carts_delete_own" on public.carts
for delete using (auth.uid() = user_id);

-- 16-4. orders / order_items (본인 주문만 조회/생성)
drop policy if exists "orders_select_own" on public.orders;
create policy "orders_select_own" on public.orders
for select using (auth.uid() = user_id);

drop policy if exists "orders_insert_own" on public.orders;
create policy "orders_insert_own" on public.orders
for insert with check (auth.uid() = user_id);

drop policy if exists "order_items_select_own" on public.order_items;
create policy "order_items_select_own" on public.order_items
for select using (
    exists (
        select 1 from public.orders
        where orders.id = order_items.order_id
          and orders.user_id = auth.uid()
    )
);

-- 16-5. refunds (본인 환불 요청만 조회/생성)
drop policy if exists "refunds_select_own" on public.refunds;
create policy "refunds_select_own" on public.refunds
for select using (auth.uid() = user_id);

drop policy if exists "refunds_insert_own" on public.refunds;
create policy "refunds_insert_own" on public.refunds
for insert with check (auth.uid() = user_id);

-- 16-6. notifications (본인 알림만 조회/수정)
drop policy if exists "notifications_select_own" on public.notifications;
create policy "notifications_select_own" on public.notifications
for select using (auth.uid() = user_id);

drop policy if exists "notifications_update_own" on public.notifications;
create policy "notifications_update_own" on public.notifications
for update using (auth.uid() = user_id);

-- 16-7. reviews (조회는 전체, 작성/수정/삭제는 본인)
drop policy if exists "reviews_select_all" on public.reviews;
create policy "reviews_select_all" on public.reviews
for select using (true);

drop policy if exists "reviews_insert_own" on public.reviews;
create policy "reviews_insert_own" on public.reviews
for insert with check (auth.uid() = user_id);

drop policy if exists "reviews_update_own" on public.reviews;
create policy "reviews_update_own" on public.reviews
for update using (auth.uid() = user_id);

drop policy if exists "reviews_delete_own" on public.reviews;
create policy "reviews_delete_own" on public.reviews
for delete using (auth.uid() = user_id);
