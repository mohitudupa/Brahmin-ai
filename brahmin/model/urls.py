from django.urls import path, include
from . import views


app_name = 'model'


urlpatterns = [
    path('api/', include('model.api.urls')),
    path('home/', views.home, name="home"),
    path('register/', views.register, name="register"),
]
