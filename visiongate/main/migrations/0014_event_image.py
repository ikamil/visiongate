# Generated by Django 5.1.4 on 2024-12-18 19:12

import main.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0013_location_opened_by_location_opened_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=main.models.imgpath, verbose_name='Фото'),
        ),
    ]
