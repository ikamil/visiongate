from django.contrib import admin
from .models import *
from main.admin import BaseAdmin


@admin.register(LocationUser)
class ProjectUserAdmin(BaseAdmin):
    fields = ['location', 'user']
    list_display = fields
    list_filter = ['location']
    search_fields = ('location__name', 'user__first_name', 'user__last_name')
    save_as = True
