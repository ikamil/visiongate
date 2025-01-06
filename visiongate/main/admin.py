from django.contrib import admin
from django.db.models import Q
from datetime import datetime
from .models import *
from management.models import LocationUser
from django.utils.safestring import mark_safe
from django.conf.locale.es import formats as es_formats
from django.contrib.auth.models import User
from django.contrib.admin import SimpleListFilter
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
                    fields += (ro, )
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


class LocationFilter(SimpleListFilter):
    title = 'Локация'
    parameter_name = 'Локация'
    model = None
    ids=set()

    def lookups(self, request, model_admin):
        if request.user.is_superuser or request.user.groups.filter(name='prorab'):
            locations = Location.objects.filter(deleted__isnull=True)
        else:
            self.ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
            locations = Location.objects.filter(Q(deleted__isnull=True) & (Q(pk__in=self.ids) | Q(owner=request.user) | Q(owner__isnull=True)))
        self.model = model_admin.model
        return [(c.id, c.name) for c in set([c for c in locations])]

    def queryset(self, request, queryset):
        if request.user.is_superuser or request.user.groups.filter(name='admin'):
            if self.value():
                return queryset.filter(Q(deleted__isnull=True) & Q(location=self.value()))
            else:
                return queryset.filter(Q(deleted__isnull=True))
        else:
            if hasattr(self.model, 'owner'):
                if self.value():
                    return queryset.filter(Q(deleted__isnull=True) & Q(location=self.value()) & (Q(owner=request.user) | Q(owner__isnull=True)))
                else:
                    self.ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
                    return queryset.filter(Q(deleted__isnull=True) & (Q(location__in=self.ids) | Q(owner=request.user) | Q(owner__isnull=True)))


class LocationUserAdmin(BaseAdmin):
    def render_change_form(self, request, context, *args, **kwargs):
         if request.user.is_superuser:
             if context['adminform'].form.fields.get('location'):
                context['adminform'].form.fields['location'].queryset = Location.objects.filter(deleted__isnull=True)
         else:
             ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
             if context['adminform'].form.fields.get('location'):
                context['adminform'].form.fields['location'].queryset = Location.objects.filter(Q(deleted__isnull=True) & (Q(id__in=ids) | Q(owner=request.user) | Q(owner__isnull=True)))
         return super(LocationUserAdmin, self).render_change_form(request, context, *args, **kwargs)

    def get_queryset(self, request):
        qs = super(BaseAdmin, self).get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name='admin'):
            return qs.filter(deleted__isnull=True)
        else:
            ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location',flat=True)
            return qs.filter(Q(deleted__isnull=True) & (Q(owner=request.user) | Q(owner__isnull=True) | Q(location__in=ids)))

    list_filter = [LocationFilter]


BTN_TEMPLATE = """<div style="display: inline-grid; width: 125px; height: 40px; line-height: 40px; border-style: groove; background-color: #EBEBEB; cursor: pointer; text-align: center;" id="%s"
    onClick="fetch('/%s/%s').then(function(res){return res.json();}).then(function(data) {document.getElementById('status').textContent = data.status_title;})">%s</div>"""


@admin.register(Location)
class LocationAdmin(BaseAdmin):
    def get_queryset(self, request):
        qs = super(BaseAdmin, self).get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name='admin'):
            return qs.filter(deleted__isnull=True)
        else:
            self.ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
            return qs.filter(Q(deleted__isnull=True) & (Q(pk__in=self.ids) | Q(owner=request.user) | Q(owner__isnull=True)))

    def location_control(self, obj):
        return mark_safe(BTN_TEMPLATE % ("status", "open" if str(obj.status).startswith("CLOS") or obj.mode == "AUTOCLOSE" else "close", obj.id, "🔄 " + obj.location.get_status_display()))

    location_control.short_description = "Нажать кнопку"
    readonly_fields = ("location_control", )
    fields = ["code", "name", "address", "allowed", "device", "location_control", "status", "mode", "description"]
    list_display = ("code", "name", "address", "device", "status")
    search_fields = ("code", "name", "address")


@admin.register(Camera)
class CameraAdmin(LocationUserAdmin):
    def videopreview(self, obj):
        return mark_safe(f'<video controls width="450"><source src="{obj.sample.url}" type="video/mp4"/></video>' if not obj.url else """
        <div id="vid"><div id="click" style="background-color: #EBEBEB; cursor: pointer" onClick=
        "let str = document.getElementById('stream'); str.src = ''; str.src = 'https://visiongate.ru/video/%s/'; redraw();">     
        <img id="stream" src="https://visiongate.ru/video/%s" alt="Просмотр видео"/><strong id="strong"></strong></div>
        <script>let clk = document.getElementById('click'); let stg = document.getElementById('strong');
        function redraw(){stg.innerText=''; setTimeout(()=>{stg.innerText='Перезапустить';}, 31000);};redraw();</script></div>""" % (obj.id, obj.id))
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
            ) + (((BTN_TEMPLATE % ("open", "open", obj.id, "Открыть")
            ) + (BTN_TEMPLATE % ("close", "close", obj.id, "Закрыть"))) if obj.location.mode != "AUTOCLOSE" else (
                (BTN_TEMPLATE % ("open", "open", obj.id, "Нажать"))
            ))
        )

    location_control.short_description = "Управление"

    readonly_fields = ("videopreview", "controlpreview", "location_control")
    fields = ["code", "title", "name", "inout", "sample", "videopreview", "url", "location_control", "location", "description"]
    list_display = ("code", "title", "inout", "sample", "url", "location")
    search_fields = ("code", "title", "name", "sample", "url", "location__name")


@admin.register(Event)
class EventAdmin(ExportMixin, LocationUserAdmin):
    def imagepreview(self, obj):
        return mark_safe(f'<img src="%s" alt="Фото" width="560px"/>' % obj.image.url)
    imagepreview.short_description = "Фото"

    fields = ["location", "camera", "inout", "status", "created", "payload", "image", "imagepreview"]
    list_display = ("created", "location", "camera", "inout", "status", "payload")
    list_filter = (LocationFilter, "status")
    readonly_fields = ("imagepreview",)
    search_fields = ("payload",)

    def get_export_formats(self):
        return [CSV]
