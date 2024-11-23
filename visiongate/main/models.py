from django.db import models
from django.conf import settings
from django.utils.timezone import now


def imgpath(instance, filename):
    return "files/{0}/{1}".format(instance.id, filename)


STATUS = (
    ("OPEN", "Открыт"),
    ("CLOSED", "Закрыт"),
    ("OPENING", "Открывается"),
    ("CLOSING", "Закрывается"),
)

class Location(models.Model):
    code = models.CharField(verbose_name="Код", max_length=255, unique=True)
    name = models.CharField(verbose_name="Наименование", max_length=500, blank=True, null=True)
    address = models.CharField(verbose_name="Адрес", max_length=500, blank=True, null=True)
    allowed = models.TextField(verbose_name="Разрешённые", blank=True, null=True)
    device = models.CharField(verbose_name="Устройство", max_length=500, blank=True, null=True)
    status = models.CharField(verbose_name="Статус", choices=STATUS, default="CLOSED", max_length=7)
    description = models.TextField(verbose_name="Описание", blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True, verbose_name="Владелец")
    created = models.DateTimeField(default=now)
    changed = models.DateTimeField(default=now)
    deleted = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Локация"
        verbose_name_plural = "Локации"

    def __str__(self):
        return self.name or self.code


IN_OUT = (
    ("IN", "Вход"),
    ("OUT", "Выход"),
)

class Camera(models.Model):
    code = models.CharField(verbose_name="Код", max_length=255, unique=True)
    location = models.ForeignKey(Location, verbose_name="Локация", on_delete=models.PROTECT, blank=True, null=True)
    title = models.CharField(verbose_name="Заголовок", max_length=65, default="")
    name = models.CharField(verbose_name="Наименование", max_length=500, blank=True, null=True)
    inout = models.CharField(verbose_name="Направление", choices=IN_OUT, default="IN", max_length=5)
    sample = models.FileField(verbose_name="Пример видео", upload_to=imgpath, blank=True, null=True)
    url = models.CharField(verbose_name="Адрес потока rstp", blank=True, null=True, help_text="rtsp://admin:@192.168.1.219:554/out.h264")
    description = models.TextField(verbose_name="Описание", blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True, verbose_name="Владелец")
    created = models.DateTimeField(default=now)
    changed = models.DateTimeField(default=now)
    deleted = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Камера"
        verbose_name_plural = "Камеры"

    def __str__(self):
        return self.title


class Event(models.Model):
    location = models.ForeignKey(Location, verbose_name="Локация", on_delete=models.PROTECT, related_name="+")
    camera = models.ForeignKey(Camera, verbose_name="Камера", on_delete=models.PROTECT)
    inout = models.CharField(verbose_name="Направление", choices=IN_OUT, default="IN", max_length=5)
    payload = models.CharField(verbose_name="Объекты", max_length=2000, blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True, verbose_name="Владелец")
    created = models.DateTimeField(default=now, verbose_name="Дата и время")
    changed = models.DateTimeField(default=now)
    deleted = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __str__(self):
        return f"{self.location}-{self.inout}-{self.created}"
