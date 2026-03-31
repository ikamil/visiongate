"""
URL configuration for visiongate project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic.base import RedirectView
from main.views import *
from management.views import *

def home(request):
    return HttpResponseRedirect("/admin")


favicon_view = RedirectView.as_view(url="/static/main/favicon.ico", permanent=True)
admin.site.site_header = "VisionGate"
admin.site.index_title = ('Контроль доступа')
admin.site.site_title = ("Панель управления")

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', home),
    path("video/<int:id>/", video, name="video"),
    path("image/<int:id>/", image, name="image"),
    path("open/<int:id>/", gate_open, name="open", kwargs={"do_open": True}),
    path("close/<int:id>/", gate_open, name="close", kwargs={"do_open": False}),
    path("status/<int:id>/", gate_open, name="status", kwargs={"do_open": None}),
    re_path(r'^uploads/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path("stream", streaming_view),
    path("webdav/<int:cnt>/", webdav, name="webdav"),
    path("webdav/", webdav, name="webdav_default"),
]
