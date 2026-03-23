# visiongate
License plate recognition-based access control system

# Core system architecture
1. Bounding-box detection of license plate images using a YOLO model trained for license plate recognition
2. OCR text recognition within bounding-box zones of the frame
3. Django admin panel as the deployment interface for the model and system configuration
4. Locations — entities where video stream sources are configured
5. Locations contain lists of Allowed license plates (corresponding list field)
6. Cameras — linked to a Location, have a Direction, and include rtsp links and sample video stream files
7. Events — a log of recognized license plate objects within a Location, triggered on match with the Allowed list

# Business value
1. Local or cloud-based access control solution running on a standard PC
2. Support for any rtsp sources, such as rtsp IP cameras
3. Event analytics: both in the web interface and in the Postgres database
4. Convenient management of allowed license plates via the web interface
5. Ability to extend the YOLO recognition model through fine-tuning
6. Ability to extend functionality, e.g. implement face recognition with a GPU available
7. CSV export of events

# Core files implementing the model and application
- visiongate/main/models.py - data schema
- visiongate/main/views.py - ONNX model handling in the Django endpoint
- visiongate/main/numberplate.py - IOU bounding-box calculation and PaddleOCR execution
- visiongate/main/admin.py - admin panel interface layer
- Итоговая_Аттестация.ipynb - model training, ONNX export, and basic functionality verification
- https://colab.research.google.com/drive/1IGudyk6Hvj-adFBQs86s-ol0WK_IQwB4?usp=drive_link - Colab demo of the model and recognition workflow

# Configuring locations and cameras
1. Log in at https://visiongate.ru/admin
2. Go to the Locations section https://visiongate.ru/admin/main/location/, click Create
3. Enter a line-by-line list of allowed license plates in the "Allowed" field
4. Go to the Cameras section https://visiongate.ru/admin/main/camera/, click Create
5. Specify the Location, Direction (entry/exit), upload a demo video, and enter the rtsp link to the camera

# Viewing video stream analysis
1. Select any camera at https://visiongate.ru/admin/main/camera/
2. Open the camera detail page, e.g. https://visiongate.ru/admin/main/camera/2/change/
3. The demo video can be viewed in the **Sample video preview** block
4. The ML model's bounding-box detection and subsequent text recognition can be viewed in the **Access control preview** block

# Installation
## Downloading and running the Docker Compose build
1. `git clone https://github.com/ikamil/visiongate.git`
2. `cd visiongate`
3. `docker compose up -d`

## Creating the database
```
root@lkwuthwrux:~# docker exec -it visiongate-pg-1 bash
root@17d007ef0c92:/# su - postgres
postgres@17d007ef0c92:~$ psql
psql (17.0 (Debian 17.0-1.pgdg120+1))
Type "help" for help.

postgres=# create user visiongate password 'visiongate' login;
postgres=# create database visiongate owner visiongate;
```
## Optional: restore the current demo database dump
```
root@lkwuthwrux:~# docker exec -it visiongate-pg-1 bash
root@17d007ef0c92:/# su - postgres
postgres@17d007ef0c92:~$ cat /tmp/data/visiongate.sql > psql visiongate
```
## Optional: create an admin user and run migrations
```
root@lkwuthwrux:~# docker exec -it visiongate-python-1 bash
root@8225c6af5bbb:/# python /code/visiongate/manage.py createsuperuser
root@8225c6af5bbb:/# python /code/visiongate/manage.py makemigrations
root@8225c6af5bbb:/# python /code/visiongate/manage.py migrate
```
