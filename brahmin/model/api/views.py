from model.models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
import re
import datetime
from sklearn import *
import numpy as np
import base64
import pickle
import pymongo
from bson.objectid import ObjectId
import bson


number = r'^[0-9]+$'
name = r'^[a-zA-Z\' ]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'
boolean = r'^(True)$|(False)$'
array = r'^\[(.*)*\]$'

#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client['modelmgmt']
collection = db['models']

"""
history = db['history']
Work in progress
def log_action(user, action, instance):
    pass
"""

def serialize(x):
   return({"id": str(x["_id"]), "name": x["name"], "version": x["version"],"date_created": x["date_created"],
                         "last_modified": x["last_modified"], "trash": x["trash"], "private": x["private"],
                         "pickle": x["pickle"],"confidence": x["confidence"], "docs": x["docs"]})


def validate(data, keys, regex, error):
    for i in range(len(keys)):
        if not bool(re.match(regex[i], data[keys[i]])):
            error["error"].append(keys[i] + " invalid input")
    return error


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
            error = validate(data, keys, regex, error)

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

        if error["error"]:
            return Response(error)

        # No errors are found, registering user
        user = User.objects.create_user(data['username'], data['email'], data['password'])
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.save()

        # Generate token for user
        token = Token.objects.create(user=user)

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
            error = validate(data, keys, regex, error)

        except KeyError:
            error["error"].append("The following values are required: username and password")

        if error["error"]:
            return Response(error)
        # Auth
        user = authenticate(request, username=data['username'], password=data['password'])
        if user is not None:
            return Response({"token": Token.objects.get(user=user).key})
        return Response({"error": ["Invalid username or password"]})


class Clone(APIView):
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
            error = validate(data, keys, regex, error)

            x=collection.find_one({"_id":ObjectId(data["id"]),"trash":False})

            if not x:
                error["error"].append("Instance does not exist")
            else:    
                if x["private"] and x["user"] != user.id:
                    error["error"].append("Instance is private")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        # Cloning instance
        newmodel = {
                    "user":user.id,
                    "name":x["name"],
                    "version":x["version"],
                    "date_created":datetime.datetime.now(),
                    "last_modified":datetime.datetime.now(),
                    "private":x["private"],
                    "trash":x["trash"],
                    "pickle":x["pickle"],
                    "confidence":x["confidence"],
                    "docs":x["docs"]
                    }
        # Saving new instance
        pid=collection.insert_one(newmodel).inserted_id

        return Response({"Mongo_instance_id":str(pid)})


class Upload(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["name", "version", "pickle", "private", "docs"]
            regex = [text, text, text, boolean, text]
            error = validate(data, keys, regex, error)

            try:
                obj = pickle.loads(base64.b64decode(request.data['pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"].append("Not of type sklearn")
                """
            except:
                error["error"].append("Invalid pickle")

        except KeyError:
            error["error"].append("The following values are required: name, version, pickle, private and docs")

        if error["error"]:
            return Response(error)

        #Saving new instance
        newmodel = {
                    "user":user.id,
                    "name":data["name"],
                    "version":data["version"],
                    "date_created":datetime.datetime.now(),
                    "last_modified":datetime.datetime.now(),
                    "private":eval(data["private"]),
                    "trash":False,
                    "pickle":data["pickle"],
                    "confidence":0.0,
                    "docs":data["docs"]
                    }
        pid=collection.insert_one(newmodel).inserted_id

        return Response({"Mongo_instance_id":str(pid)})


class Update(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []

        # Validating received data
        try:
            keys = ["id", "new_name", "new_version", "new_pickle", "new_private", "new_docs"]
            regex = [text, text, text, text, boolean, text]
            error = validate(data, keys, regex, error)

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id})
            
            if x:
                try:
                    obj = pickle.loads(base64.b64decode(request.data['new_pickle']))
                    """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                        error["error"].append("Not of type sklearn")
                    """
                except Exception:
                    error["error"].append("Invalid pickle")
            else:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, new_name, new_version, "
                                  "new_pickle, new_private and new_docs")

        if error["error"]:
            return Response(error)

        # Updating instance entries
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id} ,
        {"$set":{
            "name":data["new_name"],
            "version":data["new_version"],
            "pickle":data["new_pickle"],
            "private":eval(data["new_private"]),
            "last_modified":datetime.datetime.now(),
            "docs":data["new_docs"]}
        })
        x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id})

        return Response(serialize(x))


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
            error = validate(data, keys, regex, error)

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        # Moving instance into trash
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False} ,
        {"$set":{"trash":True,"last_modified":datetime.datetime.now()}})

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
            error = validate(data, keys, regex, error)

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":True})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        # Restoring instance from trash
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":True} ,
        {"$set":{"trash":False,"last_modified":datetime.datetime.now()}})

        return Response({"Success": "Instance: " + data["id"] + " restored from trash"})


class GetDetails(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        final = {}

        # Validating received data
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)

            x=collection.find({"user":user.id,"trash":eval(data["trash"])})

            # Preparing return json data
            for i in x:
                if i["name"] not in final:
                    final[i["name"]] = {}
                if i["version"] not in final[i["name"]]:
                    final[i["name"]][i["version"]] = []
                final[i["name"]][i["version"]].append({
                    "id": str(i["_id"]),
                    "date_created": i["date_created"],
                    "confidence": i["confidence"]
                })

        except KeyError:
            error["error"].append("The following values are required: trash")

        if error["error"]:
            return Response(error)

        return Response(final)


class GetNames(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        final = {"names": set()}

        # Validating received data
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)

            x = collection.find({"user":user.id,"trash":eval(data["trash"])})

            # Preparing return json data
            for i in x:
                final["names"].add(i["name"])
            final["names"] = list(final["names"])

        except KeyError:
            error["error"].append("The following values are required: trash")

        if error["error"]:
            return Response(error)

        return Response(final)


class GetVersions(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        final = {"versions": set()}

        # Validating received data
        try:
            keys = ["name", "trash"]
            regex = [text, boolean]
            error = validate(data, keys, regex, error)

            x=collection.find({"user":user.id,"name":data["name"],"trash":eval(data["trash"])})

            # Preparing return json data
            for i in x:
                final["versions"].add(i["version"])
            final["versions"] = list(final["versions"])

        except KeyError:
            error["error"].append("The following values are required: name, trash")

        if error["error"]:
            return Response(error)

        return Response(final)


class GetInstances(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        final = {"id": []}

        # Validating received data
        try:
            keys = ["name", "version", "trash"]
            regex = [text, text, boolean]
            error = validate(data, keys, regex, error)
            
            x = collection.find({"user":user.id,"name":data["name"],"version":data["version"],"trash":eval(data["trash"])})

            # Preparing return json data
            for i in x:
                final["id"].append(str(i["_id"]))

        except KeyError:
            error["error"].append("The following values are required: name, version, trash")

        if error["error"]:
            return Response(error)

        return Response(final)


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
            error = validate(data, keys, regex, error)

            x = collection.find_one({"_id":ObjectId(data["id"]),"trash":False})
            
            if not x:
                error["error"].append("Instance does not exist")
            else:
                if x["private"] and x["user"] != user.id:
                    error["error"].append("Instance is private")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")
        
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        return Response(serialize(x))


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
            keys = ["id", "x_train", "y_train"]
            regex = [text, array, array]
            error = validate(data, keys, regex, error)

            x_train = np.array(eval(data['x_train']))
            y_train = np.array(eval(data['y_train']))
            if len(x_train) != len(y_train):
                error["error"].append("Error in training data")

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_train, y_train")

        if error["error"]:
            return Response(error)

        # Training the model
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        cls.fit(x_train, y_train)

        return Response({"success": "The model was trained successfully"})


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
            keys = ["id", "x_test", "y_test"]
            regex = [text, array, array]
            error = validate(data, keys, regex, error)

            x_test = np.array(eval(data['x_test']))
            y_test = np.array(eval(data['y_test']))
            if len(x_test) != len(y_test):
                error["error"].append("error in training data")

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid model ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_test, y_test")

        if error["error"]:
            return Response(error)

        # Testing the model
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        confidence = cls.score(x_test, y_test)
        
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False},
        {"$set":{"confidence":confidence}})
        return Response({"confidence": confidence})


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
            keys = ["id", "x_predict"]
            regex = [text, array]
            error = validate(data, keys, regex, error)

            x_predict = np.array(eval(data['x_predict']))
            print(x_predict)

            x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_predict")

        if error["error"]:
            return Response(error)

        # Predicting results
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        y = cls.predict(x_predict)

        return Response({"result": y})
