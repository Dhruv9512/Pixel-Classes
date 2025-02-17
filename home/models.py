from django.db import models
from datetime import datetime
import requests

# Model of Course List
class CourseList(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, null=False)
    number_sem = models.IntegerField(null=False)

    def __str__(self):
        return self.name

# Model of QuePdf
class QuePdf(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(CourseList, on_delete=models.CASCADE)
    pdf = models.URLField(max_length=255, null=False)
    sem = models.IntegerField(null=False)
    div = models.CharField(max_length=10, null=False)  
    year = models.IntegerField(null=False)  
    
    # Automatically set date and time when a record is created
    dateCreated = models.DateField(auto_now_add=True)
    timeCreated = models.TimeField(auto_now_add=True)
    
    # Store PDF size in MB (2 decimal places)
    size = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Name of the PDF
    name = models.CharField(max_length=255, null=False)

    def save(self, *args, **kwargs):
        # Fetch file size from URL before saving the instance
        if self.pdf:
            self.size = self.get_pdf_size_from_url(self.pdf)
        
        super().save(*args, **kwargs)  # Call the real save() method to save the instance

    def get_pdf_size_from_url(self, url):
        try:
            # Send a HEAD request to get file size without downloading
            response = requests.head(url)
            file_size = int(response.headers.get('Content-Length', 0))  # Size in bytes
            return round(file_size / (1024 * 1024), 2)  # Convert to MB and round to 2 decimal places
        except requests.exceptions.RequestException as e:
            print(f"Error fetching PDF: {e}")
            return 0.0  # Return 0 if there is an error

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year} - {self.name}"
