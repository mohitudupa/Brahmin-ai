from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
import re
import pymongo
from bson.objectid import ObjectId
import bson


number = r'^[+-]?[0-9]+$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
templates = db["templates"]
users = db["users"]


def validate(all_data, data, keys, types, error):
    for i in range(len(keys)):
        if not isinstance(all_data[keys[i]], types[i]):
            error["error"].append("Invalid type for " + keys[i])
            raise AssertionError()
        
    template_params = {}

    for key in data.keys():
        if not isinstance(data[key], list):
            error["error"].append("Value field must be an array")
            raise AssertionError()
        if len(data[key]) and (data[key][0] in ["int", "float", "str"]):
            template_params[key] = data[key][0:1]
        elif (len(data[key]) >= 2) and (data[key][0] == "array"):
            try:
                shape = [int(i) for i in data[key][1:]]
                template_params[key] = ["array"] + shape
            except:
                error["error"].append("Invalid datatype field for array")
                raise AssertionError()
        else:
            error["error"].append("Invalid datatype field")
            raise AssertionError()
    return(template_params)


def add_user_collection(user_id, template, name, docs):
    user_collection = users.find_one({"user": user_id})

    user_collection["templates"][str(template)] = [name, docs]

    users.update_one({"user": user_id}, {"$set": {"templates": user_collection["templates"]}})


def del_user_collection(user_id, template):
    user_collection = users.find_one({"user": user_id})

    del user_collection["templates"][str(template)]

    users.update_one({"user": user_id}, {"$set": {"templates": user_collection["templates"]}})


class CloneTemplate(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            if not isinstance(data["template_id"], str):
                error["error"].append("Invalid type for id")
                raise AssertionError()

            template = ObjectId(data["template_id"])

            if data["template_id"] not in user_collection["templates"].keys():
                error["error"].append("Template does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Cloning instance
        x = templates.find_one({"_id": template})
        x["name"] = x["name"] + " - clone"
        del x["_id"]
        template = templates.insert_one(x).inserted_id

        # Updating the user collection
        add_user_collection(user.id, template, x["name"], x["docs"])

        return Response({"Mongo_instance_id":str(template)})


class UploadTemplate(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["name", "docs", "data"]
            types = [str, str, dict]
            template_params = validate(dict(data), dict(data["data"]), keys, types, error)

            if data["name"] in [i[0] for i in user_collection["templates"].values()]:
                error["error"].append("template name conflict")

        except KeyError as e:
            error["error"].append("The following keys are required: name, docs and data")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        #Saving new template
        data["data"] = template_params
        template = templates.insert_one(data).inserted_id

        # Updating the user collection
        add_user_collection(user.id, template, data["name"], data["docs"])

        return Response({"Mongo_instance_id": str(template)})


class EditTemplate(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["template_id", "new_name", "new_docs", "new_data"]
            types = [str, str, str, dict, str]
            template_params = validate(dict(data), dict(data["new_data"]), keys, types, error)

            template = ObjectId(data["template_id"])

            if data["template_id"] not in user_collection["templates"].keys():
                error["error"].apend("Template does not exist")
            elif data["new_name"] in [i[0] for i in user_collection["templates"].values()]:
                error["error"].append("Template name conflict")

        except bson.errors.InvalidId:
            error["error"].append("Invalid template ID")
        except KeyError as e:
            error["error"].append("The following keys are required: id, new_name, new_docs and new_data")
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Getting template data
        x = templates.find_one({"_id": template})

        # Updating instance entries
        res = templates.update_one({"_id": template} ,
        {"$set":{
            "name": data["new_name"],
            "docs": data["new_docs"],
            "data": template_params,
            }
        })

        # Updating the user collection
        del_user_collection(user.id, template)
        add_user_collection(user.id, template, data["new_name"], data["new_docs"])

        return Response({"Success": "Model updated successfully"})


class DeleteTemplate(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        user_collection = users.find_one({"user": user.id})
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            if not isinstance(data["template_id"], str):
                error["error"].append("Invalid type for id")
                raise AssertionError()

            template = ObjectId(data["template_id"])

            if data["template_id"] not in user_collection["templates"].keys():
                error["error"].apend("Template does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid template ID")
        except KeyError:
            error["error"].append("The following keys are required: id")
        except AssertionError:
            pass
        if error["error"]:
            return Response(error)

        # Deleting template
        x = templates.find_one({"_id": template})
        templates.remove({"_id": template})

        # Updating the user collection
        del_user_collection(user.id, template)

        return Response({"Success": "Template: " + data["template_id"] + " deleted"})
