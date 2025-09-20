from django.contrib import admin
from .models import CourseList, QuePdf, AnsPdf, Subject

# Registering the model CourseList
@admin.register(CourseList)
class CourseListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'number_sem')
    search_fields = ('name',)  # quick lookup by name [web:172]
    list_filter = ('number_sem',)  # sidebar filter [web:191]
    list_per_page = 50  # snappier pagination on large datasets [web:172]

# Registering the model QuePdf
@admin.register(QuePdf)
class QuePdfAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'pdf', 'sem', 'dateCreated', 'timeCreated', 'name', 'div', 'year', 'sub', 'choose', 'username')
    list_select_related = ('course',)  # avoid extra queries when showing FK [web:172]
    search_fields = ('name', 'sub', 'username', 'course__name')  # common text lookups [web:172]
    list_filter = ('course', 'sem', 'year', 'choose', 'div', 'sub')  # indexed fields speed filters [web:191]
    list_per_page = 50  # reduce per-page rendering cost [web:172]

# Registering the model AnsPdf
@admin.register(AnsPdf)
class AnsPdfAdmin(admin.ModelAdmin):
    list_display = ('que_pdf', 'name', 'contant', 'pdf')
    list_select_related = ('que_pdf',)  # join que_pdf for list view [web:172]
    search_fields = ('name', 'que_pdf__name', 'que_pdf__sub', 'que_pdf__username')  # useful linked fields [web:172]
    list_filter = ('name', 'que_pdf')  # basic filters; que_pdf FK filter is efficient [web:191]
    list_per_page = 50

# Registering the model Subject
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'sem', 'course_obj', 'name')
    list_select_related = ('course_obj',)  # speed up course_obj column [web:172]
    search_fields = ('name', 'course_obj__name')  # quick search by subject/course [web:172]
    list_filter = ('sem', 'course_obj')  # common filters [web:191]
    list_per_page = 50
