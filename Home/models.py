from django.db import models

# Create your models here.
class CourseList(models.Model):
    name = models.CharField(max_length=255, primary_key=True)