from rest_framework.response import Response
from .models import CourseList , QuePdf
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer , QuePdfSerializer
from rest_framework import status


# Create your views here.
class coursesView(APIView):
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


# Create QuePdfView here
class QuePdfView(APIView):
    @csrf_exempt
    def post(self, request):
        try:
            # Fetch all QuePdf records
            queryset = QuePdf.objects.all()

            # Serialize the queryset
            serializer = QuePdfSerializer(queryset, many=True)

            # Return serialized data as JSON
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle any errors that occur during the process
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )