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


number = r'^[0-9]+$'
name = r'^[a-zA-Z\' ]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'
boolean = r'^(True)$|(False)$'
array = r'^\[(.*)*\]$'


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

        # Validating registration data
        data = request.data
        error = {"error": []}
        x = []
        try:
            keys = ["id"]
            regex = [number]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(id=int(data["id"]))
            if x.private and x.user != user:
                error["error"].append("Model is private")
        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        # Saving new model
        model = Inst(user=user, name=x.name, version=x.version, date_created=datetime.datetime.now(),
                     last_modified=datetime.datetime.now(), private=x.private,
                     trash=x.trash, pickle=x.pickle, confidence=x.confidence, docs=x.docs)
        model.save()

        return Response({"New model id": model.pk})


class Upload(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user

        # Validating registration data
        data = request.data
        error = {"error": []}
        x = []
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
                error["error"].append("invalid pickle")
        except KeyError:
            error["error"].append("The following values are required: name, version, pickle, private and docs")

        if error["error"]:
            return Response(error)

        # Saving model
        model = Inst(user=user, name=data['name'], version=data['version'], date_created=datetime.datetime.now(),
                     last_modified=datetime.datetime.now(), private=eval(data['private']),
                     trash=False, pickle=data['pickle'], confidence=0, docs=data['docs'])
        model.save()

        return Response({"Model ID": model.pk})


class Update(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user

        # Validating registration data
        data = request.data
        error = {"error": []}
        x = []
        try:
            keys = ["id", "new_name", "new_version", "new_pickle", "new_private", "new_docs"]
            regex = [number, text, text, text, boolean, text]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(user=user, id=int(data['id']))

            try:
                obj = pickle.loads(base64.b64decode(request.data['new_pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"].append("Not of type sklearn")
                """
            except Exception:
                error["error"].append("invalid pickle")

        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id, new_name, new_version, "
                                  "new_pickle, new_private and new_docs")

        if error["error"]:
            return Response(error)

        x.name = data["new_name"]
        x.version = data["new_version"]
        x.last_modified = datetime.datetime.now()
        x.pickle = data["new_pickle"]
        x.private = data["new_private"]
        x.docs = data["new_docs"]
        x.save()
        return Response(data)


class Delete(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []
        try:
            keys = ["id"]
            regex = [number]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(user=user, id=int(data["id"]), trash=False)
        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        x.trash = True
        x.last_modified = datetime.datetime.now()
        x.save()
        return Response({"Success": "Model: " + data["id"] + " moved to trash"})


class Restore(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x = []
        try:
            keys = ["id"]
            regex = [number]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(user=user, id=int(data["id"]), trash=True)
        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)

        x.trash = False
        x.last_modified = datetime.datetime.now()
        x.save()
        return Response({"Success": "Model: " + data["id"] + " restored from trash"})


class GetDetails(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        final = {}
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, trash=eval(data['trash']))
            for i in x:
                if i.name not in final:
                    final[i.name] = {}
                if i.version not in final[i.name]:
                    final[i.name][i.version] = []
                final[i.name][i.version].append({
                    "id": i.id,
                    "date_created": i.date_created,
                    "confidence": i.confidence
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
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, trash=eval(data['trash']))
            for i in x:
                final['names'].update({i.name})
            final['names'] = list(final['names'])
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
        try:
            keys = ["name", "trash"]
            regex = [text, boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, name=data['name'], trash=eval(data['trash']))
            for i in x:
                final['versions'].update({i.version})
            final['versions'] = list(final['versions'])
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
        try:
            keys = ["name", "version", "trash"]
            regex = [text, text, boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, name=data["name"], version=data["version"], trash=eval(data['trash']))
            for i in x:
                final["id"].append(i.id)
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

        try:
            keys = ["id",]
            regex = [number]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(id=int(data["id"]))
            if x.private and x.user != user:
                error["error"].append("Model is private")
        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id")

        if error["error"]:
            return Response(error)
        return Response({"id": x.id, "name": x.name, "version": x.version,"date_created": x.date_created,
                         "last_modified": x.last_modified, "trash": x.trash, "private": x.private,
                         "pickle": x.pickle,"confidence": x.confidence, "docs": x.docs})


class Train(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_train = []
        y_train = []
        x = ''
        try:
            keys = ["id", "x_train", "y_train"]
            regex = [number, array, array]
            error = validate(data, keys, regex, error)

            x_train = np.array(eval(data['x_train']))
            y_train = np.array(eval(data['y_train']))
            if len(x_train) != len(y_train):
                error["error"].append("error in training data")

            x = Inst.objects.get(user=user, id=int(data["id"]))
        except Inst.DoesNotExist:
            error["error"].append("Model does not exist")
        except KeyError:
            error["error"].append("The following values are required: id, x_train, y_train")

        if error["error"]:
            return Response(error)

        # Training the model
        cls = pickle.loads(base64.b64decode(x.pickle))
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
        try:
            keys = ["id", "x_test", "y_test"]
            regex = [number, array, array]
            error = validate(data, keys, regex, error)

            x_test = np.array(eval(data['x_test']))
            y_test = np.array(eval(data['y_test']))
            if len(x_test) != len(y_test):
                error["error"].append("error in training data")

            x = Inst.objects.get(user=user, id=int(data["id"]))
        except Inst.DoesNotExist:
            error["error"].append("Invalid model id")
        except KeyError:
            error["error"].append("The following values are required: id, x_test, y_test")

        if error["error"]:
            return Response(error)

        # Testing the model
        cls = pickle.loads(base64.b64decode(x.pickle))
        confidence = cls.score(x_test, y_test)

        x.confidence = confidence
        x.save()

        return Response({"confidence": confidence})


class Predict(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {"error": []}
        x_predict = []
        x = ''
        try:
            keys = ["id", "x_predict"]
            regex = [number, array]
            error = validate(data, keys, regex, error)

            x_predict = np.array(eval(data['x_predict']))
            print(x_predict)

            x = Inst.objects.get(user=user, name=data['name'], version=data['version'])
        except Inst.DoesNotExist:
            error["error"].append("Invalid model id")
        except KeyError:
            error["error"].append("The following values are required: id, x_predict")

        if error["error"]:
            return Response(error)

        # Testing the model
        cls = pickle.loads(base64.b64decode(x.pickle))
        y = cls.predict(x_predict)

        return Response({"result": y})
