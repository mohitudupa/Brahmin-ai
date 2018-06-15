from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from rest_framework.authtoken.models import Token
from django.contrib import messages
from django.contrib.messages import get_messages
import re
import pymongo


number = r'^[0-9]+$'
name = r'^[a-zA-Z\' -]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'
boolean = r'^(True)$|(False)$'
array = r'^\[(.*)*\]$'
date_format = r'^[0-3][0-9]-[0-1][0-9]-[0-9]{4}$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
collection = db["models"]
log = db["log"]

# Function to log user activities
def log_instance(action, instance):
    x = log.find_one({"instance":instance})
    now = datetime.datetime.now()
    key = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
    if key not in x:
        x[key] = []
    x[key].append(action)
    log.update_one({"instance":instance}, {"$set": {key: x[key]}})


# Function to validate posted data
def validate(data, keys, regex, types, error):
    for i in range(len(keys)):
        if isinstance(data[keys[i]], types[i]):
            if not bool(re.match(regex[i], str(data[keys[i]]))):
                error.append("Invalid value for " + keys[i])
                raise AssertionError()
        else:
            error.append("Invalid type for " + keys[i])
            raise AssertionError()
    return error


# Home page view
def home(request, *args, **kwargs):
    if request.method == "GET":
        logged_in = False
        if request.user.is_authenticated:
            logged_in = True
        return render(request, "model/home.html", {"errors": [], "logged_in": logged_in})


# Login page view
def user_login(request, *args, **kwargs):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect("model:dashboard")

        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        return render(request, "model/login.html", {"errors": errors})



# Login form submittion view
def login_form(request, *args, **kwargs):
    if request.method == "GET":
        return redirect("model:home")

    if request.method == "POST":

        data = request.POST
        error = []

        try:
            keys = ["email", "password"]
            regex = [email, password]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            username = User.objects.get(email=data["email"])

        except User.DoesNotExist:
            messages.info(request, "Incorrect email or password")
            return redirect("model:login")
        except Exception:
            messages.info(request, "Invalid form submition")
            return redirect("model:login")


        user = authenticate(request, username=username, password=data["password"])

        if user is not None:
            login(request, user)
            return redirect("model:dashboard")
        else:
            messages.info(request, "Incorrect email or password")
            return redirect("model:login")


# User logout view
def user_logout(request, *args, **kwargs):
    if request.method == "GET":
        if request.user.is_authenticated:
            logout(request)
        return redirect("model:home")


# Registration page view
def register(request, *args, **kwargs):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect("model:dashboard")
        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))
        return render(request, "model/register.html", {"errors": errors})


# Registration form submittion view
def register_form(request, *args, **kwargs):
    if request.method == "POST":
        data = request.POST
        print(data)
        error = []

        try:
            post_data_keys=['first_name','last_name','username','email','password','conf_password']
            #keys = ["first_name", "last_name", "email", "password", "username"]
            regex = [name,name,text,email,password,password]
            types = [str, str, str, str, str, str]
            error = validate(data, post_data_keys, regex, types, error)

            # Checking if username and email has already been taken

            try:
                User.objects.get(email=data["email"])
                messages.info(request, "email already exists")
                return redirect("model:register")
            except User.DoesNotExist:
                pass

            try:
                User.objects.get(username=data["username"])
                messages.info(request, "username already exists")
                return redirect("model:register")
            except User.DoesNotExist:
                pass

        except KeyError:
            messages.info(request,"The following values are required: first_name, last_name, username,password and email")
            return redirect("model:register")
        except AssertionError:
                for i in error:
                    messages.info(request,i)
                return redirect("model:register")
        # No errors are found, registering user
        user = User.objects.create_user(data['username'], data['email'], data['password'])
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.save()

        # Generate token for user
        token = Token.objects.create(user=user)
        token.save()
        #authenticate user
        user = authenticate(request, username=data["username"], password=data["password"])

        if user is not None:
            login(request, user)
            return redirect("model:dashboard")
        else:
            messages.info(request, "Should not happen!")
            return redirect("model:register")


# User dashboard view
@login_required(login_url="model:login")
def dashboard(request, *args, **kwargs):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        x = collection.find({"user":user.id,"trash":False})

        # Preparing return json data
        for i in x:
            if i["name"] not in final:
                #list = [set(version_names), no_of_versions, no_of_instances]
                final[i["name"]] = [set(),0,0]
            if i["version"] not in final[i["name"]][0]:
                final[i["name"]][0].add(i["version"])
                final[i["name"]][1] += 1
            final[i["name"]][2]+=1
        print(final)

        return render(request, "model/dashboard.html", {"error": False,"final":final})
