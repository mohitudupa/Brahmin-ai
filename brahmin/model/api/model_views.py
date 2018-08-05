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
import base64
import pickle
import pymongo
from bson.objectid import ObjectId
import bson


number = r'^[0-9]+$'
# name = r'^[a-zA-Z\' -]+$'
text = r'^.+$'
date_format = r'^[0-3][0-9]-[0-1][0-9]-[0-9]{4}$'
boolean = r'^(True)$|(False)$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
models = db["models"]
logs = db["logs"]
users = db["users"]


def log_instance(action, description, model):
    x = logs.find_one({"model":model})
    now = datetime.datetime.now()
    date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
    x["logs"].append([date, action, description])
    if action == "Commit":
        index = len(x["traceback"]) + 1
        x["traceback"].append([date, index, description])
        logs.update_one({"model": model}, {"$set": {"logs": x["logs"], "traceback": x["traceback"]}})
    else:
        logs.update_one({"model": model}, {"$set": {"logs": x["logs"]}})


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


def add_user_collection(user_id, model, state, name, version, docs, status):
    user_collection = users.find_one({"user": user_id})

    user_collection[state][str(model)] = [name, version, docs, status]

    users.update_one({"user": user_id}, {"$set": {state: user_collection[state]}})


def del_user_collection(user_id, model, state):
    user_collection = users.find_one({"user": user_id})

    del user_collection[state][str(model)]

    users.update_one({"user": user_id}, {"$set": {state: user_collection[state]}})


class CloneModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["model_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Cloning model

        new_model = models.find_one({"_id": model})
        new_model["version"] = new_model["version"] + " - clone"
        new_model["results"] = []
        new_model["task_id"] = 0
        new_model["status"] = 0
        del new_model["_id"]

        # Saving new model
        model = models.insert_one(new_model).inserted_id

        # Creating model log
        now = datetime.datetime.now()
        date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        new_log = {
                    "model": model,
                    "user": user.id,
                    "logs": [[date, "Clone", "Model cloned from user: " + user.username]],
                    "traceback": [],
        }

        # Saving model log
        logs.insert_one(new_log)

        # Updating the user collection
        add_user_collection(user.id, model, "running", new_model["name"], new_model["version"], new_model["docs"], 0)

        return Response({"Mongo_instance_id": str(model)})


class UploadModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["name", "version", "pickle", "docs"]
            regex = [text, text, text, text]
            types = [str, str, str, str]
            error = validate(data, keys, regex, types, error)

            try:
                obj = pickle.loads(base64.b64decode(request.data['pickle']))
            except:
                error["error"].append("Invalid pickle")

            # Checking for conflicts
            if [data["name"], data["version"]] in [i[0:2] for i in user_collection["running"].values()]:
                error["error"].append("Model conflict occoured")

        except KeyError:
            error["error"].append("The following values are required: name, version, pickle, private and docs")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Creating new model
        new_model = {
                    "user":user.id,
                    "name":data["name"],
                    "version":data["version"],
                    "result": [],
                    "status": 0,
                    "task_id": 0,
                    "traceback": [data["pickle"]],
                    "pickle":"",
                    "docs":data["docs"]
                    }
        #Saving new model
        model = models.insert_one(new_model).inserted_id

        # Creating model log
        now = datetime.datetime.now()
        date = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        new_log = {
                    "model": model,
                    "user": user.id,
                    "logs": [[date, "Upload", "Model uploaded by user: " + user.username]],
                    "traceback": [],
        }

        # Saving model log
        logs.insert_one(new_log)

        # Updating the user
        add_user_collection(user.id, model, "running", new_model["name"], new_model["version"], new_model["docs"], 0)

        return Response({"Mongo_instance_id": str(model)})


class EditModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["model_id", "new_name", "new_version", "new_docs", "description"]
            regex = [text, text, text, text, text]
            types = [str, str, str, str, str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])
            
            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")

            # Checking for conflicts
            if [data["new_name"], data["new_version"]] in [i[0:2] for i in user_collection["running"].values()]:
                error["error"].append("Model conflict occoured")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id, new_name, new_version, "
                                  "new_pickle, new_docs and description")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        status = user_collection["running"][data["model_id"]][3]
        # Updating model entries
        res = models.update_one({"_id": model} ,
        {"$set":{
            "name":data["new_name"],
            "version":data["new_version"],
            "docs":data["new_docs"]}
        })

        # Logging activity
        log_instance("Edit", data["description"], model)

        # Updating the user collection
        # Deleting old data
        del_user_collection(user.id, model, "running")
        add_user_collection(user.id, model, "running", data["new_name"], data["new_version"], data["new_docs"], status)

        return Response({"Success": "Model updated successfully"})


class DeleteModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["model_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
            elif user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is busy")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Updating the epoc extension
        new_version = x["version"].split("_rest_")[0] + "_rest_" + str(time.time())

        # Moving model into trash
        models.update_one({"_id": model}, {"$set":{"version": new_version}})

        # Logging activity
        log_instance("Delete", "Model moved to trash", model)

        # Updating the user collection
        del_user_collection(user.id, model, "running")
        add_user_collection(user.id, model, "deleted", x["name"], new_version, x["docs"], 0)

        return Response({"Success": "model: " + data["model_id"] + " moved to trash"})


class RestoreModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["model_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["deleted"].keys():
                error["error"].append("Model does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Updating the epoc extension
        new_version = user_collection["deleted"][data["model_id"]][1].split("_rest_")[0] + "_rest_" + str(time.time())

        # Restoring model from trash
        models.update_one({"_id": model}, {"$set":{"version": new_version}})

        model_name = user_collection["deleted"][data["model_id"]][0]
        model_docs = user_collection["deleted"][data["model_id"]][2]

        # Logging activity
        log_instance("Restore", "Model restored from trash", model)

        # Updating the user collection
        del_user_collection(user.id, model, "deleted")
        add_user_collection(user.id, model, "running", model_name, new_version, model_docs, 0)

        return Response({"Success": "model: " + data["model_id"] + " restored from trash"})


class Commit(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = ''

        # Validating received data
        try:
            keys = ["model_id", "description"]
            regex = [text, text]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
            elif user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is busy")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id, description")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})

        if x["pickle"]:
            x["traceback"].append(x["pickle"])
            models.update_one({"_id": model}, {"$set": {"description": data["description"], 
                                                        "pickle": "", 
                                                        "traceback": x["traceback"]}})

            # Logging activity
            log_instance("Commit", data["description"], model)

            return Response({"commit": "success"})

        return Response({"commit": "nothing to commit"})


class Discard(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = ''

        # Validating received data
        try:
            keys = ["model_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
            elif user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is busy")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})

        if x["pickle"]:
            models.update_one({"_id": model}, {"$set": {"pickle": ""}})

            # Logging activity
            log_instance("Discard", "Discarded buffer model", model)

            return Response({"discard": "success"})

        return Response({"discard": "nothing to discard"})


class RollBack(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        age = 0
        x = ''

        # Validating received data
        try:
            keys = ["model_id", "index"]
            regex = [text, number]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            age = int(data["index"])

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
            elif user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is busy")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id and index")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})

        print(len(x["traceback"]))
        print(age)

        if (len(x["traceback"]) > age) and (age >= 0):
            models.update_one({"_id": model}, {"$set": {"pickle": "", 
                                                            "traceback": x["traceback"][:(age + 1)]}})
            x = logs.find_one({"model": model})
            logs.update_one({"model": model}, {"$set": {"traceback": x["traceback"][:age]}})

            # Logging activity
            log_instance("Rollback", "Rollback to age: " + str(age), model)

            return Response({"rollback": "success"})

        return Response({"rollback": "invalid age"})
