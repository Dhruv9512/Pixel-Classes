from django.db import models
from datetime import datetime
import requests
from django.contrib.auth.models import User

# Function to return the current time as a string in HH:MM:SS format
def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

# Function to return the current date as a string in YYYY-MM-DD format
def get_current_date():
    return datetime.today().strftime("%Y-%m-%d")

# Model of Course List
class CourseList(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, null=True)
    number_sem = models.IntegerField(null=True)

    def __str__(self):
        return self.name

# Model of QuePdf
class QuePdf(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    pdf = models.URLField(max_length=255, null=True)
    sem = models.IntegerField(null=True)
    div = models.CharField(max_length=10, null=True)
    year = models.IntegerField(null=True)
    sub = models.CharField(max_length=100, null=True)
    # Store date and time as strings
    dateCreated = models.CharField(max_length=10, default=get_current_date)  # Format: YYYY-MM-DD
    timeCreated = models.CharField(max_length=8, default=get_current_time)   # Format: HH:MM:SS
    
    # Name of the PDF
    name = models.CharField(max_length=255, null=True)

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year} - {self.name}"
    
class AnsPdf(models.Model):
    que_pdf  = models.ForeignKey(QuePdf, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=True)
    contant = models.TextField(null=True)
    pdf = models.URLField(max_length=255, null=True)


# Model for subject name
class Subject(models.Model):

    id = models.AutoField(primary_key=True)
    sem = models.IntegerField(null=True)
    course_obj = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name


# profile
class profile(models.Model):
    id = models.AutoField(primary_key=True)
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.CharField(max_length=20 , null=True)