from rest_framework.response import Response
from .models import CourseList
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer

class courses(APIView):
    @csrf_exempt
    def get(self, request):
        try:
            course_lists = CourseList.objects.all()  # Get all CourseList objects
            if not course_lists:
                return Response({'message': 'No course lists found.'}, status=404)

            # Use the serializer to convert queryset into JSON
            serializer = CourseListSerializer(course_lists, many=True)
            return Response({'CourseList': serializer.data}, status=200)

        except Exception as e:
            return Response({'error': str(e)}, status=500)
