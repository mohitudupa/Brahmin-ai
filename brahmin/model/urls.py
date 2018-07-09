from django.urls import path, include
from . import views


app_name = 'model'


urlpatterns = [
    path('api/', include('model.api.urls')),
    path('home/', views.home, name="home"),
    path('login/', views.user_login, name="login"),
    path('logout/', views.user_logout, name="logout"),
    path('login/form', views.login_form, name="login_form"),
    path('register/', views.register, name="register"),
    path('register/form', views.register_form, name="register_form"),
    path('dashboard/', views.dashboard, name="dashboard"),
    path('versionview/<str:modelname>/',views.versionview,name="versionview"),
    path('upload/',views.upload,name="upload"),
    path('upload/form/',views.upload_form,name="upload_form"),
    path('trash/',views.trash,name="trash"),
    path('restore/<str:instance_id>/',views.restore,name="restore"),
    path('deleteins/<str:instance_id>/',views.delete_ins,name="delete_ins"),
    path('instanceview/<str:instance_id>/',views.instanceview,name="instanceview"),
    path('instance_train/',views.instance_train,name="instance_train"),
    path('instance_cluster/',views.instance_cluster,name="instance_cluster"),
    path('instance_test/',views.instance_test,name="instance_test"),
    path('instance_predict/',views.instance_predict,name="instance_predict"),
    path('commit/<str:instance_id>/',views.commit,name="commit"),
    path('discard/<str:instance_id>/',views.discard,name="discard"),
    path('rollback/<str:instance_id>/<str:index>/',views.rollback,name="rollback"),

]
