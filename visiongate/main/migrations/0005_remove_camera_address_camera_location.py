# Generated by Django 5.1.2 on 2024-11-03 03:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_location_changed_location_created_location_deleted_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='camera',
            name='address',
        ),
        migrations.AddField(
            model_name='camera',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='main.location', verbose_name='Локация'),
        ),
    ]
