from rest_framework import serializers
from .models import CourseList, QuePdf, AnsPdf, Subject

# course list serializer
class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseList
        fields = ['id', 'name', 'number_sem']
        read_only_fields = ['id']  # id is not written by clients [web:27]

# QuePdf serializer
class QuePdfSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuePdf
        fields = ['id', 'course', 'pdf', 'sem', 'dateCreated', 'timeCreated', 'name', 'div', 'year', 'sub', 'choose', 'username']
        read_only_fields = ['id', 'dateCreated', 'timeCreated']  # these are typically system-set [web:27]

# AnsPdf serializer
class AnsPdfSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnsPdf
        # Keep explicit list to avoid unintended fields and preserve API contract [web:27]
        fields = ['id', 'que_pdf', 'name', 'contant', 'pdf']
        read_only_fields = ['id']  # primary key is read-only [web:27]

# Subject serializer
class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'sem']
        read_only_fields = ['id']  # id is read-only [web:27]
