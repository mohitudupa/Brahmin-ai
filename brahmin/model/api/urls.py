from django.urls import path, include
from . import views


urlpatterns = [
    path('index/', views.Index.as_view(), name="index"),
    path('register/', views.Register.as_view(), name="register"),
    path('gettoken/', views.GetToken.as_view(), name="get_token"),
    path('changepassword/', views.ChangePassword.as_view(), name="change_password"),
    path('changetoken/', views.ChangeToken.as_view(), name="change_token"),
    path('clone/', views.Clone.as_view(), name="clone"),
    path('upload/', views.Upload.as_view(), name="upload"),
    path('update/', views.Update.as_view(), name="update"),
    path('delete/', views.Delete.as_view(), name="delete"),
    path('restore/', views.Restore.as_view(), name="restore"),
    path('getdetails/', views.GetDetails.as_view(), name="get_details"),
    path('getnames/', views.GetNames.as_view(), name="get_names"),
    path('getversions/', views.GetVersions.as_view(), name="get_versions"),
    path('getinstances/', views.GetInstances.as_view(), name="get_instances"),
    path('getmodel/', views.GetModel.as_view(), name="get_model"),
    path('getlog/', views.GetLog.as_view(), name="get_log"),
    path('getuserlog/', views.GetUserLog.as_view(), name="get_user_log"),
    path('getdatelog/', views.GetDateLog.as_view(), name="get_date_log"),
    path('gettraceback/', views.GetTraceback.as_view(), name="gettraceback"),
    path('train/', views.Train.as_view(), name="train"),
    path('test/', views.Test.as_view(), name="test"),
    path('predict/', views.Predict.as_view(), name="predict"),
    path('commit/', views.Commit.as_view(), name="commit"),
    path('discard/', views.Discard.as_view(), name="discard"),
    path('rollback/', views.RollBack.as_view(), name="rollback"),
    path('getstatus/', views.GetStatus.as_view(), name="getstatus"),
]
