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
import numpy as np
import pandas as pd
from io import StringIO
import pymongo
from bson.objectid import ObjectId
import bson
from tasks import *
from celery.task.control import revoke


number = r'^[0-9]+$'
text = r'^.'
date_format = r'^[0-3][0-9]-[0-1][0-9]-[0-9]{4}$'
func = r"__.*__"
boolean = r'^(True)$|(False)$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
models = db["models"]
templates = db["templates"]
logs = db["logs"]
users = db["users"]


def array(x, data):
    text_data = ""
    for chunk in data.chunks():
        text_data += chunk.decode()

    shape = [int(i) for i in x]
    return np.array(pd.read_csv(StringIO(text_data))).reshape(shape).tolist()


types = ["str", "int", "float", "bool"]

def get_params(type_data, data):
    params = {}
    for i in type_data:
        if i[1] in types:
            params[i[0]] = eval(i[1])(data[i[0]][0])
        elif i[1] == "array":
            params[i[0]] = array(i[2:], data[i[0]][0])
        else:
            raise AssertionError()
    return params


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
        print(data[keys[i]], str(type(data[keys[i]])), types[i])
        if isinstance(data[keys[i]], types[i]):
            if not bool(re.match(regex[i], str(data[keys[i]]))):
                error["error"].append("Invalid value for " + keys[i])
                raise AssertionError()
        else:
            error["error"].append("Invalid type for " + keys[i])
            raise AssertionError()
    return error


class ExecCommand(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        params = {}
        x = ''

        try:
            keys = ["model_id", "kwargs", "function", "type_data"]
            regex = [text, boolean, text, text]
            types = [str, str, str, str]
            error = validate(data, keys, regex, types, error)

            data["type_data"] = eval(data["type_data"])
            data["kwargs"] = eval(data["kwargs"])

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
                raise AssertionError()
            
            if user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is busy")
                raise AssertionError()

            x = models.find_one({"_id": model})
            clf = x["pickle"] if x["pickle"] else x["traceback"][-1]

            input_params = dict(data)
            del input_params["function"], input_params["kwargs"]
            del input_params["model_id"], input_params["type_data"]

            params = get_params(data["type_data"], input_params)

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: model_id, kwargs, function, type_data")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")

        except ValueError:
            error["error"].append("Invalid template parameters")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        params["model_id"] = data["model_id"]
        params["clf"] = clf
        params["cmd"] = data["function"]
        params["user_id"] = user.id
        params["kwargs"] = data["kwargs"]

        # print("Params:", params)

        result = sub_precess.delay(**params)
        task_id = result.task_id

        user_collection["running"][data["model_id"]][3] = 1
        users.update_one({"user": user.id}, {"$set": {"running": user_collection["running"]}})

        return Response({"success": "The model is queued for: " + str(data["function"])})


class Abort(APIView):
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
            elif not user_collection["running"][data["model_id"]][3]:
                error["error"].append("Model is idle")
            
        except bson.errors.InvalidId:
            error["error"].append("Invalid Model ID")

        except KeyError:
            error["error"].append("The following values are required: model_id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})

        revoke(str(x["task_id"]))

        user_collection["running"][data["model_id"]][3] = 0
        users.update_one({"user": user.id}, {"$set": {"running": user_collection["running"]}})

        return Response({"Abort": "Success"})
