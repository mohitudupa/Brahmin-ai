from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from rest_framework.authtoken.models import Token
from django.contrib import messages
from django.contrib.messages import get_messages
import re
import pymongo
import datetime
from bson.objectid import ObjectId
import bson
import pandas as pd
from io import StringIO
import numpy as np
from sklearn import *
import base64
import pickle

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
users = db["users"]

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


# Updating the user collection
def update_user_collection(id, name, version, instance_id, trash):
    user_collection = users.find_one({"user": id})

    if name not in user_collection:
        user_collection[name] = {}
    if version not in user_collection[name]:
        user_collection[name][version] = {"True": [], "False": []}

    toggle = "True"
    if str(trash) == "True":
        toggle = "False"

    intlist1 = set(user_collection[name][version][toggle][:])
    intlist1.discard(instance_id)
    user_collection[name][version][toggle] = list(intlist1)
    intlist = set(user_collection[name][version][str(trash)][:])
    intlist.add(instance_id)
    user_collection[name][version][str(trash)] = list(intlist)
    print(user_collection)

    users.update_one({"user": id}, {"$set": {name: user_collection[name]}})


# Home page view
def home(request, *args, **kwargs):
    if request.method == "GET":
        logged_in = False
        if request.user.is_authenticated:
            logged_in = True
        print(request.user.id)
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

        # Generate an entry for the user in the users collection
        users.insert_one({"user": user.id})

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
    """if request.method == "GET":
        user = request.user
        error = []
        final = {}
        x = collection.find({"user":user.id,"trash":False})

        # Preparing return html data
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
        """
    if request.method == "GET":
        user = request.user
        final = {}

        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        x = users.find_one({"user":user.id})

        # Preparing return html data
        del x["_id"]
        del x["user"]
        print(x)
        final = x
        models = list(x.keys())
        print(models)
        for model in models:
            versions = list(x[model].keys())
            print(versions)
            for version in versions:
                inst_in_trash = x[model][version]["True"]
                inst_not_in_trash = x[model][version]["False"]
                print(inst_in_trash,inst_not_in_trash)
                del final[model][version]["True"]
                if len(inst_not_in_trash) == 0:
                    del final[model][version]
            if len(final[model]) == 0:
                del final[model]
        print(final)
        final1={}
        for model in final:
            if model not in final1:
                final1[model]= [set(),0,0]
            for version in final[model]:
                final1[model][0].add(version)
                final1[model][1] += 1
                final1[model][2] += len(final[model][version]["False"])
        print(final1)

        return render(request, "model/dashboard.html", {"errors": errors,"final1":final1})

@login_required(login_url="model:login")
def versionview(request,modelname):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}

        #fetching version data
        x=users.find_one({"user":user.id,modelname:{'$exists': True}})

        # Preparing return html data
        del x["_id"]
        del x["user"]
        final = {}
        for version in x[modelname]:
            if len(x[modelname][version]["False"]) == 0:
                continue
            final[version] = x[modelname][version]["False"]
        print(modelname,final)
        return render(request , "model/version.html", {"error":False,"final":final})


@login_required(login_url="model:login")
def trash(request, *args, **kwargs):
    if request.method == "GET":
        user = request.user
        final = {}

        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        x = users.find_one({"user":user.id})
        # Preparing return html data
        del x["_id"]
        del x["user"]
        print(x)
        final = x
        models = list(x.keys())
        for model in models:
            versions = list(x[model].keys())
            for version in versions:
                inst_in_trash = x[model][version]["True"]
                inst_not_in_trash = x[model][version]["False"]
                print(inst_in_trash,inst_not_in_trash)
                del final[model][version]["False"]
                if len(inst_in_trash) == 0:
                    del final[model][version]
            if len(final[model]) == 0:
                del final[model]
        print(final)
        final1={}
        for model in final:
            for version in final[model]:
                for instance in final[model][version]["True"]:
                    if instance not in final1:
                        final1[instance] = {"Model_Name" : model , "Version" : version}
        print(final1)

        return render(request, "model/trash.html", {"errors": errors,"final1":final1})

@login_required(login_url="model:login")
def restore(request,instance):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance_id = ObjectId(instance)
            x = collection.find_one({"_id": instance_id, "user": user.id, "trash": True})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")

        except bson.errors.InvalidId:
            messages.info(request, "invalid instance ID")
            return redirect("model:trash")

            #error["error"].append("Invalid instance ID")

        # Restoring instance from trash
        res = collection.update_one({"_id":instance_id,"user":user.id,"trash":True} ,
        {"$set":{"trash":False,"last_modified":datetime.datetime.now()}})

        # Logging activity
        log_instance("Restore", instance_id)

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], instance_id, False)

        return redirect("model:dashboard")


@login_required(login_url="model:login")
def delete_ins(request,instance_id):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance,"user": user.id,"trash": False})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")
                #error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")
            #error["error"].append("Invalid instance ID")


        # Moving instance into trash
        res = collection.update_one({"_id":ObjectId(instance_id),"user":user.id,"trash":False} ,
        {"$set":{"trash":True,"last_modified":datetime.datetime.now()}})

        # Logging activity
        log_instance("Delete", instance)

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], instance, True)

        return redirect("model:trash")



@login_required(login_url="model:login")
def instanceview(request,instance_id):
    if request.method == "GET":
        user = request.user
        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        final = {}
        #return render(request, "model/instance.html", {"errors": False,"final":final})

        try:
            print(instance_id)
            instance = ObjectId(instance_id)
            # Fetching instance data
            x = collection.find_one({"_id": instance, "trash": False})
            x1 = log.find_one({"instance":instance, "user":user.id})
            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:dashboard")
                #error["error"].append("Instance does not exist")

            else:
                if x["private"] and x["user"] != user.id:
                    messages.info(request, "instance is private")
                    return redirect("model:dashboard")
                #    error["error"].append("Instance is private")
            if not x1:
                messages.info(request, "log does not exist")
                return redirect("model:dashboard")

        except bson.errors.InvalidId:
            messages.info(request, "invalid Instance ID")
            return redirect("model:dashboard")
            #error["error"].append("Invalid instance ID")


        del x["user"]
        x["id"] = str(x["_id"])
        del x["_id"]
        model_detail = x

        del x1["_id"]
        del x1["instance"]
        del x1["user"]
        model_full_log = x1
        model_partial_log = {}
        dates = sorted(list(model_full_log.keys()))
        print(dates)
        for i in range(0,(min(len(dates),10))):
            model_partial_log[dates[i]] = model_full_log[dates[i]]

        #print(model_detail,model_full_log,model_partial_log)
        return render(request, "model/instance.html", {"errors": errors,"model_detail":model_detail,"model_partial_log":model_partial_log})




@login_required(login_url="model:login")
def instance_train(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        print(data)
        print(files["x_train_file"])
        error = []
        final = {}
        try:
            text_data = b""
            for chunk in files['x_train_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            print(text_data)
            x_train = np.matrix(pd.read_csv(StringIO(text_data),names=["col"]*4))
            print(x_train)

            text_data = b""
            for chunk in files['y_train_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            y_train = np.array(pd.read_csv(StringIO(text_data),names=["col"]*2))[0]
            print(y_train)

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])

        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview",data["instance_id"])

            #            error["error"].append("A text file must be uploaded")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])
            #error["error"].append("Invalid instance ID")

    cls = pickle.loads(base64.b64decode(x["pickle"]))
    cls.fit(x_train, y_train)
    log_instance("Train", instance)
    #print(data["instance_id"])

    messages.info(request, "model "+str(data["instance_id"])+" trained")
    return redirect("model:instanceview",data["instance_id"])


@login_required(login_url="model:login")
def instance_test(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        #print(data)
        #print(files["x_test_file"])
        error = []
        final = {}
        try:
            text_data = b""
            for chunk in files['x_test_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            print(text_data)
            x_test = np.matrix(pd.read_csv(StringIO(text_data),names=["col"]*4))
            print(x_test)

            text_data = b""
            for chunk in files['y_test_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            y_test = np.array(pd.read_csv(StringIO(text_data),names=["col"]*2))[0]
            print(y_test)

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])

        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview",data["instance_id"])

            #            error["error"].append("A text file must be uploaded")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])
            #error["error"].append("Invalid instance ID")

    cls = pickle.loads(base64.b64decode(x["pickle"]))
    confidence = cls.score(x_test, y_test)

    res = collection.update_one({"_id": ObjectId(data["instance_id"]), "user": user.id, "trash": False},
    {"$set":{"confidence": confidence}})

    # Logging activity
    log_instance("Test", instance)

    messages.info(request, "model "+str(data["instance_id"])+" confidence = "+str(confidence))
    return redirect("model:instanceview",data["instance_id"])


@login_required(login_url="model:login")
def instance_predict(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        #print(data)
        #print(files["x_test_file"])
        error = []
        final = {}
        try:
            text_data = b""
            for chunk in files['x_predict_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            print(text_data)
            x_predict = np.matrix(pd.read_csv(StringIO(text_data),names=["col"]*4))
            print(x_predict)


            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])

        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview",data["instance_id"])

            #            error["error"].append("A text file must be uploaded")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview",data["instance_id"])
            #error["error"].append("Invalid instance ID")

    cls = pickle.loads(base64.b64decode(x["pickle"]))
    y = cls.predict(x_predict)


    log_instance("Predict", instance)

    messages.info(request, "model "+str(data["instance_id"])+" result = "+str(y))
    return redirect("model:instanceview",data["instance_id"])
