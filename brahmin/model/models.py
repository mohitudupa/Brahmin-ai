from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Inst(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    version = models.CharField(max_length=50)
    last_modified = models.DateTimeField()
    trash = models.BooleanField()
    private = models.BooleanField()
    pickle = models.TextField()

    def __str__(self):
        return "Model: " + self.user.first_name + " - " + str(self.name) + " ( " + str(self.version) + " )"
