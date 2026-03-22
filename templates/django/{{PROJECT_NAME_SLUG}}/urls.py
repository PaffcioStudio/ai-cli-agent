from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

def index(request):
    return JsonResponse({"project": "{{PROJECT_NAME}}", "status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", index),
]
