from django.db import models
from django.conf import settings
from django.utils.timezone import now
from main.models import Location


class LocationUser(models.Model):
    location = models.ForeignKey(Location, related_name='+', verbose_name='Локация', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='+', verbose_name='Пользователь', on_delete=models.DO_NOTHING)
    created = models.DateTimeField(default=now)
    changed = models.DateTimeField(default=now)
    deleted = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Доступ к локации'
        verbose_name_plural = 'Доступы к локациям'

    def __str__(self):
        return "%s => %s" % (self.location.__str__(), self.user.__str__())
