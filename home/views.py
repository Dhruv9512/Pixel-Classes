from rest_framework.response import Response

import user
from .models import CourseList, QuePdf, AnsPdf , Subject
from user.models import User
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer, QuePdfSerializer, AnsPdfSerializer , SubjectSerializer
from rest_framework import status
import os
from django.utils.decorators import method_decorator
from vercel_blob import put
from rest_framework.parsers import MultiPartParser, FormParser
from dotenv import load_dotenv
from .models import get_current_date, get_current_time
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from user.utils import user_key   # or any key function you are using

# Load environment variables
load_dotenv()

# ✅ Course List View
@method_decorator(csrf_exempt, name="dispatch")
class CoursesView(APIView):
    def get(self, request):
        try:
            course_lists = CourseList.objects.all()
            if not course_lists:
                return Response({'message': 'No course lists found.'}, status=404)

            serializer = CourseListSerializer(course_lists, many=True)
            return Response({'CourseList': serializer.data}, status=200)

        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ✅ QuePdf View (Fixed to GET)
@method_decorator(csrf_exempt, name="dispatch")
class QuePdfView(APIView):
    def get(self, request):
        try:
            queryset = QuePdf.objects.all()
            serializer = QuePdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# QuePdf View Subject vise
@method_decorator(csrf_exempt, name="dispatch")
class QuePdfSubView(APIView):
    def post(self, request):
        try:
            sub = request.data.get("sub")
            course_name = request.data.get("course_name")  

            # Extract course_id from CourseList model
            course = CourseList.objects.filter(name=course_name).first()
            if not course:
                return Response({"error": "Invalid course name"}, status=status.HTTP_400_BAD_REQUEST)

            course_id = course.id  

            # Filter using both sub and course_id
            queryset = QuePdf.objects.filter(sub=sub, course_id=course_id).all()  
            serializer = QuePdfSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Get all subject
@method_decorator(csrf_exempt, name="dispatch")
class QuePdfGetSubView(APIView):
    def post(self, request):
        try:
            course_name = request.data.get("course_name")  
            sem = request.data.get("sem")
            
            # Extrsct Subject sub from QuePdf model as par course_name and sem
            queryset = Subject.objects.filter(course_obj__name=course_name , sem=sem).distinct()
            serializer = SubjectSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# ✅ AnsPdf Upload View (File Upload Handling)
load_dotenv()

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class AnsPdfUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)  # Ensure file handling support

    def post(self, request):
        try:
            print("\n🔍 Debugging: Received POST request")

            # ✅ Extract Data from Request
            name = request.data.get("name")
            content = request.data.get("content")
            file = request.FILES.get("pdf")  # Get the uploaded file
            id = request.data.get("id")
            que_pdf_id = QuePdf.objects.get(id=id)
            # Debugging logs for input data
            print(f"📌 Name: {name}")
            print(f"📌 Content: {content}")

            if not file:
                print("❌ No file uploaded!")
                return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            print(f"✅ File received: {file.name} ({file.size} bytes)")

            # ✅ Get Vercel Blob Token
            token = os.getenv("BLOB_READ_WRITE_TOKEN")
            print(f"BLOB_TOKEN: {os.getenv('BLOB_READ_WRITE_TOKEN')}")
            if not token:
                print("❌ ERROR: Vercel Blob token is missing!")
                return Response(
                    {"error": "Vercel Blob token is missing. Please check your environment variables."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            print("🔄 Uploading file to Vercel Blob...")

            # ✅ Upload to Vercel Blob
            try:
                blob = put(f"AnsPdf/{file.name}", file.read())
                print(f"✅ File uploaded successfully: {blob["url"]}")
            except Exception as upload_error:
                print(f"❌ Upload error: {upload_error}")
                return Response({"error": f"Upload failed: {str(upload_error)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ✅ Save to Database
            ans_pdf = AnsPdf.objects.create(que_pdf=que_pdf_id, name=name, contant=content, pdf=blob["url"])
            print("✅ File record saved in the database!")

           
            user = User.objects.get(username=name)
            cache.delete(user_key(user))
            serializer = AnsPdfSerializer(ans_pdf)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"❌ General Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ AnsPdf View (Fixed to GET)
@method_decorator(csrf_exempt, name="dispatch")
class AnsPdfView(APIView):
    def post(self, request):
        try:
            id = request.data.get("id")
            queryset = AnsPdf.objects.filter(que_pdf=id)
            serializer = AnsPdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Adding in que pdf table

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class QuePdfAddView(APIView):
    def post(self, request):
        try:
            name = request.data.get("name")
            sub = request.data.get("sub")
            choose = request.data.get("choose")
            sem = request.data.get("sem") 
            pdf = request.FILES.get("pdf")
            course_id = request.data.get("course_id", 1)  
            # Upload PDF to blob storage
            try:
                blob = put(f"QuePdf/{choose}/sem {sem}/{pdf.name}", pdf.read())
                print(f"✅ File uploaded successfully: {blob['url']}")
            except Exception as upload_error:
                print(f"❌ Upload error: {upload_error}")
                return Response(
                    {"error": f"Upload failed: {str(upload_error)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            serializer = QuePdfSerializer(data={
                "name": name,
                "sub": sub,
                "choose": choose,
                "sem": sem,
                "pdf": blob["url"],
                "dateCreated": get_current_date(),
                "timeCreated": get_current_time(),
                "year": 2025,
                "div": "all",
                "course": course_id,  
            })

            username = request.data.get('username')
            user = User.objects.get(username=username)
            cache.delete(user_key(user))
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

# Delete expire cached data
@method_decorator(csrf_exempt, name="dispatch")
class CacheCleanupView(APIView):
    def post(self, request):
        from django.core.cache import cache
        cache.clear_expired()
        return Response({"status": "Cache cleanup task started"}, status=status.HTTP_202_ACCEPTED)