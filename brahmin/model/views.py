from django.shortcuts import render, redirect
from django.contrib.auth.models import User


# Create your views here.
def home(request, *args, **kwargs):
    if request.method == 'GET':

        return render(request, 'model/home.html', {"error": False})


def register(request, *args, **kwargs):
    if request.method == 'GET':

        return render(request, 'model/register.html', {"error": False})