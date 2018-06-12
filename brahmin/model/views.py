from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
import requests
import json

host = "127.0.0.1:8000"
# Create your views here.
def home(request, *args, **kwargs):
    if request.method == 'GET':

        return render(request, 'model/home.html', {"error": False})


def register(request, *args, **kwargs):
    #post_data_keys=['first_name','last_name','username','email','password','conf_password']
    #api_keys = ["first_name", "last_name", "email", "password", "username"]

    url = "http://" + host + "/model/api/register/"
    headers = {"content-type": "application/json"}
    if request.method == "POST":
        x=dict(request.POST)
        #to satisfy data of requests
        data = {}
        data["first_name"] = x["first_name"][0]
        data["last_name"] = x["last_name"][0]
        data["email"] = x["email"][0]
        data["password"] = x["password"][0]
        data["username"] = x["username"][0]

        r = requests.post(url = url , data = json.dumps(data) , headers = headers)
        print("registration response : " + r.text)
        user = authenticate(request,username=data['username'], password=data['password'])
        if user is not None:
            if user.is_active:
                print("Exists & active")
                login(request, user)
                return redirect('model:home')
            else:
                return render(request, 'model/home.html', {'error_message': 'Your account has been disabled'})
        else:
            return render(request, 'model/register.html', {'error': True})
    else:
        return render(request, 'model/register.html', {'error': False})
