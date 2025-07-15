from django.db import models
from datetime import datetime
import pytz


# Function to return the current time as a string in HH:MM:SS format
def get_current_time():
    ist = pytz.timezone('Asia/Kolkata')  
    return datetime.now(ist).strftime("%I:%M %p")  # 12-hour format with AM/PM

# Function to return the current date as a string in YYYY-MM-DD format
def get_current_date():
    return datetime.today().strftime("%Y-%m-%d")

# Model of Course List
class CourseList(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)  # Removed null=True
    number_sem = models.IntegerField()  # Removed null=True

    def __str__(self):
        return self.name

# Model of QuePdf
class QuePdf(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    pdf = models.URLField(max_length=255)  # Removed null=True
    sem = models.IntegerField()  # Removed null=True
    div = models.CharField(max_length=10)  # Removed null=True
    year = models.IntegerField()  # Removed null=True
    sub = models.CharField(max_length=100)  # Removed null=True
    dateCreated = models.CharField(max_length=10, default=get_current_date)  # Format: YYYY-MM-DD
    timeCreated = models.CharField(max_length=8, default=get_current_time)  # Format: HH:MM:SS
    name = models.CharField(max_length=255)  # Removed null=True
    choose = models.CharField(max_length=40)

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year} - {self.name}"

# Model of AnsPdf
class AnsPdf(models.Model):
    que_pdf = models.ForeignKey(QuePdf, on_delete=models.CASCADE)
    name = models.CharField(max_length=255) 
    contant = models.TextField() 
    pdf = models.URLField(max_length=255) 

# Model for subject name
class Subject(models.Model):
    id = models.AutoField(primary_key=True)
    sem = models.IntegerField()  # Removed null=True
    course_obj = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # Removed null=True

    def __str__(self):
        return self.name


