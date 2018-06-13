from django.urls import path, include
from . import views


app_name = 'model'


urlpatterns = [
    path('api/', include('model.api.urls')),
    path('home/', views.home, name="home"),
    path('login/', views.user_login, name="login"),
    path('login/form', views.login_form, name="login_form"),
    path('logout/', views.user_logout, name="logout"),
    path('register/', views.register, name="register"),
    path('register/form', views.register_form, name="register_form"),
    path('dashboard/', views.dashboard, name="dashboard"),
]
