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


BTN_TEMPLATE = """<div style="display: inline-grid; width: 125px; height: 40px; line-height: 40px; border-style: groove; background-color: #EBEBEB; cursor: pointer; text-align: center;" id="%s"
    onClick="fetch('/%s/%s').then(function(res){return res.json();}).then(function(data) {document.getElementById('status').textContent = data.status_title;})">%s</div>"""


@admin.register(Location)
class LocationAdmin(BaseAdmin):
    def location_control(self, obj):
        return mark_safe(BTN_TEMPLATE % ("status", "open" if str(obj.status).startswith("CLOS") else "close", obj.id, "🔄 " + obj.location.get_status_display()))

    location_control.short_description = "Нажать кнопку"
    readonly_fields = ("location_control", )
    fields = ["code", "name", "address", "allowed", "device", "location_control", "status", "mode", "description"]
    list_display = ("code", "name", "address", "device", "status")
    search_fields = ("code", "name", "address")


@admin.register(Camera)
class CameraAdmin(BaseAdmin):
    def videopreview(self, obj):
        return mark_safe(f'<video controls width="450"><source src="{obj.sample.url}" type="video/mp4"/></video>' if not obj.url else """
        <div id="vid"><div id="click" style="background-color: #EBEBEB; cursor: pointer" onClick=
        "let str = document.getElementById('stream'); str.src = ''; str.src = 'https://visiongate.ru/video/%s/';">     
        <img id="stream" src="https://visiongate.ru/video/%s" alt="Просмотр видео"/>
        <strong>Перезапустить</strong></div><script>let clk = document.getElementById('click');</script></div>""" % (obj.id, obj.id))
    videopreview.short_description = "Просмотр видео"

    def controlpreview(self, obj):
        return mark_safe("""<div id="iframe"><div id="click" style="background-color: #EBEBEB; cursor: pointer" 
        onClick="var frm = document.getElementById('iframe'); let ifrm = document.getElementById('ifrm'); if (ifrm) ifrm.remove(); var fr = document.createElement('iframe');
        fr.id = 'ifrm'; fr.src = 'https://visiongate.ru/video/%s/';  fr.width = 600; fr.height = 300; fr.onLoad = function () {document.getElementById('click').click();}
        frm.appendChild(fr);"><strong>Включить модель детекции образов.</strong>"!" - обнаружено</div></div>""" % obj.id)
    controlpreview.short_description = "Просмотр контроля"

    def location_control(self, obj):
        return mark_safe(
            (BTN_TEMPLATE % ("status", "status", obj.id, "🔄 " + obj.location.get_status_display())
            ) + (BTN_TEMPLATE % ("open", "open", obj.id, "Открыть")
            ) + (BTN_TEMPLATE % ("close", "close", obj.id, "Закрыть"))
        )

    location_control.short_description = "Управление"

    readonly_fields = ("videopreview", "controlpreview", "location_control")
    fields = ["code", "title", "name", "inout", "sample", "videopreview", "url", "location_control", "location", "description"]
    list_display = ("code", "title", "inout", "sample", "url", "location")
    list_filter = ("location",)
    search_fields = ("code", "title", "name", "sample", "url", "location__name")


@admin.register(Event)
class EventAdmin(ExportMixin, BaseAdmin):
    def imagepreview(self, obj):
        return mark_safe(f'<img src="%s" alt="Фото" width="560px"/>' % obj.image.url)
    imagepreview.short_description = "Фото"

    fields = ["location", "camera", "inout", "status", "created", "payload", "image", "imagepreview"]
    list_display = ("created", "location", "camera", "inout", "status", "payload")
    list_filter = ("location", "status")
    readonly_fields = ("imagepreview",)
    search_fields = ("payload",)

    def get_export_formats(self):
        return [CSV]
