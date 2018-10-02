from celery import Celery
from sklearn import *
import numpy as np
import pickle
import base64
import pymongo
from bson.objectid import ObjectId
import datetime


def log_instance(action, description, model, logs):
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


app = Celery("tasks", broker="amqp://localhost//")


@app.task
def sub_precess(**kwargs):
    
    client = pymongo.MongoClient()
    db = client["modelmgmt"]
    models = db["models"]
    logs = db["logs"]
    users = db["users"]

    model = ObjectId(kwargs["model_id"])
    clf = pickle.loads(base64.b64decode(kwargs["clf"]))
    cmd = kwargs["cmd"]
    user_id = kwargs["user_id"]
    attribute_style = kwargs["kwargs"]

    del kwargs["model_id"]
    del kwargs["clf"]
    del kwargs["cmd"]
    del kwargs["user_id"]
    del kwargs["kwargs"]

    for i in kwargs.keys():
        if isinstance(kwargs[i], list):
            kwargs[i] = np.array(kwargs[i])

    user_collection = users.find_one({"user": user_id})
    try:
        if attribute_style:
            res = getattr(clf, cmd)(**kwargs)
        else:
            res = getattr(clf, cmd)(*kwargs.values())
        user_collection = users.find_one({"user": user_id})
        if not user_collection["running"][str(model)][3]:
            return True


        if type(res) == type(clf):
            log_instance("Train", "finished running " + str(cmd), model, logs)
            base64_bytes = base64.b64encode(pickle.dumps(res))
            res = base64_bytes.decode('utf-8')
            models.update_one({"_id": model}, {"$set": {"pickle": res, "result": [0, cmd, ""], "task_id": "0"}})
        elif str(type(res)) == "<class 'numpy.ndarray'>":
            res = res.tolist()
            log_instance("Train", "finished running " + str(cmd), model, logs)
            models.update_one({"_id": model}, {"$set": {"result": [0, cmd, res], "task_id": "0"}})
        elif res:
            log_instance("Train", "finished running " + str(cmd), model, logs)
            models.update_one({"_id": model}, {"$set": {"result": [0, cmd, res], "task_id": "0"}})
        else:
            log_instance("Train", "finished running " + str(cmd), model, logs)
            models.update_one({"_id": model}, {"$set": {"result": [0, cmd, ""], "task_id": "0"}})
    except Exception as e:
        models.update_one({"_id": model}, {"$set": {"result": [1, cmd, str(e)], "task_id": "0"}})
    finally:
        user_collection["running"][str(model)][3] = 0
        users.update_one({"user": user_id}, {"$set": {"running": user_collection["running"], "task_id": "0"}})
        return True
