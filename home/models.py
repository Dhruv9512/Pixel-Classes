from django.db import models
from datetime import datetime
import requests
import os
# Vercel Blob read/write token (you may want to load this from environment variables in production)
BLOB_READ_WRITE_TOKEN = os.environ.get("BLOB_TOKEN")

# Function to return the current time as a string in HH:MM:SS format
def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

# Function to return the current date as a string in YYYY-MM-DD format
def get_current_date():
    return datetime.today().strftime("%Y-%m-%d")

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
    
    # Store date and time as strings
    dateCreated = models.CharField(max_length=10, default=get_current_date)  # Format: YYYY-MM-DD
    timeCreated = models.CharField(max_length=8, default=get_current_time)   # Format: HH:MM:SS
    
    # Store PDF size in MB (2 decimal places)
    size = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Name of the PDF
    name = models.CharField(max_length=255, null=False)

    def save(self, *args, **kwargs):
        # Fetch file size from URL before saving the instance
        if self.pdf:
            self.size = self.get_pdf_size_from_url(self.pdf)
        super().save(*args, **kwargs)

    def get_pdf_size_from_url(self, url):
        # Prepare headers including the blob token for authorization
        headers = {
            "Authorization": f"Bearer {BLOB_READ_WRITE_TOKEN}"
        }
        try:
            # Try a HEAD request first, including the authorization header
            response = requests.head(url, headers=headers)
            content_length = response.headers.get('Content-Length')
            
            # Fallback: If Content-Length is not provided, try a GET request with streaming
            if content_length is None:
                response = requests.get(url, headers=headers, stream=True)
                content_length = response.headers.get('Content-Length')
            
            if content_length:
                file_size = int(content_length)
                return round(file_size / (1024 * 1024), 2)  # Convert bytes to MB
            else:
                print("Content-Length header not found for URL:", url)
                return 0.0
        except requests.exceptions.RequestException as e:
            print(f"Error fetching size for {url}: {e}")
            return 0.0

    def __str__(self):
        return f"{self.course} - Sem {self.sem} - {self.div} - Year {self.year} - {self.name}"
