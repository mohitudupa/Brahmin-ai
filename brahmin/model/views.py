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
import time

number = r'^[0-9]+$'
name = r'^[a-zA-Z\' -]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'
boolean = r'^(True)$|(False)$'
array = r'^\[(.*)*\]$'
date_format = r'^[0-3][0-9]-[0-1][0-9]-[0-9]{4}$'


# List of suupoted and tested ml classes
supervised_set = ["LinearRegression", "KNeighborsClassifier", "SVC"]
unsupervised_set = ["KMeans", "MeanShift"]


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
collection = db["models"]
log = db["log"]
users = db["users"]

# Function to log user activities
def log_instance(action, description, instance):
    x = log.find_one({"instance":instance})
    now = datetime.datetime.now()
    date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
    x["logs"].append([date, action, description])
    if action == "Commit":
        index = len(x["traceback"])
        x["traceback"].append([date, index, description])
        log.update_one({"instance":instance}, {"$set": {"logs": x["logs"], "traceback": x["traceback"]}})
    else:
        log.update_one({"instance":instance}, {"$set": {"logs": x["logs"]}})


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


def add_user_collection(user_id, name, version, instance_id, state, docs):
    user_collection = users.find_one({"user": user_id})

    if name not in user_collection[state]:
        user_collection[state][name] = {}
    if version not in user_collection[state][name]:
        user_collection[state][name][version] = {}

    user_collection[state][name][version] = [str(instance_id), docs]

    users.update_one({"user": user_id}, {"$set": {state: user_collection[state]}})


def del_user_collection(user_id, name, version, instance_id, state, docs):
    user_collection = users.find_one({"user": user_id})

    del user_collection[state][name][version]

    if user_collection[state][name] == {}:
        del user_collection[state][name]

    users.update_one({"user": user_id}, {"$set": {state: user_collection[state]}})


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
        error = []

        try:
            keys=['first_name','last_name','username','email','password','conf_password']
            regex = [name,name,text,email,password,password]
            types = [str, str, str, str, str, str]
            error = validate(data, keys, regex, types, error)

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
        users.insert_one({"user": user.id, "running": {}, "deleted": {}})

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
        final = {}
        errors = []

        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        x = users.find_one({"user":user.id})

        return render(request, "model/dashboard.html", {"errors": errors,"final": x["running"]})


@login_required(login_url="model:login")
def versionview(request,modelname):
    if request.method == "GET":
        user = request.user

        #fetching version data
        x=users.find_one({"user":user.id})

        # Preparing return html data
        final = x["running"][modelname]

        return render(request , "model/version.html", {"error":False,"final":final})

@login_required(login_url="model:login")
def upload(request):
    if request.method == "GET":
        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))
        return render(request, "model/upload.html", {"errors": errors})

@login_required(login_url="model:login")
def upload_form(request):
    if request.method == "POST":
        data = request.POST
        user = request.user
        user_collection = users.find_one({"user": user.id})
        error = []
        #validating html data
        try:
            keys = ["name", "version", "pickle", "private", "docs"]
            regex = [text, text, text, boolean, text]
            types = [str, str, str, str, str]
            error = validate(data, keys, regex, types, error)

            try:
                obj = pickle.loads(base64.b64decode(data['pickle']))    
            except:
                messages.info(request, "invalid pickle")
                return redirect("model:upload")

            if str(type(obj))[8:-2].split(".")[-1] in supervised_set:
                model_type = 0
            elif str(type(obj))[8:-2].split(".")[-1] in unsupervised_set:
                model_type = 1
            else:
                error["error"].append("Model class not yet supported")

            try:
                user_collection["running"][data["name"]][data["version"]]
                messages.info(request, "Model conflict occoured")
                return redirect("model:upload")
            except KeyError:
                pass

        except AssertionError:
            messages.info(request, error[-1])
            return redirect("model:upload")

        newmodel = {
                    "user":user.id,
                    "name":data["name"],
                    "version":data["version"],
                    "date_created":datetime.datetime.now(),
                    "last_modified":datetime.datetime.now(),
                    "private":eval(data["private"]),
                    "trash":False,
                    "type": model_type,
                    "results": [],
                    "buffer": "",
                    "traceback": [],
                    "pickle":data["pickle"],
                    "confidence":0.0,
                    "docs":data["docs"]
                    }
        #Saving new instance
        pid=collection.insert_one(newmodel).inserted_id

        # Creating instance log
        now = datetime.datetime.now()
        date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        newlog = {
                    "instance": pid,
                    "user": user.id,
                    "logs": [[date, "Upload", "Model uploaded by user: " + user.username]],
                    "traceback": [],
        }
        # Saving instance log
        log.insert_one(newlog).inserted_id

        # Updating the user collection
        add_user_collection(user.id, newmodel["name"], newmodel["version"], pid, "running", newmodel["docs"])

        return redirect("model:dashboard")



@login_required(login_url="model:login")
def trash(request, *args, **kwargs):
    if request.method == "GET":
        user = request.user
        final = {}

        errors = []
        storage = get_messages(request)
        for message in storage:
            errors.append(str(message))

        user_collection = users.find_one({"user":user.id})

        x = user_collection["deleted"]
        for model in x.keys():
            for version in x[model].keys():
                final[x[model][version][0]] = {"model": model, "version": version}

        return render(request, "model/trash.html", {"errors": False, "final": final})

@login_required(login_url="model:login")
def restore(request,instance_id):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance, "user": user.id, "trash": True})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:trash")

        except bson.errors.InvalidId:
            messages.info(request, "invalid instance ID")
            return redirect("model:trash")

            #error["error"].append("Invalid instance ID")

        # Updating the epoc extension
        new_version = x["version"].split("_rest_")[0] + "_rest_" + str(time.time())

        # Restoring instance from trash
        res = collection.update_one({"_id":instance,"user":user.id,"trash":True} ,
        {"$set":{"trash":False,"last_modified":datetime.datetime.now(), "version": new_version}})

        # Logging activity
        log_instance("Restore", "Model restored from trash", instance)

        # Updating the user collection
        del_user_collection(user.id, x["name"], x["version"], instance, "deleted", x["docs"])
        add_user_collection(user.id, x["name"], new_version, instance, "running", x["docs"])

        return redirect("model:dashboard")


@login_required(login_url="model:login")
def delete_ins(request, instance_id):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance,"user": user.id,"trash": False})

            if not x:
                return redirect("model:dashboard")

        except bson.errors.InvalidId:
            return redirect("model:dashboard")

        # Updating the epoc extension
        new_version = x["version"].split("_rest_")[0] + "_rest_" + str(time.time())

        # Moving instance into trash
        res = collection.update_one({"_id":ObjectId(instance_id),"user":user.id,"trash":False} ,
        {"$set":{"trash":True,"last_modified":datetime.datetime.now(), "version": new_version}})

        # Logging activity
        log_instance("Delete", "Model moved to trash", instance)

        # Updating the user collection
        del_user_collection(user.id, x["name"], x["version"], instance, "running", x["docs"])
        add_user_collection(user.id, x["name"], new_version, instance, "deleted", x["docs"])

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
            instance = ObjectId(instance_id)
            # Fetching instance data
            x = collection.find_one({"_id": instance, "trash": False})

            if not x:
                messages.info(request, "instance does not exist")
                return redirect("model:dashboard")
                #error["error"].append("Instance does not exist")

            else:
                if x["private"] and x["user"] != user.id:
                    messages.info(request, "instance is private")
                    return redirect("model:dashboard")
                #    error["error"].append("Instance is private")

        except bson.errors.InvalidId:
            messages.info(request, "invalid Instance ID")
            return redirect("model:dashboard")
            #error["error"].append("Invalid instance ID")

        status = False
        if x["buffer"]:
            status = "uncommited"

        predict_results = False
        predict_cols = False
        if x["results"]:
            results_type = x["results"]
            predict_results = x["results"]
            if not isinstance(predict_results[0], list):
                predict_results = np.array(predict_results).reshape(-1, 1).tolist()
            predict_cols = list(range(len(predict_results[0])))
            
            # Removing previous results from the database
            collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"results": []}})

        del x["results"]
        del x["user"]
        del x["_id"]
        del x["buffer"]
        del x["traceback"]
        del x["confidence"]
        # del x["description"]
        del x["trash"]

        x["id"] = str(instance)
        model_detail = x

        model_log = log.find_one({"instance":instance, "user":user.id})

        return render(request, "model/instance.html", {"errors": errors,
                                                    "model_detail":model_detail,
                                                    "log":model_log["logs"][-10:],
                                                    "traceback": model_log["traceback"][-10:],
                                                    "status": status,
                                                    "type": x["type"],
                                                    "results": predict_results,
                                                    "predict_cols": predict_cols})



@login_required(login_url="model:login")
def instance_train(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        error = []
        final = {}
        try:
            keys=["instance_id", "split"]
            regex = [text, number]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            if (int(data["split"]) < 10) or (int(data["split"]) > 100):
                error["error"].append("Split must be between 10 and 100")
                raise AssertionError()

            text_data = b""
            for chunk in files['x_train_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            x_train = np.matrix(pd.read_csv(StringIO(text_data)))

            text_data = b""
            for chunk in files['y_train_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            y_train = np.array(pd.read_csv(StringIO(text_data))).reshape(1, -1)[0]

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif x["type"] != 0:
                error["error"].append("model does not support testing")

        except KeyError:
            messages.info(request, "Invalid form submission")
            return redirect("model:dashboard")
        except AssertionError:
            messages.info(request, error["error"])
            return redirect("model:instanceview", data["instance_id"])
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview", data["instance_id"])
        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview", data["instance_id"])
        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")


        # Training the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:
            model = pickle.loads(base64.b64decode(x["pickle"]))

        training_cases = int(len(x_train) * int(data["split"]) / 100)

        try:
            model.fit(x_train[:training_cases], y_train[:training_cases])
        except Exception as e:
            messages.info(request, str(e))
            return redirect("model:instanceview", data["instance_id"])

        accuracy = 0
        if len(x_train) - training_cases >= 2:
            try:
                accuracy = model.score(x_train[training_cases:], y_train[training_cases:])
            except Exception as e:
                messages.info(request, str(e))
                return redirect("model:instanceview", data["instance_id"])
        base64_bytes = base64.b64encode(pickle.dumps(model))
        x["buffer"] = base64_bytes.decode('utf-8')

        collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"buffer": x["buffer"]}})
        # Logging activity
        log_instance("Train", "Trained with " + str(len(y_train)) + "cases", instance)

        messages.info(request, "Model trained successfully")
        messages.info(request, "Accuracy: " + str(accuracy))

        return redirect("model:instanceview", data["instance_id"])


@login_required(login_url="model:login")
def instance_cluster(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        error = []
        final = {}
        try:
            keys=["instance_id"]
            regex = [text, number]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in files['x_cluster_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            x_cluster = np.matrix(pd.read_csv(StringIO(text_data)))

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif x["type"] != 1:
                error["error"].append("model does not support clustering")

        except KeyError:
            messages.info(request, "Invalid form submission")
            return redirect("model:dashboard")
        except AssertionError:
            messages.info(request, error["error"])
            return redirect("model:instanceview", data["instance_id"])
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview", data["instance_id"])
        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview", data["instance_id"])
        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")


        # Training the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:
            model = pickle.loads(base64.b64decode(x["pickle"]))


        try:
            model.fit(x_cluster)
        except Exception as e:
            messages.info(request, str(e))
            return redirect("model:instanceview", data["instance_id"])

        base64_bytes = base64.b64encode(pickle.dumps(model))
        x["buffer"] = base64_bytes.decode('utf-8')

        collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"buffer": x["buffer"], "results": model.cluster_centers_.tolist()}})
        # Logging activity
        log_instance("Cluster", "Clustered with " + str(len(x_cluster)) + "cases", instance)

        messages.info(request, "Model trained successfully")

        return redirect("model:instanceview", data["instance_id"])


@login_required(login_url="model:login")
def instance_test(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        error = []
        final = {}
        try:

            keys=["instance_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in files['x_test_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            x_test = np.matrix(pd.read_csv(StringIO(text_data)))

            text_data = b""
            for chunk in files['y_test_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            y_test = np.array(pd.read_csv(StringIO(text_data))).reshape(1, -1)[0]

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif x["type"] != 0:
                error["error"].append("model does not support testing")

        except KeyError:
            messages.info(request, "Invalid form submission")
            return redirect("model:dashboard")
        except AssertionError:
            messages.info(request, error["error"])
            return redirect("model:instanceview", data["instance_id"])
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview", data["instance_id"])
        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview", data["instance_id"])
        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")

        # Testing the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:
            model = pickle.loads(base64.b64decode(x["pickle"]))

        try:
            confidence = model.score(x_test, y_test)
        except Exception as e:
            messages.info(request, str(e))
            return redirect("model:instanceview", data["instance_id"])

        res = collection.update_one({"_id": instance, "user": user.id, "trash": False},
        {"$set":{"confidence": confidence}})

        # Logging activity
        log_instance("Test", "Accuracy: " + str(confidence), instance)

        messages.info(request, "Accuracy: " + str(confidence))

        return redirect("model:instanceview",data["instance_id"])


@login_required(login_url="model:login")
def instance_predict(request):
    if request.method == "POST":
        user = request.user
        data = request.POST
        files = request.FILES
        error = []
        final = {}
        try:

            keys=["instance_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in files['x_predict_file'].chunks():
                text_data += chunk
            text_data = text_data.decode()
            x_predict = np.matrix(pd.read_csv(StringIO(text_data)))

            instance = ObjectId(data["instance_id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")

        except KeyError:
            messages.info(request, "Invalid form submission")
            return redirect("model:dashboard")
        except AssertionError:
            messages.info(request, error["error"])
            return redirect("model:instanceview", data["instance_id"])
        except UnicodeDecodeError:
            messages.info(request, "Invalid instance ID")
            return redirect("model:instanceview", data["instance_id"])
        except AttributeError:
            messages.info(request, "A text file must be uploaded")
            return redirect("model:instanceview", data["instance_id"])
        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")

        # Predicting results
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:
            model = pickle.loads(base64.b64decode(x["pickle"]))

        try:
            y = model.predict(x_predict)
        except Exception as e:
            messages.info(request, str(e))
            return redirect("model:instanceview", data["instance_id"])

        collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"results": y.tolist()}})

        # Logging activity
        log_instance("Predict", "Predictions done on " + str(len(x_predict)) + "cases", instance)


        return redirect("model:instanceview",data["instance_id"])


@login_required(login_url="model:login")
def commit(request, instance_id):
    if request.method == "POST":
        user = request.user
        data = request.POST
        error = []
        final = {}
        try:

            keys=["description"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif not x["buffer"]:
                return redirect("model:deshboard")

        except KeyError:
            messages.info(request, "Invalid form submission")
            return redirect("model:dashboard")
        except AssertionError:
            messages.info(request, error["error"])
            return redirect("model:instanceview", data["instance_id"])
        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")

        x["traceback"].append(x["pickle"])
        collection.update_one({"_id":instance}, {"$set": {"description": data["description"],
                                                        "pickle": x["buffer"],
                                                        "traceback": x["traceback"],
                                                        "buffer": ""}})

        # Logging activity
        log_instance("Commit", data["description"], instance)

        messages.info(request, "Commit successful")

        return redirect("model:instanceview",instance_id)


@login_required(login_url="model:login")
def discard(request, instance_id):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif not x["buffer"]:
                return redirect("model:deshboard")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")

        collection.update_one({"_id":instance}, {"$set": {"buffer": ""}})

        # Logging activity
        log_instance("Discard", "Discarded buffer model", instance)

        messages.info(request, "Discard successful")

        return redirect("model:instanceview", instance_id)


@login_required(login_url="model:login")
def rollback(request, instance_id, index):
    if request.method == "GET":
        user = request.user
        error = []
        final = {}
        try:

            instance = ObjectId(instance_id)
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                return redirect("model:dashboard")
            elif len(x["traceback"]) < int(index):
                error["error"].append("Invalid rollback index")

        except bson.errors.InvalidId:
            messages.info(request, "Invalid instance ID")
            return redirect("model:dashboard")

        collection.update_one({"_id":instance}, {"$set": {"buffer": "",
                                                        "pickle": x["traceback"][int(index)],
                                                        "traceback": x["traceback"][:int(index)]}})
        x = log.find_one({"instance":instance})
        log.update_one({"instance":instance}, {"$set": {"traceback": x["traceback"][:int(index)]}})

        # Logging activity
        log_instance("Discard", "Discarded buffer model", instance)

        messages.info(request, "Rollback successful")

        return redirect("model:instanceview", instance_id)
