from model.models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
import re
import datetime
import time
from sklearn import *
import numpy as np
import pandas as pd
from io import StringIO
import base64
import pickle
import pymongo
from bson.objectid import ObjectId
import bson


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


def validate(data, keys, regex, types, error):
    for i in range(len(keys)):
        if isinstance(data[keys[i]], types[i]):
            if not bool(re.match(regex[i], str(data[keys[i]]))):
                error["error"].append("Invalid value for " + keys[i])
                raise AssertionError()
        else:
            error["error"].append("Invalid type for " + keys[i])
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


class Index(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        return Response(request.data)


class Register(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        # Validating registration data
        data = request.data
        error = {"error": []}

        try:
            keys = ["first_name", "last_name", "email", "password", "username"]
            regex = [name, name, email, password, text]
            types = [str, str, str, str, str]
            error = validate(data, keys, regex, types, error)

            # Checking if username and email has already been taken

            try:
                User.objects.get(email=data['email'])
                error["error"].append("email already exists")
            except User.DoesNotExist:
                pass

            try:
                User.objects.get(username=data['username'])
                error["error"].append("username already exists")
            except User.DoesNotExist:
                pass
        except KeyError:
            error["error"].append("The following values are required: first_name, last_name, username, "
                                  "password and email")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

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

        return Response({
            "status": "User registration successful",
            "username": user.username,
            "email": user.email,
            "token": token.key,
        })


class GetToken(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        data = request.data
        error = {"error": []}

        # Validating login data
        try:

            keys = ["password", "username"]
            regex = [password, name]
            types = [str, str]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: username and password")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)
        # Auth
        user = authenticate(request, username=data['username'], password=data['password'])
        if user is not None:
            return Response({"token": Token.objects.get(user=user).key})
        return Response({"error": ["Invalid username or password"]})


class ChangePassword(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}

        # Validating post data
        try:

            keys = ["old_password", "new_password"]
            regex = [password, password]
            types = [str, str]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: old_password and new_password")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)
        # Auth
        user = authenticate(request, username=user.username, password=data["old_password"])
        if user is not None:
            # Changing the password
            user.set_password(data["new_password"])
            user.save()
            return Response({"Success": "Password changed"})
        return Response({"error": ["Invalid old password"]})


class ChangeToken(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        data = request.data
        error = {"error": []}

        # Validating login data
        try:

            keys = ["password", "username"]
            regex = [password, name]
            types = [str, str]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: username and password")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)
        # Auth
        user = authenticate(request, username=data['username'], password=data['password'])
        if user is not None:
            # Deleting old token
            token = Token.objects.get(user=user)
            token.delete()
            # Creating new token for user
            token = Token.objects.create(user=user)
            token.save()
            return Response({"token": token.key})
        return Response({"error": ["Invalid username or password"]})


class Clone(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")
            else:
                if x["private"] and x["user"] != user.id:
                    error["error"].append("Instance is private")

                # Checking for conflicts
                try:
                    user_collection["running"][x["name"]]["clone - " + x["version"]]
                    error["error"].append("Model conflict occoured")
                except KeyError:
                    pass
        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Cloning instance
        newmodel = {
                    "user": user.id,
                    "name": x["name"],
                    "version": "clone - " + x["version"],
                    "date_created": datetime.datetime.now(),
                    "last_modified": datetime.datetime.now(),
                    "private": x["private"],
                    "trash": x["trash"],
                    "type": x["type"],
                    "buffer": "",
                    "traceback": x["traceback"],
                    "pickle": x["pickle"],
                    "confidence": x["confidence"],
                    "docs": x["docs"]
                    }
        # Saving new instance
        pid = collection.insert_one(newmodel).inserted_id

        # Creating instance log
        now = datetime.datetime.now()
        date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        original_user = User.objects.get(id=x["user"]).username
        newlog = {
                    "instance": pid,
                    "user": user.id,
                    "logs": [[date, "Clone", "Model cloned from user: " + original_user]],
                    "traceback": [],
        }
        # Saving instance log
        log.insert_one(newlog).inserted_id

        # Updating the user collection
        add_user_collection(user.id, x["name"], "clone - " + x["version"], pid, "running", x["docs"])

        return Response({"Mongo_instance_id":str(pid)})


class Upload(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["name", "version", "pickle", "private", "docs"]
            regex = [text, text, text, boolean, text]
            types = [str, str, str, bool, str]
            error = validate(data, keys, regex, types, error)

            try:
                obj = pickle.loads(base64.b64decode(request.data['pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"].append("Not of type sklearn")
                """
            except:
                error["error"].append("Invalid pickle")

            # Checking for conflicts
            try:
                user_collection["running"][data["name"]][data["version"]]
                error["error"].append("Model conflict occoured")
            except KeyError:
                pass

            if str(type(obj))[8:-2].split(".")[-1] in supervised_set:
                model_type = 0
            elif str(type(obj))[8:-2].split(".")[-1] in unsupervised_set:
                model_type = 1
            else:
                error["error"].append("Model class not yet supported")

        except KeyError:
            error["error"].append("The following values are required: name, version, pickle, private and docs")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Creating new instance
        newmodel = {
                    "user":user.id,
                    "name":data["name"],
                    "version":data["version"],
                    "date_created":datetime.datetime.now(),
                    "last_modified":datetime.datetime.now(),
                    "private":data["private"],
                    "trash": False,
                    "type": model_type,
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

        return Response({"Mongo_instance_id":str(pid)})


class Update(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id", "new_name", "new_version", "new_private", "new_docs", "description"]
            regex = [text, text, text, boolean, text, text]
            types = [str, str, str, bool, str, str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance,"user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")

           # Checking for conflicts
            try:
                user_collection["running"][data["new_name"]][data["new_version"]]
                error["error"].append("Model conflict occoured")
            except KeyError:
                pass
        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id, new_name, new_version, "
                                  "new_pickle, new_private, new_docs and description")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Updating instance entries
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id} ,
        {"$set":{
            "name":data["new_name"],
            "version":data["new_version"],
            "private":data["new_private"],
            "last_modified":datetime.datetime.now(),
            "docs":data["new_docs"]}
        })

        # Logging activity
        log_instance("Edit", data["description"], instance)

        # Updating the user collection
        # Deleting old data
        del_user_collection(user.id, x["name"], x["version"], instance, "running", x["docs"])
        add_user_collection(user.id, data["new_name"], data["new_version"], instance, "running", data["new_docs"])

        return Response({"Success": "Model updated successfully"})


class Delete(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance,"user": user.id,"trash": False})

            if not x:
                error["error"].append("Instance does not exist")
        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Updating the epoc extension
        new_version = x["version"].split("_rest_")[0] + "_rest_" + str(time.time())

        # Moving instance into trash
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False} ,
        {"$set":{"trash":True,"last_modified":datetime.datetime.now(), "version": new_version}})

        # Logging activity
        log_instance("Delete", "Model moved to trash", instance)

        # Updating the user collection
        del_user_collection(user.id, x["name"], x["version"], instance, "running", x["docs"])
        add_user_collection(user.id, x["name"], new_version, instance, "deleted", x["docs"])

        return Response({"Success": "Instance: " + data["id"] + " moved to trash"})


class Restore(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": True})

            if not x:
                error["error"].append("Instance does not exist")
        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Updating the epoc extension
        new_version = x["version"].split("_rest_")[0] + "_rest_" + str(time.time())

        # Restoring instance from trash
        res = collection.update_one({"_id": ObjectId(data["id"]), "user": user.id, "trash": True} ,
        {"$set":{"trash": False, "last_modified": datetime.datetime.now(), "version": new_version}})

        # Logging activity
        log_instance("Restore", "Model restored from trash", instance)

        # Updating the user collection
        del_user_collection(user.id, x["name"], x["version"], instance, "deleted", x["docs"])
        add_user_collection(user.id, x["name"], new_version, instance, "running", x["docs"])

        return Response({"Success": "Instance: " + data["id"] + " restored from trash"})


class GetDetails(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}

        # Validating received data
        try:
            keys = ["trash"]
            regex = [boolean]
            types = [bool]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: trash")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Sending response
        if data["trash"]:
            return Response(user_collection["deleted"])
        return Response(user_collection["running"])


class GetNames(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}

        # Validating received data
        try:
            keys = ["trash"]
            regex = [boolean]
            types = [bool]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: trash")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Sending response
        if data["trash"]:
            return Response({"names": user_collection["deleted"].keys()})
        return Response({"names": user_collection["running"].keys()})


class GetVersions(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}

        # Validating received data
        try:
            keys = ["name", "trash"]
            regex = [text, boolean]
            types = [str, bool]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: name, trash")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Sending response
        try:
            if data["trash"]:
                return Response({"versions": user_collection["deleted"][data["name"]].keys()})
            return Response({"versions": user_collection["running"][data["name"]].keys()})
        except KeyError:
            return Response({"error": ["Model name does not exist"]})


class GetInstances(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        final = {"id": []}

        # Validating received data
        try:
            keys = ["name", "version", "trash"]
            regex = [text, text, boolean]
            types = [str, str, bool]
            error = validate(data, keys, regex, types, error)
        except KeyError:
            error["error"].append("The following values are required: name, version, trash")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Sending response
        try:
            if data["trash"]:
                return Response({"id": user_collection["deleted"][data["name"]][data["version"]][0]})
            return Response({"id": user_collection["running"][data["name"]][data["version"]][0]})
        except KeyError:
            return Response({"error": ["Model does not exist"]})


class GetModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            # Fetching instance data
            x = collection.find_one({"_id": instance, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")
            else:
                if x["private"] and x["user"] != user.id:
                    error["error"].append("Instance is private")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        del x["user"]
        x["id"] = str(x["_id"])
        del x["_id"]
        del x["traceback"]
        return Response(x)


class GetLog(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            # Fetching logs
            x = log.find_one({"instance": instance, "user": user.id})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        del x["_id"]
        del x["user"]
        del x["traceback"]
        x["instance"] = str(x["instance"])

        return Response(x)


class GetUserLog(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data

        # Fetching logs
        x = log.find({"user": user.id})

        rdata = {"user": user.username}
        
        for obj in x:
            rdata[str(obj["instance"])] = obj["logs"]

        return Response(rdata)


class GetDateLog(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}

        # Validating received data
        try:
            keys = ["date"]
            regex = [date_format]
            types = [str]
            error = validate(data, keys, regex, types, error)

            day, month, year = data["date"].split("-")
            date = datetime.datetime(int(year), int(month), int(day))

        except KeyError:
            error["error"].append("The following values are required: date(dd-mm-yyyy)")

        except ValueError:
            error["error"].append("Invalid date")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Fetching logs
        x = log.find({"user": user.id})

        rdata = {"date": date}
        for obj in x:
            activities = []
            for activity in obj["logs"]:
                if activity[0] == data["date"]:
                    activities.append(activity)
            rdata[str(obj["instance"])] = activities

        return Response(rdata)


class GetTraceback(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            # Fetching logs
            x = log.find_one({"instance": instance, "user": user.id})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        return Response({"traceback": x["traceback"]})


class Train(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_train = []
        y_train = []
        x = ''

        # Validating received data
        try:
            print(type(data["split"]))
            keys = ["id", "split"]
            regex = [text, number]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            if (int(data["split"]) < 10) or (int(data["split"]) > 100):
                error["error"].append("Split must be between 10 and 100")
                raise AssertionError()

            text_data = b""
            for chunk in request.data['x_train'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            x_train = np.array(pd.read_csv(StringIO(text_data)))

            text_data = b""
            for chunk in request.data['y_train'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            y_train = np.array(pd.read_csv(StringIO(text_data))).reshape(1, -1)[0]

            # if len(x_train) != len(y_train):
            #     error["error"].append("Error in training data")

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")
            elif x["type"] != 0:
                error["error"].append("model does not support training")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, split, x_train, y_train")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Training the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:    
            model = pickle.loads(base64.b64decode(x["pickle"]))

        training_cases = int(len(x_train) * int(data["split"]) / 100)

        print(training_cases)

        try:
            model.fit(x_train[:training_cases], y_train[:training_cases])
        except Exception as e:
            error["error"].append(str(e))
            return Response(error)

        accuracy = 0
        if len(x_train) - training_cases >= 1:
            accuracy = model.score(x_train[training_cases:], y_train[training_cases:])
        base64_bytes = base64.b64encode(pickle.dumps(model))
        x["buffer"] = base64_bytes.decode('utf-8')

        collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"buffer": x["buffer"]}})
        # Logging activity
        log_instance("Train", "Trained with " + str(len(y_train)) + "cases", instance)

        return Response({"success": "The model was trained successfully", "accuracy": accuracy})


class Test(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_test = []
        y_test = []
        x = ''

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in request.data['x_test'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            x_test = np.array(pd.read_csv(StringIO(text_data)))

            text_data = b""
            for chunk in request.data['y_test'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            y_test = np.array(pd.read_csv(StringIO(text_data))).reshape(1, -1)[0]

            # if len(x_test) != len(y_test):
            #     error["error"].append("error in training data")

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")
            elif x["type"] != 0:
                error["error"].append("model does not support testing")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_test, y_test")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Testing the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:    
            model = pickle.loads(base64.b64decode(x["pickle"]))

        try:
            confidence = model.score(x_test, y_test)
        except Exception as e:
            error["error"].append(str(e))
            return Response(error)

        res = collection.update_one({"_id": ObjectId(data["id"]), "user": user.id, "trash": False},
        {"$set":{"confidence": confidence}})

        # Logging activity
        log_instance("Test", "Accuracy: " + str(confidence), instance)

        return Response({"confidence": confidence})


class Cluster(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_train = []
        y_train = []
        x = ''

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in request.data['x_cluster'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            x_cluster = np.array(pd.read_csv(StringIO(text_data)))

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")
            elif x["type"] != 1:
                error["error"].append("model does not support clustering")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError as e:
            print(e)
            error["error"].append("The following values are required: id, x_cluster")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Training the model
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:    
            model = pickle.loads(base64.b64decode(x["pickle"]))

        try:
            model.fit(x_cluster)
        except Exception as e:
            error["error"].append(str(e))
            return Response(error)

        labels = model.labels_
        cluster_centers = model.cluster_centers_

        base64_bytes = base64.b64encode(pickle.dumps(model))
        x["buffer"] = base64_bytes.decode('utf-8')

        collection.update_one({"_id": instance, "user": user.id, "trash": False}, {"$set": {"buffer": x["buffer"]}})
        # Logging activity
        log_instance("Train", "Clustered with " + str(len(x_cluster)) + "cases", instance)

        return Response({"success": "The model was clustered successfully", "labels": labels, "cluster_centers": cluster_centers})


class Predict(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_predict = []
        x = ''

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in request.data['x_predict'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            x_predict = np.array(pd.read_csv(StringIO(text_data)))

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id":instance, "user":user.id, "trash":False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_predict")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Predicting results
        if x["buffer"]:
            model = pickle.loads(base64.b64decode(x["buffer"]))
        else:    
            model = pickle.loads(base64.b64decode(x["pickle"]))

        try:
            y = model.predict(x_predict)
        except Exception as e:
            error["error"].append(str(e))
            return Response(error)

        # Logging activity
        log_instance("Predict", "Predictions done on " + str(len(x_predict)) + "cases", instance)

        return Response({"result": y})


class Commit(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = ''

        # Validating received data
        try:
            keys = ["id", "description"]
            regex = [text, text]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id":instance, "user":user.id, "trash":False})
            if not x:
                error["error"].append("Instance does not exist")
            elif not x["buffer"]:
                error["error"].append("Nothing to commit")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id, description")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x["traceback"].append(x["pickle"])
        collection.update_one({"_id":instance}, {"$set": {"description": data["description"], 
                                                        "pickle": x["buffer"], 
                                                        "traceback": x["traceback"], 
                                                        "buffer": ""}})

        # Logging activity
        log_instance("Commit", data["description"], instance)


        return Response({"commit": "success"})


class Discard(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = ''

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id":instance, "user":user.id, "trash":False})
            if not x:
                error["error"].append("Instance does not exist")
            elif not x["buffer"]:
                error["error"].append("Nothing to discard")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        collection.update_one({"_id":instance}, {"$set": {"buffer": ""}})

        # Logging activity
        log_instance("Discard", "Discarded buffer model", instance)

        return Response({"discard": "success"})


class RollBack(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_predict = []
        x = ''

        # Validating received data
        try:
            keys = ["id", "index"]
            regex = [text, number]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            data["index"] = int(data["index"])

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id":instance, "user":user.id, "trash":False})
            if not x:
                error["error"].append("Instance does not exist")
            elif len(x["traceback"]) < data["index"]:
                error["error"].append("Invalid rollback index")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id and index")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        collection.update_one({"_id":instance}, {"$set": {"buffer": "", 
                                                        "pickle": x["traceback"][data["index"]], 
                                                        "traceback": x["traceback"][:data["index"]]}})
        x = log.find_one({"instance":instance})
        log.update_one({"instance":instance}, {"$set": {"traceback": x["traceback"][:data["index"]]}})

        # Logging activity
        log_instance("Discard", "Discarded buffer model", instance)

        return Response({"discard": "success"})


class GetStatus(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = ''

        # Validating received data
        try:
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id":instance, "user":user.id, "trash":False})
            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        if x["buffer"]:
            return Response({"status": "Model awaits commit"})
        return Response({"status": "Nothing to commit"})