select * from main_event order by id desc;

-- старфе фото на отправку в облако
select id, image, changed from main_event
		where nullif(trim(image), '') is not null and changed < (current_timestamp - interval '10 days')
		order by id limit 10 + 1;

-- подмена N-го символа в строке, в том числе с конца
create or replace function change(src text, i int, v text) returns text language sql immutable as $$
    select case when i = -1 then substr(src, 1, length(src) - 1) || v
        when i >= 0 then SUBSTRING(src FROM 1 FOR i + 1 - 1) || v || SUBSTRING(src FROM i + 1 + 1)
        else SUBSTRING(src FROM 1 FOR length(src) - i + 1 - 1) || v || SUBSTRING(src FROM length(src) - i + 1 + 1)
    end
$$;

-- подмена некорректных или похожих символов
create or replace function unify_replace(src text) returns text language plpgsql immutable as $$
declare res text := src;
REPLACE_ jsonb := '{"D": "0", "Q": "0", "O": "0", "R": "K", ".": "", ",": "", "/": "7", "V": "Y", "|": "", "I": "", " ": ""}';
r text; v text;
begin
    FOR r, v IN SELECT * FROM jsonb_each_text(REPLACE_) LOOP
--         RAISE NOTICE 'REPLACE %: % => %', res, r, v;
        res := replace(res, r, v);
    END LOOP;
    return res;
end;
$$;

-- Унификация номеров с подменой и заменой на позициях
create or replace function unify(src text) returns text language plpgsql immutable as $$
declare res text := unify_replace(src);
INPLACE jsonb := '{"0": {"4": "A", "X": "K", "V": "Y", "9": "B", "7": "T", "1": "T"},
		   "4,5": {"0": "C", "8": "B", "1": "T", "3": "B", "7": "T", "V": "Y", "X": "K", "9": "B"},
		   "1,2,3": {"B": "8", "A": "4"},
		   "6": {"M": "11"}}';
CHANGES jsonb := '{"10": {"7": ""}}';
r text; v text; i_ text; d jsonb; ii text;  i int; l_ text; c jsonb; ll text; l int;
begin
    for i_, d in SELECT * FROM jsonb_each(INPLACE) LOOP
        for r, v in SELECT * FROM jsonb_each_text(d) LOOP
            foreach ii in array string_to_array(i_, ',') loop
                i := ii::int;
                if length(res) > i and substr(res, i+1, 1) = r then
--                     RAISE NOTICE 'CHANGE %: % => % | i_=%| d=%| r=% | v=%', res, i, v, i_, d, r, v;
                    res = change(res, i, v);
                end if;
            end loop;
        end loop;
    end loop;

    for l_, c in SELECT * FROM jsonb_each(CHANGES) loop
        foreach ll in array string_to_array(l_, ',') loop
            l := ll::int;
            if length(res) = l then
                for i_, v in SELECT * FROM jsonb_each_text(c) loop
                    foreach ii in array string_to_array(i_,',') loop
                        i := ii::int;
                        if length(res) > i then
--                             RAISE NOTICE 'CHANGE2 %: % => %', res, i, v;
                            res := change(res, i, v);
                        end if;
                    end loop;
                end loop;
            end if;
        end loop;
    end loop;
    return res;
end;
$$;

-- поиск "своих" номеров на выезде
with src as (select (regexp_matches(payload, '''[0-9A-Z\.\/]{8,}''', 'g'))[1] mat, count(1) cnt, max(image) img
             from main_event where inout='OUT' and payload ~ '[A-Z]+' and nullif(trim(image), '') is not null group by mat),
    trm as (select cnt, img, trim(both '''' from mat) num, unify(trim(both '''' from mat)) uni from src) ,
    un as (select cnt, num, img, uni from trm where cnt > 1 or (num = uni and length(num) between 8 and 9)),
    cnts as (select uni, max(cnt) qty, count(distinct num) nums, max(img) image from un group by uni)
select distinct uni||' : '||qty||'-'||nums,  'https://visiongate.ru/uploads/'||image url, qty, nums
from cnts join un using (uni) where (qty > 1 or nums > 1 )
order by qty desc, nums desc;

-- <список из номеров> для добавления этих номеров на разрешение в локацию
with src as (select (regexp_matches(payload, '''[0-9A-Z\.\/]{8,}''', 'g'))[1] mat, count(1) cnt, max(image) img
             from main_event where inout='OUT' and payload ~ '[A-Z]+' and nullif(trim(image), '') is not null group by mat),
    trm as (select cnt, img, trim(both '''' from mat) num, unify(trim(both '''' from mat)) uni from src) ,
    un as (select cnt, num, img, uni from trm where cnt > 1 or (num = uni and length(num) between 8 and 9)),
    cnts as (select uni, max(cnt) qty, count(distinct num) nums, max(img) image from un group by uni)
select distinct unify_replace(num)
from cnts join un using (uni) where (qty > 1 or nums > 1);

-- шаблон запроса на обновление списка допустимых номеров
update main_location set allowed = allowed||chr(13)||'<список из номеров>' where id = '<ИД локации>';
