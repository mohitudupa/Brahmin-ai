from django.urls import path, include
from . import model_views
from . import template_views
from . import detail_views
from . import exec_views
from . import user_views

urlpatterns = [
    path('index/', user_views.Index.as_view(), name="index"),
    path('register/', user_views.Register.as_view(), name="register"),
    path('gettoken/', user_views.GetToken.as_view(), name="get_token"),
    path('changepassword/', user_views.ChangePassword.as_view(), name="changepassword"),
    path('changetoken/', user_views.ChangeToken.as_view(), name="changetoken"),

    path('clonemodel/', model_views.CloneModel.as_view(), name="clonemodel"),
    path('uploadmodel/', model_views.UploadModel.as_view(), name="uploadmodel"),
    path('editmodel/', model_views.EditModel.as_view(), name="editmodel"),
    path('deletemodel/', model_views.DeleteModel.as_view(), name="deletemodel"),
    path('restoremodel/', model_views.RestoreModel.as_view(), name="restoremodel"),
    path('commit/', model_views.Commit.as_view(), name="commit"),
    path('discard/', model_views.Discard.as_view(), name="discard"),
    path('rollback/', model_views.RollBack.as_view(), name="rollback"),

    path('getdetails/', detail_views.GetDetails.as_view(), name="getdetails"),
    path('getmodelid/', detail_views.GetModelId.as_view(), name="getmodelid"),
    path('getmodel/', detail_views.GetModel.as_view(), name="getmodel"),
    path('getlog/', detail_views.GetLog.as_view(), name="getlog"),
    path('getuserlog/', detail_views.GetUserLog.as_view(), name="getuserlog"),
    path('getdatelog/', detail_views.GetDateLog.as_view(), name="getdatelog"),
    path('gettraceback/', detail_views.GetTraceback.as_view(), name="gettraceback"),
    path('getstatus/', detail_views.GetStatus.as_view(), name="getstatus"),
    path('gettemplatedetails/', detail_views.GetTemplateDetails.as_view(), name="gettemplatedetails"),
    path('gettemplate/', detail_views.GetTemplate.as_view(), name="gettemplate"),
    path('getresult/', detail_views.GetResult.as_view(), name="getresult"),
    path('getattribute/', detail_views.GetAttribute.as_view(), name="getattribute"),

    path('execcommand/', exec_views.ExecCommand.as_view(), name="execcommand"),
    path('abort/', exec_views.Abort.as_view(), name="abort"),

    path('clonetemplate/', template_views.CloneTemplate.as_view(), name="clonetemplate"),
    path('uploadtemplate/', template_views.UploadTemplate.as_view(), name="uploadtemplate"),
    path('edittemplate/', template_views.EditTemplate.as_view(), name="edittemplate"),
    path('deletetemplate/', template_views.DeleteTemplate.as_view(), name="deletetemplate"),
]
