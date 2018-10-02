from django.urls import path, include


app_name = 'model'


urlpatterns = [
    path('api/', include('model.api.urls')),
]
