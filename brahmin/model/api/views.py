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


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
collection = db["models"]
log = db["log"]
users = db["users"]


def log_instance(action, instance):
    x = log.find_one({"instance":instance})
    now = datetime.datetime.now()
    key = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
    if key not in x:
        x[key] = []        
    x[key].append(action)
    log.update_one({"instance":instance}, {"$set": {key: x[key]}})


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


def update_user_collection(id, name, version, instance_id, trash):
    user_collection = users.find_one({"user": id})

    if name not in user_collection:
        user_collection[name] = {}
    if version not in user_collection[name]:
        user_collection[name][version] = {"True": [], "False": []}
    user_collection[name][version][str(trash)].append(instance_id)

    users.update_one({"user": id}, {"$set": {name: user_collection[name]}})




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
        users.insert_one({"user": user.id})

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
            x=collection.find_one({"_id": instance, "trash": False})

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

        # Creating instance log
        now = datetime.datetime.now()
        key = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        newlog = {
                    "instance": pid,
                    "user": user.id,
                    key: ["Clone"]
        }
        # Saving instance log
        log.insert_one(newlog).inserted_id

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], pid, x["trash"])

        res = users.update_one({"_id":ObjectId(data["id"]),"user":user.id} ,
        {"$set":{
            "name":data["new_name"],
            "version":data["new_version"],
            "pickle":data["new_pickle"],
            "private":data["new_private"],
            "last_modified":datetime.datetime.now(),
            "docs":data["new_docs"]}
        })

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
            types = [str, str, str, bool, str]
            error = validate(data, keys, regex, types, error)

            try:
                obj = pickle.loads(base64.b64decode(request.data['pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"].append("Not of type sklearn")
                """
            except:
                error["error"].append("Invalid pickle")

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
                    "trash":False,
                    "pickle":data["pickle"],
                    "confidence":0.0,
                    "docs":data["docs"]
                    }
        #Saving new instance
        pid=collection.insert_one(newmodel).inserted_id

        # Creating instance log
        now = datetime.datetime.now()
        key = "{0:02}-{1:02}-{2:04}".format(now.day, now.month, now.year)
        newlog = {
                    "instance": pid,
                    "user": user.id,
                    key: ["Upload"]
        }
        # Saving instance log
        log.insert_one(newlog).inserted_id

        # Updating the user collection
        update_user_collection(user.id, newmodel["name"], newmodel["version"], pid, newmodel["trash"])

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
            types = [str, str, str, str, bool, str]
            error = validate(data, keys, regex, types, error)

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance,"user": user.id, "trash": False})
            
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
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Updating instance entries
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id} ,
        {"$set":{
            "name":data["new_name"],
            "version":data["new_version"],
            "pickle":data["new_pickle"],
            "private":data["new_private"],
            "last_modified":datetime.datetime.now(),
            "docs":data["new_docs"]}
        })
        x = collection.find_one({"_id":ObjectId(data["id"]),"user":user.id})

        # Logging activity
        log_instance("Update", instance)

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], pid, x["trash"])

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

        # Moving instance into trash
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":False} ,
        {"$set":{"trash":True,"last_modified":datetime.datetime.now()}})

        # Logging activity
        log_instance("Delete", instance)

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], pid, True)

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

        # Restoring instance from trash
        res = collection.update_one({"_id":ObjectId(data["id"]),"user":user.id,"trash":True} ,
        {"$set":{"trash":False,"last_modified":datetime.datetime.now()}})

        # Logging activity
        log_instance("Restore", instance)

        # Updating the user collection
        update_user_collection(user.id, x["name"], x["version"], pid, False)

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
            types = [bool]
            error = validate(data, keys, regex, types, error)

        except KeyError:
            error["error"].append("The following values are required: trash")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Fetching instance data
        x=collection.find({"user":user.id,"trash":data["trash"]})

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
            types = [bool]
            error = validate(data, keys, regex, types, error)

        except KeyError:
            error["error"].append("The following values are required: trash")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Fetching instance data
        x = collection.find({"user":user.id,"trash":data["trash"]})

        # Preparing return json data
        for i in x:
            final["names"].add(i["name"])
        final["names"] = list(final["names"])

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
            types = [str, bool]
            error = validate(data, keys, regex, types, error)

        except KeyError:
            error["error"].append("The following values are required: name, trash")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Fetching instance data
        x=collection.find({"user":user.id,"name":data["name"],"trash":data["trash"]})

        # Preparing return json data
        for i in x:
            final["versions"].add(i["version"])
        final["versions"] = list(final["versions"])

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
            types = [str, str, bool]
            error = validate(data, keys, regex, types, error)

        except KeyError:
            error["error"].append("The following values are required: name, version, trash")

        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Fetching Instance data
        x = collection.find({"user":user.id,"name":data["name"],"version":data["version"],"trash":data["trash"]})

        # Preparing return json data
        for i in x:
            final["id"].append(str(i["_id"]))

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
        x["instance"] = str(x["instance"])

        return Response(x)


class GetUserLog(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        
        # Fetching logs
        x = log.find({"user": user.id})

        rdata = {"user": user.username, "activities": []}
        for obj in x:
            del obj["user"]
            del obj["_id"]
            obj["instance"]=str(obj["instance"])
            rdata["activities"].append(obj)
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
        x = log.find({"user": user.id, data["date"]: {"$exists" : True}})

        rdata = {"date": date, "activities": {}}
        for obj in x:
            rdata["activities"][str(obj["instance"])]=obj[data["date"]]
        return Response(rdata)


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
            keys = ["id"]
            regex = [text]
            types = [str]
            error = validate(data, keys, regex, types, error)

            text_data = b""
            for chunk in request.data['x_train'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            x_train = np.array(pd.read_csv(StringIO(text_data)))

            text_data = b""
            for chunk in request.data['y_train'].chunks():
                text_data += chunk
            text_data = text_data.decode()

            y_train = np.array(pd.read_csv(StringIO(text_data)))[0]

            # if len(x_train) != len(y_train):
            #     error["error"].append("Error in training data")

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")

        except bson.errors.InvalidId:
            error["error"].append("Invalid instance ID")

        except KeyError:
            error["error"].append("The following values are required: id, x_train, y_train")

        except UnicodeDecodeError:
            error["error"].append("Invalid text encoding")

        except AttributeError:
            error["error"].append("A text file must be uploaded")
        
        except AssertionError:
            pass

        if error["error"]:
            return Response(error)

        # Training the model
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        cls.fit(x_train, y_train)

        # Logging activity
        log_instance("Train", instance)

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

            y_test = np.array(pd.read_csv(StringIO(text_data)))[0]

            # if len(x_test) != len(y_test):
            #     error["error"].append("error in training data")

            instance = ObjectId(data["id"])
            x = collection.find_one({"_id": instance, "user": user.id, "trash": False})

            if not x:
                error["error"].append("Instance does not exist")

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
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        confidence = cls.score(x_test, y_test)
        
        res = collection.update_one({"_id": ObjectId(data["id"]), "user": user.id, "trash": False},
        {"$set":{"confidence": confidence}})

        # Logging activity
        log_instance("Test", instance)

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
        cls = pickle.loads(base64.b64decode(x["pickle"]))
        y = cls.predict(x_predict)

        # Logging activity
        log_instance("Predict", instance)

        return Response({"result": y})
