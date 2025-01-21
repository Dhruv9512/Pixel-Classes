from rest_framework.response import Response
from .models import CourseList
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
# Create your views here.


# CourseList
class courses(APIView):
    @csrf_exempt
    # Fetch all course lists
    def get(self, request):
        try:
            course_lists = CourseList.objects.all()  # Get all CourseList objects
            # If there are no course lists, return a specific message
            if not course_lists:
                return Response({'message': 'No course lists found.'}, status=404)

            # Return the course lists as a response
            return Response({'CourseList': course_lists}, status=200)
        
        except Exception as e:
            # Catch any errors that occur during the database query or response processing
            return Response({'error': str(e)}, status=500)  # 500 is the server error status