from django.urls import path, include
from . import views


urlpatterns = [
    path('index/', views.Index.as_view(), name="index"),
    path('register/', views.Register.as_view(), name="register"),
    path('gettoken/', views.GetToken.as_view(), name="get_token"),
    path('clone/', views.Clone.as_view(), name="clone"),
    path('upload/', views.Upload.as_view(), name="upload"),
    path('update/', views.Update.as_view(), name="update"),
    path('delete/', views.Delete.as_view(), name="delete"),
    path('restore/', views.Restore.as_view(), name="restore"),
    path('getdetails/', views.GetDetails.as_view(), name="getdetails"),
    path('getnames/', views.GetNames.as_view(), name="getnames"),
    path('getversions/', views.GetVersions.as_view(), name="getversions"),
    path('getinstances/', views.GetInstances.as_view(), name="getinstances"),
    path('getmodel/', views.GetModel.as_view(), name="getmodel"),
    path('train/', views.Train.as_view(), name="train"),
    path('test/', views.Test.as_view(), name="test"),
    path('predict/', views.Predict.as_view(), name="predict"),
]
