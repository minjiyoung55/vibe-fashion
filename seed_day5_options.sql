-- =====================================================
-- Day 5: 상품별 색상 × 사이즈 재고 Seed SQL
-- =====================================================
-- 1. products 테이블의 실제 id를 조회하여 동적으로 연결
-- 2. 상품별 색상 2~3종 × 사이즈 3종(S, M, L) = 6~9개 옵션 조합
-- 3. 재고는 품절(0), 품절임박(1), 충분(10~30)을 다양하게 배분
-- 4. uq_product_options_product_color_size 고유 제약에 맞춰 중복 시 업데이트 처리

do $$
declare
    r_prod record;
    v_colors text[];
    v_sizes text[] := array['S', 'M', 'L'];
    v_color text;
    v_size text;
    v_idx integer;
    v_stock integer;
    v_stocks integer[] := array[0, 1, 15, 25, 1, 0, 30, 20, 1]; -- 품절(0), 품절임박(1), 충분(10~30) 혼합
begin
    -- 등록된 모든 상품을 순회
    for r_prod in (select id, name, category_id from public.products order by created_at) loop
        v_idx := 1;

        -- 상품 특성에 어울리는 색상 2~3개 지정
        if r_prod.name like '%데님%' or r_prod.name like '%청%' then
            v_colors := array['Light Blue', 'Deep Blue', 'Black'];
        elsif r_prod.name like '%원피스%' or r_prod.name like '%드레스%' then
            v_colors := array['Ivory', 'Sky Blue', 'Black'];
        elsif r_prod.name like '%니트%' or r_prod.name like '%베스트%' then
            v_colors := array['Beige', 'Navy', 'Charcoal'];
        elsif r_prod.name like '%목걸이%' or r_prod.name like '%악세%' or r_prod.name like '%안경%' then
            v_colors := array['Silver', 'Gold'];
        elsif r_prod.name like '%힐%' or r_prod.name like '%슈즈%' or r_prod.name like '%구두%' then
            v_colors := array['Black', 'Cream', 'Red'];
        else
            -- 기본 의류 (티셔츠, 자켓 등)
            v_colors := array['White', 'Black', 'Oatmeal'];
        end if;

        -- 색상 × 사이즈 조합 생성 후 insert
        foreach v_color in array v_colors loop
            foreach v_size in array v_sizes loop
                -- 테스트용 재고 패턴 선택 (0: 품절, 1: 품절임박, 10~30: 여유)
                v_stock := v_stocks[((v_idx - 1) % array_length(v_stocks, 1)) + 1];

                insert into public.product_options (
                    product_id,
                    color,
                    size,
                    stock,
                    option_type,
                    option_value,
                    additional_price,
                    stock_quantity
                )
                values (
                    r_prod.id,
                    v_color,
                    v_size,
                    v_stock,
                    'COMBINATION',
                    v_color || ' / ' || v_size,
                    0,
                    v_stock
                )
                on conflict (product_id, color, size) where color is not null and size is not null
                do update set
                    stock = excluded.stock,
                    stock_quantity = excluded.stock_quantity;

                v_idx := v_idx + 1;
            end loop;
        end loop;
    end loop;
end $$;

-- 등록된 옵션 데이터 확인용 조회
select 
    p.name as 상품명,
    po.color as 색상,
    po.size as 사이즈,
    po.stock as 재고,
    case 
        when po.stock = 0 then '품절'
        when po.stock = 1 then '품절 임박 (1개 남음)'
        else '재고 충분'
    end as 상태
from public.product_options po
join public.products p on p.id = po.product_id
where po.color is not null and po.size is not null
order by p.name, po.color, po.size;
