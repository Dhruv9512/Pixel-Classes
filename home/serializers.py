from rest_framework import serializers
from .models import CourseList , QuePdf , AnsPdf


# course list serializer
class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseList
        fields = ['id', 'name' , 'number_sem']  

# QuePdf serializer
class QuePdfSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuePdf
        fields = ['id', 'course', 'pdf', 'sem', 'dateCreated', 'timeCreated', 'name' , 'div' , 'year' , 'sub']

# AnsPdf serializer
class AnsPdfSerializer(serializers.ModelSerializer): 
    class Meta:
        model = AnsPdf
        fields = ['que_pdf', 'name', 'contant', 'pdf']
        fields = '__all__'
