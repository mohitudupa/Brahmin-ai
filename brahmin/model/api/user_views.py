from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
import re
import pymongo


name = r'^[a-zA-Z\' -]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'


#mongod connection create a db called "modelmgmt" and a collection called "models" in "modelmgmt" db
client = pymongo.MongoClient()
db = client["modelmgmt"]
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


class Index(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        data = request.data

        print(data)
        print(data["z"])

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
        users.insert_one({"user": user.id, "running": {}, "deleted": {}, "templates": {}})

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
