from rest_framework.response import Response
from .models import CourseList, QuePdf, AnsPdf , Subject
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer, QuePdfSerializer, AnsPdfSerializer , SubjectSerializer
from rest_framework import status
import os
from django.utils.decorators import method_decorator
from vercel_blob import put
from rest_framework.parsers import MultiPartParser, FormParser
from dotenv import load_dotenv
import logging
# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
# Load environment variables
load_dotenv()

# ✅ Course List View

@method_decorator(csrf_exempt, name="dispatch")
class CoursesView(APIView):
    def get(self, request):
        try:
            courses = CourseList.objects.all()

            if not courses.exists():
                return Response(
                    {"message": "No courses available."},
                    status=status.HTTP_204_NO_CONTENT
                )

            serializer = CourseListSerializer(courses, many=True)
            return Response(
                {"data": serializer.data, "message": "Courses retrieved successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error retrieving courses.")
            return Response(
                {"error": "Something went wrong while fetching the course list."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

# ✅ QuePdf View (Fixed to GET)

@method_decorator(csrf_exempt, name="dispatch")
class QuePdfView(APIView):
    def get(self, request):
        try:
            # Efficient query to avoid unnecessary database hits
            que_pdfs = QuePdf.objects.all()

            if not que_pdfs.exists():
                return Response(
                    {"message": "No question PDFs found."},
                    status=status.HTTP_204_NO_CONTENT
                )

            serializer = QuePdfSerializer(que_pdfs, many=True)
            return Response(
                {"data": serializer.data, "message": "PDF list retrieved successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error while fetching QuePdf data.")
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
# ✅ QuePdf Upload View (File Upload Handling)
@method_decorator(csrf_exempt, name="dispatch")
class QuePdfSubView(APIView):
    def post(self, request):
        try:
            sub = request.data.get("sub")
            course_name = request.data.get("course_name")

            if not sub or not course_name:
                return Response(
                    {"error": "Both 'sub' and 'course_name' are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Efficient query: only retrieve 'id' instead of full CourseList object
            course = CourseList.objects.only("id").filter(name=course_name).first()
            if not course:
                return Response({"error": "Invalid course name."}, status=status.HTTP_404_NOT_FOUND)

            # Filter QuePdf by subject and course ID
            queryset = QuePdf.objects.filter(sub=sub, course_id=course.id)
            if not queryset.exists():
                return Response({"message": "No PDFs found for the selected course and subject."}, status=status.HTTP_200_OK)

            serializer = QuePdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# Get all subject
@method_decorator(csrf_exempt, name="dispatch")
class QuePdfGetSubView(APIView):
    def post(self, request):
        try:
            course_name = request.data.get("course_name")
            sem = request.data.get("sem")

            if not course_name or not sem:
                return Response(
                    {"error": "Both 'course_name' and 'sem' are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subjects = Subject.objects.filter(
                course_obj__name=course_name,
                sem=sem
            ).distinct()

            if not subjects.exists():
                return Response(
                    {"message": "No subjects found for the given course and semester."},
                    status=status.HTTP_204_NO_CONTENT
                )

            serializer = SubjectSerializer(subjects, many=True)
            return Response(
                {"data": serializer.data, "message": "Subjects retrieved successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error retrieving subjects for course and semester.")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name="dispatch")
class AnsPdfUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        try:
            name = request.data.get("name")
            content = request.data.get("content")
            file = request.FILES.get("pdf")
            que_pdf_id = request.data.get("id")

            # 🔍 Input validation
            if not file or not name or not content or not que_pdf_id:
                return Response(
                    {"error": "Missing required fields."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 🔍 Get QuePdf object
            try:
                que_pdf = QuePdf.objects.get(id=que_pdf_id)
            except QuePdf.DoesNotExist:
                return Response(
                    {"error": "Invalid question PDF ID."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 🔐 Token validation
            token = os.getenv("BLOB_READ_WRITE_TOKEN")
            if not token:
                logger.error("Vercel Blob token not set in environment variables.")
                return Response(
                    {"error": "Vercel Blob token missing. Check environment settings."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 📤 Upload to Vercel Blob
            try:
                blob = put(f"AnsPdf/{file.name}", file.read())
                blob_url = blob.get("url")
                if not blob_url:
                    raise Exception("Blob upload failed, no URL returned.")
            except Exception as upload_err:
                logger.exception("Blob upload failed.")
                return Response(
                    {"error": f"Blob upload failed: {str(upload_err)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 💾 Save record to database
            ans_pdf = AnsPdf.objects.create(
                que_pdf=que_pdf,
                name=name,
                contant=content,
                pdf=blob_url
            )

            serializer = AnsPdfSerializer(ans_pdf)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.exception("Unexpected error in AnsPdfUploadView.")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    


# ✅ AnsPdf View (Fixed to GET)

@method_decorator(csrf_exempt, name="dispatch")
class AnsPdfView(APIView):
    def post(self, request):
        try:
            que_pdf_id = request.data.get("id")

            if not que_pdf_id:
                return Response(
                    {"error": "Missing 'id' in request."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            queryset = AnsPdf.objects.filter(que_pdf=que_pdf_id)

            if not queryset.exists():
                return Response(
                    {"message": "No answers found for this question."},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = AnsPdfSerializer(queryset, many=True)
            return Response(
                {"data": serializer.data, "message": "Answers retrieved successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error fetching answer PDFs.")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )