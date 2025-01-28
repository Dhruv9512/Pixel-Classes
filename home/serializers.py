from rest_framework import serializers
from .models import CourseList , QuePdf


# course list serializer
class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseList
        fields = ['id', 'name']  # specify the fields to include in the response

# QuePdf serializer
class QuePdfSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuePdf
        fields = ['id', 'course', 'pdf', 'sem', 'name'] 
