from django.db import models

# Create your models here.


# model of course list
class CourseList(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255 , unique=True , null=False)
    def _str_(self):
        return self.name
    
# model of QuePdf
from django.db import models

class QuePdf(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    pdf = models.CharField(max_length=255, null=False)
    sem = models.IntegerField(null=False)
    div = models.CharField(max_length=10, null=False)  
    year = models.IntegerField(null=False)  

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year}"
