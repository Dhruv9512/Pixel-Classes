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
            # Vercel Blob Upload Endpoint (make sure this is the correct URL)
            upload_endpoint = "https://your-vercel-blob-upload-endpoint.com"  # Update with actual endpoint
            headers = {
                'Authorization': f"Bearer {os.environ.get('BLOB_TOKEN')}",  # Ensure the token is set in environment variables
            }

            # Make the upload request to the storage service (Vercel or other service)
            response = requests.post(
                upload_endpoint,
                files={'file': pdf_file},  # Ensure you're passing the file correctly
                headers=headers
            )

            # Check for a successful response (status code 200)
            if response.status_code == 200:
                # Return the URL of the uploaded file from the response
                return response.json().get("url")
            else:
                # Raise an error if the status code is not 200
                raise ValidationError(f"File upload failed with status code: {response.status_code}, {response.text}")

        except Exception as e:
            # Catch any exceptions and raise an error with the exception message
            raise ValidationError(f"An error occurred while uploading the file: {str(e)}")