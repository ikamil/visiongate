select * from main_event order by id desc;

select id, image, changed from main_event where nullif(trim(image),'') is not null and changed < (current_date-8) order by id;
--		return list(Event.objects.raw("select pk, image, changed from main_event where changed<current_date order by id limit :cnt+1", cnt)[:cnt + 1].values("pk", "image", "changed"))

with photos as (select id, count(1) over (order by id) from main_event where length(trim(image))>0)
select id, image, changed from main_event where nullif(trim(image),'') is not null and changed < (current_date) order by id limit :cnt+1;

select * from main_event where image is not null;

select * from main_event where cloud_url is not null;

select * from main_event  where changed<='2024-12-21 15:07' and image is not null;

update main_event set image=null where changed<='2024-12-21 15:07' and image is not null;