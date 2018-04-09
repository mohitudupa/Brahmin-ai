from django.urls import path, include
from . import views


urlpatterns = [
    path('api/', include('model.api.urls')),
]
