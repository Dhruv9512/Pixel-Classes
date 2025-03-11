from django.contrib import admin
from .models import CourseList , QuePdf , AnsPdf
# Register your models here.

# Registering the model CourseList
@admin.register(CourseList)
class CourseListAdmin(admin.ModelAdmin):
    list_display = ('id','name','number_sem')

# Registering the model QuePdf
@admin.register(QuePdf)
class QuePdfAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'pdf', 'sem', 'dateCreated', 'timeCreated', 'name' , 'div' , 'year' , 'sub')

# Registering the model AnsPdf
@admin.register(AnsPdf)
class AnsPdfAdmin(admin.ModelAdmin):
    list_display = ('que_pdf', 'name', 'contant', 'pdf')