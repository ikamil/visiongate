# Generated by Django 5.1.2 on 2024-10-29 06:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='code',
            field=models.CharField(max_length=255, unique=True, verbose_name='Код'),
        ),
        migrations.AlterField(
            model_name='camera',
            name='url',
            field=models.CharField(blank=True, help_text='rtsp://admin:@192.168.1.219:554/out.h264', null=True, verbose_name='Адрес потока rstp'),
        ),
    ]
