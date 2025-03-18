from rest_framework import serializers
from .models import profile


# Profile serializer
class profileSerializer(serializers.ModelSerializer):

    class Meta:
        model = profile
        fields = ['id' , 'user_obj' , 'course']
    
    def create(self, validated_data):
        return profile.objects.create(**validated_data) 
    