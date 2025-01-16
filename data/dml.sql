select * from main_event where image is not null;

select * from main_event where cloud_url is not null;

select * from main_event  where changed<='2024-12-21 15:07' and image is not null;

update main_event set image=null where changed<='2024-12-21 15:07' and image is not null;