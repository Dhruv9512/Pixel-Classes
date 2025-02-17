from django.contrib import admin
from .models import CourseList , QuePdf
# Register your models here.

# Registering the model CourseList
@admin.register(CourseList)
class CourseListAdmin(admin.ModelAdmin):
    list_display = ('id','name','number_sem')

# Registering the model QuePdf
@admin.register(QuePdf)
class QuePdfAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'pdf', 'sem', 'dateCreated', 'timeCreated', 'name')
