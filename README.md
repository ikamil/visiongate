# visiongate
Система контроля проезда на основе анализа номерных знаков

# Принципиальная архитектура системы
1. Распознавание bounding-box образов номерных знаков на основе YOLO модели, обученной на распознавание номерных знаков
2. OCR-распознавание текста внутри bounding-box зон кадра
3. Django-админ-панель в качестве развёртывания самой модели и настройки управления системой
4. Локации - сущность, где устанавливаются источники видео-потоков
5. Локации содержат списки Разрешённых номерных знаков (соответствующее поле-список)
6. Камеры - привязываются к Локации, имеют Направление, а также и включают rstp ссылки и примеры файлов видеопотока
7. События - журнал распознанных в Локации объектов-номеров, при совпадении из списка из Разрешённых

# Бизнес-ценность
1. Локальное или облачное решение по контролю доступа на базе стандартного ПК
2. Возможность подключения любых rstp-источников, например rtsp-ip-камер
3. Аналитика событий: и в web-интерфейсе, и в БД Postgres
4. Возможность удобной настройки разрешённых номеров в web-интерфейсе
5. Возможность расширения YOLO модели распознавания образов посредством дообучения
6. Возможность расширить функционал, например реализовать распознавание лиц при наличии GPU
7. Выгрузка CSV-файла событий

# Основные файлы, реализующие работу модели и приложения
- visiongate/main/models.py - схема данных
- visiongate/main/views.py - работа с onnx моделью в ендпойнте Django
- visiongate/main/numberplate.py - iou-вычисление bounding-box и запуск PaddleOCR
- visiongate/main/admin.py - интерфейсная часть админ-панели
- Итоговая_Аттестация.ipynb - обучение модели, выгрузка ONNX, принципиальная проверка работоспособности
- https://colab.research.google.com/drive/1IGudyk6Hvj-adFBQs86s-ol0WK_IQwB4?usp=drive_link - Colab-демонстрация работы модели и распознавания

# Настройка локаций и камер
1. Авторизоваться на сайте https://visiongate.ru/admin
2. Перейти в раздел Локации https://visiongate.ru/admin/main/location/, нажать Создать
3. Указать в поле "Разрешённые" построчный список разрешённых номерных знаков
4. Перейти в раздел Камеры https://visiongate.ru/admin/main/camera/, нажать Создать
5. Указать Локацию, Направление (вход-выход), загрузить демо-ролик и указать rtsp ссылку на камеру

# Просмотр анализа видеопотока
1. Выбрать любую из камер https://visiongate.ru/admin/main/camera/
2. Открыть детальную информацию по камере, например https://visiongate.ru/admin/main/camera/2/change/
3. Демонстрационное видео можно просмотреть в блоке **Просмотр пример видео**
4. Демонстрацию работы ML-модели распознавания bounding-box образов номерного знака, и последующего распознанного текста - можно посмотреть в блоке **Просмотр контроля**  

# Установка
## Скачивание и запуск docker compose сборки
1. `git clone https://github.com/ikamil/visiongate.git`
2. `cd visiongate`
3. `docker compose up -d`

## Создание БД
```
root@lkwuthwrux:~# docker exec -it visiongate-pg-1 bash
root@17d007ef0c92:/# su - postgres
postgres@17d007ef0c92:~$ psql
psql (17.0 (Debian 17.0-1.pgdg120+1))
Type "help" for help.

postgres=# create user visiongate password 'visiongate' login;
postgres=# create database visiongate owner visiongate;
```
## Опционально: или раскат текущего дампа демо-данных БД
```
root@lkwuthwrux:~# docker exec -it visiongate-pg-1 bash
root@17d007ef0c92:/# su - postgres
postgres@17d007ef0c92:~$ cat /tmp/data/visiongate.sql > psql visiongate
```
## Опционально: или создание админ-юзера и раскатка миграций
```
root@lkwuthwrux:~# docker exec -it visiongate-python-1 bash
root@8225c6af5bbb:/# python /code/visiongate/manage.py createsuperuser
root@8225c6af5bbb:/# python /code/visiongate/manage.py makemigrations
root@8225c6af5bbb:/# python /code/visiongate/manage.py migrate
```
