from django.contrib import admin
from .models import CourseList
# Register your models here.
@admin.register(CourseList)
class CourseListAdmin(admin.ModelAdmin):
    list_display = ('id','name')