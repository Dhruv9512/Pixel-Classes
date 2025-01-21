from rest_framework import serializers
from .models import CourseList

class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseList
        fields = ['id', 'name']  # specify the fields to include in the response
