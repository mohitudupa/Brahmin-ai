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
import json


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
variables = db["variables"]


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


class UploadVars(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        new_variable = {}

        try:
            for i in data:
                new_variable[i] = data[i]

            json.dumps(new_variable)
        except TypeError:
            return Response({"error": ["Non json data recieved"]})

        variables.update_one({"user": 1}, {"$set": {"vars": new_variable}})

        return Response({"Response": "Data upload successful"})


class UploadFiles(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        new_variable = {}

        try:
            for i in data:
                text_data = ""
                for chunk in data.chunks():
                    text_data += chunk.decode()
                new_variable[i] = text_data

        variables.update_one({"user": 1}, {"$set": {"files": new_variable}})

        return Response({"Response": "File upload successul"})


class DeleteData(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        variable = variables.find_one({"user": 1})
        error = {"error": []}

        try:
            if isinstance(data["vars"], list):
                for i in data["vars"]:
                    if not isinstance(i, str):
                        error["error"].append("Invalid format for detete data")
                        raise AssertionError()

            for i in data["vars"]:
                if i not in variable["vars"] or i not in variable["files"]:
                    error["error"].append("Variable does not exist")
                    raise AssertionError()

        except KeyError:
            error["error"].append("Invalid format for detete data")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        for i in data:
            if i in variable["vars"]:
                del variable["vars"][i]
            else:
                del variable["files"][i]
        del variable["_id"], variable["user"]

        variables.update_one({"user": 1}, {"$set": {variable}})

        return Response({"Response": "Data delete successful"})
