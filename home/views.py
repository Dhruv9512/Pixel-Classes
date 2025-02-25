from rest_framework.response import Response
from .models import CourseList , QuePdf , AnsPdf
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer , QuePdfSerializer , AnsPdfSerializer
from rest_framework import status
import requests
from rest_framework.parsers import MultiPartParser, FormParser
import os
from django.core.exceptions import ValidationError

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
        
# Create AnsPdfUploadView here


class AnsPdfUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)  # For handling file uploads

    def post(self, request):
        try:
            # Retrieve data from request
            name = request.data.get('name')
            content = request.data.get('content')
            pdf_file = request.FILES.get('pdf')  # PDF file uploaded by the user

            # Step 3: Upload file to cloud storage
            if pdf_file:
                url = self.upload_pdf_to_vercel(pdf_file)

                # Save the data in the database
                ans_pdf = AnsPdf.objects.create(name=name, content=content, pdf=url)

                # Serialize the response
                serializer = AnsPdfSerializer(ans_pdf)

                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"error": "No PDF file provided."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def upload_pdf_to_vercel(self, pdf_file):
        try:
            # Step 1: Get an actual upload URL from Vercel API
            get_upload_url = "https://api.vercel.com/v2/blob/upload"
            headers = {
                'Authorization': f"Bearer {os.environ.get('BLOB_TOKEN')}",
                'Content-Type': 'application/json',
            }

            response = requests.post(get_upload_url, headers=headers)
            if response.status_code != 200:
                raise ValidationError(f"Failed to get upload URL: {response.text}")

            upload_url = response.json().get("url")
            print("Actual Upload URL:", upload_url)  # Debugging

            # Step 2: Upload file to the received URL
            files = {'file': pdf_file}
            upload_response = requests.put(upload_url, files=files)

            if upload_response.status_code == 200:
                return upload_response.json().get("url")  # The final file URL
            else:
                raise ValidationError(f"File upload failed: {upload_response.text}")

        except Exception as e:
            raise ValidationError(f"Error while uploading file: {str(e)}")
