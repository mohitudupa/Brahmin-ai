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
import pymongo
from bson.objectid import ObjectId
import bson
import pickle
import base64


text = r'^.+$'
boolean = r'^(True)$|(False)$'
date_format = r'^[0-3][0-9]-[0-1][0-9]-[0-9]{4}$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
models = db["models"]
templates = db["templates"]
logs = db["logs"]
users = db["users"]


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


class GetModelId(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        model_id = ""

        # Validating received data
        try:
            keys = ["name", "version", "trash"]
            regex = [text, text, boolean]
            types = [str, str, bool]
            error = validate(data, keys, regex, types, error)

            state = "deleted" if data["trash"] else "running"

            for key in user_collection[state].keys():
                if user_collection[state][key][0:2] == [data["name"], data["version"]]:
                    model_id = key
                    break
            else:
                error["error"].append("Model does not exist")

        except KeyError:
            error["error"].append("The following values are required: name, version, trash")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Sending response
        return Response({"id": model_id})


class GetModel(APIView):
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
            error["error"].append("Invalid Model ID")

        except KeyError:
            error["error"].append("The following values are required: model_id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})
        del x["user"]
        x["id"] = str(x["_id"])
        del x["_id"]
        return Response(x)


class GetLog(APIView):
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
            error["error"].append("Invalid Model ID")

        except KeyError:
            error["error"].append("The following values are required: model_id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = logs.find_one({"model": model})

        return Response(x["logs"])


class GetUserLog(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data

        # Fetching logs
        x = logs.find({"user": user.id})

        rdata = {"user": user.username}
        
        for obj in x:
            rdata[str(obj["model"])] = obj["logs"]

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
        x = logs.find({"user": user.id})

        rdata = {"date": date}
        for obj in x:
            activities = []
            for activity in obj["logs"]:
                if activity[0] == data["date"]:
                    activities.append(activity)
            rdata[str(obj["model"])] = activities

        return Response(rdata)


class GetTraceback(APIView):
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

        x = logs.find_one({"model": model})

        return Response({"traceback": x["traceback"]})


class GetStatus(APIView):
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
            return Response({"status": "Model awaits commit"})
        return Response({"status": "Nothing to commit"})


class GetTemplateDetails(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        
        # Sending response
        return Response(user_collection["templates"])


class GetTemplate(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = ''
        
        # Validating received data
        try:
            keys = ["template_id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            template = ObjectId(data["template_id"])

            if data["template_id"] not in user_collection["templates"].keys():
                error["error"].append("Template does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")
        except KeyError:
            error["error"].append("The following values are required: model_id")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Getting template object
        x = templates.find_one({"_id": template})
        del x["_id"]

        # Sending response
        return Response(dict(x))


class GetResult(APIView):
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
            error["error"].append("Invalid Model ID")

        except KeyError:
            error["error"].append("The following values are required: model_id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        x = models.find_one({"_id": model})

        return Response({"result": x["result"]})


class GetAttribute(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["model_id", "attribute"]
            regex = [text, text]
            types = [str, str]
            error = validate(data, keys, regex, types, error)

            model = ObjectId(data["model_id"])

            if data["model_id"] not in user_collection["running"].keys():
                error["error"].append("Model does not exist")
            else:
                x = models.find_one({"_id": model})

                clf = pickle.loads(base64.b64decode(x["pickle"] if x["pickle"] else x["traceback"][-1]))

                if not (data["attribute"] in dir(clf) and not callable(getattr(clf, data["attribute"]))):
                    error["error"].append("Invalid attribute")
            
        except bson.errors.InvalidId:
            error["error"].append("Invalid Model ID")

        except KeyError:
            error["error"].append("The following values are required: model_id")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        res = getattr(clf, data["attribute"])
        if True not in [isinstance(res, i) for i in [str, int, float, list, dict, tuple]]:
            if str(type(res)) == "<class 'numpy.ndarray'>":
                res = res.tolist()
            elif isinstance(res, set):
                res = list(res)
            else:
                base64_bytes = base64.b64encode(pickle.dumps(res))
                res = base64_bytes.decode('utf-8')
        return Response({data["attribute"]: res})