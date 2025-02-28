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
    parser_classes = (MultiPartParser, FormParser)
    @csrf_exempt
    
    def post(self, request):
        try:
            # Retrieve data from request
            name = request.data.get("name")
            content = request.data.get("content")
            pdf_file = request.FILES.get("pdf")

            if not pdf_file:
                return Response({"error": "No PDF file provided."}, status=status.HTTP_400_BAD_REQUEST)

            # Upload the PDF file to Vercel
            file_url = self.upload_pdf_to_vercel(pdf_file)

            # Save to database
            ans_pdf = AnsPdf.objects.create(name=name, content=content, pdf=file_url)

            # Serialize response
            serializer = AnsPdfSerializer(ans_pdf)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print("❌ Internal Server Error:", str(e))  # Debugging
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def upload_pdf_to_vercel(self, pdf_file):
        try:
            print("🔹 Getting Vercel upload URL...")

            # Check if BLOB_TOKEN is set
            blob_token = os.environ.get("BLOB_TOKEN")
            if not blob_token:
                raise ValidationError("BLOB_TOKEN is missing!")

            # Step 1: Get an upload URL from Vercel
            get_upload_url = "https://blob.vercel-storage.com/upload"
            headers = {
                "Authorization": f"Bearer {blob_token}",
                "Content-Type": "application/json",
            }
            json_payload = {"filename": pdf_file.name}

            response = requests.post(get_upload_url, json=json_payload, headers=headers)
            print("🔹 Response from Vercel (Step 1):", response.status_code, response.text)

            if response.status_code != 200:
                raise ValidationError(f"Failed to get upload URL: {response.text}")

            # Extract upload URL
            data = response.json()
            upload_url = data.get("url")
            upload_headers = data.get("headers")

            if not upload_url or not upload_headers:
                raise ValidationError("Invalid response from Vercel, missing 'url' or 'headers'.")

            print("🔹 Actual Upload URL:", upload_url)

            # Step 2: Upload the file to Vercel
            pdf_content = pdf_file.read()
            if not pdf_content:
                raise ValidationError("Error: File content is empty!")

            print("🔹 File Size:", len(pdf_content))

            upload_response = requests.put(upload_url, data=pdf_content, headers=upload_headers)
            print("🔹 Response from Vercel (Step 2):", upload_response.status_code, upload_response.text)

            if upload_response.status_code == 200:
                return upload_url
            else:
                raise ValidationError(f"File upload failed: {upload_response.text}")

        except Exception as e:
            print("❌ Upload Error:", str(e))
            raise ValidationError(f"Error while uploading file: {str(e)}")

