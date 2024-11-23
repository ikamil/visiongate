from django.contrib import admin
from django.db.models import Q
from datetime import datetime
from .models import *
from django.utils.safestring import mark_safe
from django.conf.locale.es import formats as es_formats
from import_export.admin import ExportMixin
from import_export.formats.base_formats import CSV


es_formats.DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
es_formats.SHORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

class BaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    fields = ['name', 'description']
    save_as = True
    readonly_fields = ['deleted']

    def get_queryset(self, request):
        qs = super(BaseAdmin, self).get_queryset(request)
        if request.user.groups.filter(name="admin") or request.user.is_superuser:
            return qs.filter(deleted__isnull=True)
        else:
            return qs.filter(Q(deleted__isnull=True) & (Q(owner=request.user) | Q(owner__isnull=True)))

    def get_form(self, request, obj=None, **kwargs):
        request._obj_ = obj
        return super(BaseAdmin, self).get_form(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def delete_model(self, request, obj):
        obj.deleted = datetime.now()
        obj.save()

    def delete_queryset(self, request, queryset):
        for dl in queryset:
            self.delete_model(request, dl)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        readonly_always = ("owner", )
        if not (request.user.groups.filter(name="admin") or request.user.is_superuser):
            for ro in readonly_always:
                if hasattr(obj, ro):
                    fields += ro
        return fields

    def save_model(self, request, obj, form, change):
        obj.changed = datetime.now()
        if hasattr(obj, "created"):
            obj.created = datetime.now() if not getattr(obj, "created") else getattr(obj, "created")
        _user = request.user
        if hasattr(obj, "owner"):
            if not getattr(obj, "owner"):
                obj.owner = _user
        if hasattr(obj, "changer"):
            obj.changer = _user
        return super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if "/change/" in request.__str__() and request.__str__() != getattr(request, "_editing_document", False):  # query attribute
            return False
        return super(BaseAdmin, self).has_delete_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        if "/change/" in request.__str__() and type(self) != getattr(request, "_editing_document", False):  # query attribute
            return False
        return super(BaseAdmin, self).has_change_permission(request, obj=obj)

    def _changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        request._editing_document = type(self)
        return super(BaseAdmin, self)._changeform_view(request, object_id=object_id, form_url=form_url, extra_context=extra_context)


@admin.register(Location)
class LocationAdmin(BaseAdmin):
    fields = ["code", "name", "address", "allowed", "device", "status", "description"]
    list_display = ("code", "name", "address", "device", "status")
    search_fields = ("code", "name", "address")


@admin.register(Camera)
class CameraAdmin(BaseAdmin):
    def videopreview(self, obj):
        return mark_safe('<video controls width="450"><source src="%s" type="video/mp4" /></video>' % obj.sample.url)
    videopreview.short_description = "Просмотр примера оригинала видео"

    def controlpreview(self, obj):
        return mark_safe(f"""<div id="iframe"><div style="background-color: #EBEBEB; cursor: pointer" 
        onClick="var frm = document.getElementById('iframe'); console.log(frm); var fr = document.createElement('iframe');
        fr.src = 'https://visiongate.ru/video/{obj.id}/';  fr.width = 600; fr.height = 300;
        frm.appendChild(fr);"><strong>Включить модель детекции образов.</strong>"!" - обнаружено</div></div>""")
    controlpreview.short_description = "Просмотр контроля"

    readonly_fields = ("videopreview", "controlpreview", )
    fields = ["code", "title", "name", "inout", "sample", "videopreview", "url", "controlpreview", "location", "description"]
    list_display = ("code", "title", "inout", "sample", "url", "location")
    list_filter = ("location",)
    search_fields = ("code", "title", "name", "sample", "url", "location__name")


@admin.register(Event)
class EventAdmin(ExportMixin, BaseAdmin):
    fields = ["location", "camera", "inout", "payload", "created"]
    list_display = ("created", "location", "camera", "inout")
    list_filter = ("location",)
    search_fields = ("camera__name", "camera__url", "location__name", "location__address")

    def get_export_formats(self):
        return [CSV]
