-- =====================================================
-- Day 5: product_options 테이블 마이그레이션 SQL
-- =====================================================

-- [1] color, size, stock 컬럼 추가
alter table public.product_options
    add column if not exists color text,
    add column if not exists size text,
    add column if not exists stock integer default 0;

-- [2] 기존 option_type / option_value 혹은 name / value 컬럼이 not null인 경우를 대비해 널 허용 처리
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'product_options' and column_name = 'option_type'
    ) then
        alter table public.product_options alter column option_type drop not null;
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'product_options' and column_name = 'option_value'
    ) then
        alter table public.product_options alter column option_value drop not null;
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'product_options' and column_name = 'name'
    ) then
        alter table public.product_options alter column name drop not null;
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'product_options' and column_name = 'value'
    ) then
        alter table public.product_options alter column value drop not null;
    end if;
end $$;

-- [3] UNIQUE 제약 추가: (product_id, color, size)
-- color와 size가 둘 다 NULL이 아닌 유효한 조합 행에 대해서만 중복을 방지하는 조건부 고유 인덱스(Partial Unique Index) 생성
create unique index if not exists uq_product_options_product_color_size
on public.product_options (product_id, color, size)
where color is not null and size is not null;
