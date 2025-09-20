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
    name = models.CharField(max_length=255, unique=True, db_index=True)  # fast lookups by name [web:27]
    number_sem = models.IntegerField()

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['name']),  # explicit even with unique for clarity [web:27]
        ]

# Model of QuePdf
class QuePdf(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(CourseList, on_delete=models.CASCADE, related_name='que_pdfs', db_index=True)  # join speed [web:27]
    pdf = models.URLField(max_length=255)
    sem = models.IntegerField(db_index=True)  # often filtered by sem [web:27]
    div = models.CharField(max_length=10)
    year = models.IntegerField(db_index=True)  # often filtered by year [web:27]
    sub = models.CharField(max_length=100, db_index=True)  # subject filters [web:27]
    dateCreated = models.CharField(max_length=10, default=get_current_date)  # YYYY-MM-DD
    timeCreated = models.CharField(max_length=8, default=get_current_time)   # HH:MM AM/PM
    name = models.CharField(max_length=255, db_index=True)  # frequently filtered/ordered [web:27]
    choose = models.CharField(max_length=40, db_index=True)  # category selection filters [web:27]
    username = models.CharField(max_length=255, db_index=True)  # owner filters [web:27]

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year} - {self.name}"

    class Meta:
        indexes = [
            models.Index(fields=['course', 'sem', 'sub']),          # common composite filter [web:27]
            models.Index(fields=['username', 'choose', 'year']),    # tuned for list queries [web:27]
        ]

# Model of AnsPdf
class AnsPdf(models.Model):
    que_pdf = models.ForeignKey(QuePdf, on_delete=models.CASCADE, related_name='answers', db_index=True)  # FK join speed [web:27]
    name = models.CharField(max_length=255, db_index=True)  # list by user name [web:27]
    contant = models.TextField()
    pdf = models.URLField(max_length=255, default="Admin")

    class Meta:
        indexes = [
            models.Index(fields=['name']),               # fast name filters [web:27]
            models.Index(fields=['que_pdf', 'name']),    # list answers per que_pdf [web:27]
        ]

# Model for subject name
class Subject(models.Model):
    id = models.AutoField(primary_key=True)
    sem = models.IntegerField(db_index=True)  # frequent filter [web:27]
    course_obj = models.ForeignKey(CourseList, on_delete=models.CASCADE, related_name='subjects', db_index=True)  # join speed [web:27]
    name = models.CharField(max_length=100, db_index=True)  # subject lookups [web:27]

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['course_obj', 'sem', 'name']),  # used by subject listing per course/sem [web:27]
        ]
