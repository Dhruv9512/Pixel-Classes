from django.db import models

# Create your models here.
class CourseList(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255 , unique=True , null=False)
    def _str_(self):
        return self.name