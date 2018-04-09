from model.models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication, permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
import re
import datetime
from sklearn import *
import numpy as np
import base64
import pickle


name = r'^[a-zA-Z\' ]+$'
email = r'^.+@.+\..+$'
password = r'^.{8}'
text = r'^.+$'
boolean = r'^(True)$|(False)$'
array = r'^\[(.*)*\]$'


def validate(data, keys, regex, error):
    for i in range(len(keys)):
        if not bool(re.match(regex[i], data[keys[i]])):
            error[keys[i]] = "invalid input"
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
        error = {}

        try:

            keys = ["first_name", "last_name", "email", "password", "username"]
            regex = [name, name, email, password, text]
            error = validate(data, keys, regex, error)

            # Checking if username and email has already been taken

            try:
                User.objects.get(email=data['email'])
                error["email"] = "email already exists"
            except User.DoesNotExist:
                pass

            try:
                User.objects.get(username=data['username'])
                error["username"] = "username already exists"
            except User.DoesNotExist:
                pass

        except KeyError:
            error["format"] = "The following values are required: first_name, last_name, username, password and email"

        if error:
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
        error = {}
        # Validating login data
        try:

            keys = ["password", "username"]
            regex = [password, name]
            error = validate(data, keys, regex, error)

        except KeyError:
            error["format"] = "The following values are required: username and password"

        if error:
            return Response(error)
        # Auth
        user = authenticate(request, username=data['username'], password=data['password'])
        if user is not None:
            return Response({"token": Token.objects.get(user=user).key})
        return Response({"error": "Invalid username or password"})


class Upload(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user

        # Validating registration data
        data = request.data
        error = {}
        x = []
        try:
            keys = ["name", "version", "pickle", "private"]
            regex = [text, text, text, boolean]
            error = validate(data, keys, regex, error)

            x = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=False))
            if x:
                error["error"] = "Model and version already exists, use update command to update required version"
            try:
                obj = pickle.loads(base64.b64decode(request.data['pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"] = "Not of type sklearn"
                """
            except:
                error["error"] = "invalid pickle"
        except KeyError:
            error["format"] = "The following values are required: name, version, pickle and private"

        if error:
            return Response(error)

        # Saving model
        model = Inst(user=user, name=data['name'], version=data['version'], last_modified=datetime.datetime.now(),
                     private=eval(data['private']), trash=False, pickle=data['pickle'])
        model.save()

        return Response({"Success": "Model created " + model.name + " - " + model.version})


class Update(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user

        # Validating registration data
        data = request.data
        error = {}
        x = []
        try:
            keys = ["name", "version", "new_name", "new_version", "new_pickle", "new_private"]
            regex = [text, text, text, text, text, boolean]
            error = validate(data, keys, regex, error)

            x = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=False))
            if not x:
                error["error"] = "Model and version does not exist, use upload command to upload a new model"

            x = list(Inst.objects.filter(user=user, name=data['new_name'], version=data['new_version'], trash=False))
            if x:
                error["error"] = "New model name and version name already exists"

            try:
                obj = pickle.loads(base64.b64decode(request.data['new_pickle']))
                """if str(type(obj))[8:-2].split(".")[0] != "sklearn":
                    error["error"] = "Not of type sklearn"
                """
            except:
                error["error"] = "invalid pickle"
        except KeyError:
            error["format"] = "The following values are required: name, version, new_name, new_version, " \
                              "new_pickle and new_private"

        if error:
            return Response(error)

        x[0].name = data["new_name"]
        x[0].version = data["new_version"]
        x[0].pickle = data["new_pickle"]
        x[0].private = data["new_private"]
        x[0].save()
        return Response(data)


class Delete(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x = []
        try:
            keys = ["name", "version"]
            regex = [text, text]
            error = validate(data, keys, regex, error)

            x = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=False))
            if not x:
                error["error"] = "Model and version does not exist"
            y = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=True))
            if y:
                i = 0
                try:
                    while 1:
                        version = data['version'] + " - " + str(i)
                        Inst.objects.get(user=user, name=data['name'], version=version, trash=True)
                        i += 1
                except Inst.DoesNotExist:
                    y[0].version = y[0].version + " - " + str(i)
                    y[0].save()

        except KeyError:
            error["format"] = "The following values are required: name, version"

        if error:
            return Response(error)

        x[0].trash = True
        x[0].save()
        return Response({"Success": "Model: " + data["name"] + " - " + data["version"] + " moved to trash"})


class Restore(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x = []
        try:
            keys = ["name", "version"]
            regex = [text, text]
            error = validate(data, keys, regex, error)

            x = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=False))
            if x:
                error["error"] = "Model and version already exists, rename conflicting model"

            x = list(Inst.objects.filter(user=user, name=data['name'], version=data['version'], trash=True))
            if not x:
                error["error"] = "Model and version does not exist in trash"
        except KeyError:
            error["format"] = "The following values are required: name, version"

        if error:
            return Response(error)

        x[0].trash = False
        x[0].save()
        return Response({"Success": "Model: " + data["name"] + " - " + data["version"] + " restored from trash"})


class GetDetails(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        final = {}
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, trash=eval(data['trash']))
            for i in x:
                if i.name not in final:
                    final[i.name] = [i.version]
                else:
                    final[i.name].append(i.version)
        except KeyError:
            error["format"] = "The following values are required: trash"

        if error:
            return Response(error)
        return Response(final)


class GetNames(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        final = {"names": []}
        try:
            keys = ["trash"]
            regex = [boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, trash=eval(data['trash']))
            for i in x:
                final['names'].append(i.name)
            final['names'] = list(set(final['names']))
        except KeyError:
            error["format"] = "The following values are required: trash"

        if error:
            return Response(error)
        return Response(final)


class GetVersions(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        final = {"versions": []}
        try:
            keys = ["name", "trash"]
            regex = [text, boolean]
            error = validate(data, keys, regex, error)
            x = Inst.objects.filter(user=user, name=data['name'], trash=eval(data['trash']))
            for i in x:
                final['versions'].append(i.version)
            final['versions'] = list(set(final['versions']))
        except KeyError:
            error["format"] = "The following values are required: name, trash"

        if error:
            return Response(error)
        return Response(final)


class GetModel(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x = []

        try:
            keys = ["name", "version", "trash"]
            regex = [text, text, boolean]
            error = validate(data, keys, regex, error)

            x = Inst.objects.get(user=user, name=data['name'], version=data['version'], trash=eval(data['trash']))
        except Inst.DoesNotExist:
            error["error"] = "model does not exist"
        except KeyError:
            error["format"] = "The following values are required: name, version, trash"

        if error:
            return Response(error)
        return Response({"name": x.name, "version": x.version, "last_modified": x.last_modified,
                         "trash": x.trash, "private": x.private, "pickle": x.pickle})


class Train(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x_train = []
        y_train = []
        x = ''
        try:
            keys = ["name", "version", "x_train", "y_train"]
            regex = [text, text, array, array]
            error = validate(data, keys, regex, error)

            x_train = np.array(eval(data['x_train']))
            y_train = np.array(eval(data['y_train']))

            x = Inst.objects.get(user=user, name=data['name'], version=data['version'])
            if len(x_train) != len(y_train):
                error["error"] = "error in training data"

        except Inst.DoesNotExist:
            error["error"] = "model does not exist"
        except KeyError:
            error["format"] = "The following values are required: name, version, x_train, y_train"

        if error:
            return Response(error)

        # Training the model
        cls = pickle.loads(base64.b64decode(x.pickle))
        cls.fit(x_train, y_train)

        return Response({"success": "True"})


class Test(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x_test = []
        y_test = []
        x = ''
        try:
            keys = ["name", "version", "x_test", "y_test"]
            regex = [text, text, array, array]
            error = validate(data, keys, regex, error)

            x_test = np.array(eval(data['x_test']))
            y_test = np.array(eval(data['y_test']))

            x = Inst.objects.get(user=user, name=data['name'], version=data['version'])
            if len(x_test) != len(y_test):
                error["error"] = "error in training data"

        except Inst.DoesNotExist:
            error["error"] = "model does not exist"
        except KeyError:
            error["format"] = "The following values are required: name, version, x_test, y_test"

        if error:
            return Response(error)

        # Testing the model
        cls = pickle.loads(base64.b64decode(x.pickle))
        confidence = cls.score(x_test, y_test)

        return Response({"confidence": confidence})


class Predict(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        data = request.data
        error = {}
        x_predict = []
        x = ''
        try:
            keys = ["name", "version", "x_predict"]
            regex = [text, text, array]
            error = validate(data, keys, regex, error)

            x_predict = np.array(eval(data['x_predict']))
            print(x_predict)

            x = Inst.objects.get(user=user, name=data['name'], version=data['version'])
        except Inst.DoesNotExist:
            error["error"] = "model does not exist"
        except KeyError:
            error["format"] = "The following values are required: name, version, x_predict"
        if error:
            return Response(error)

        # Testing the model
        cls = pickle.loads(base64.b64decode(x.pickle))
        y = cls.predict(x_predict)

        return Response({"result": y})
