from rest_framework.response import Response
from .models import CourseList, QuePdf, AnsPdf, Subject
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from .serializers import CourseListSerializer, QuePdfSerializer, AnsPdfSerializer, SubjectSerializer
from rest_framework import status
import os
from django.utils.decorators import method_decorator
from vercel_blob import put
from rest_framework.parsers import MultiPartParser, FormParser
from dotenv import load_dotenv
from .models import get_current_date, get_current_time
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from user.utils import user_key
from user.authentication import CookieJWTAuthentication

load_dotenv()

@method_decorator(csrf_exempt, name="dispatch")
class CoursesView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Narrow fields to those serialized for list; adjust as serializer needs [web:27]
            course_lists = CourseList.objects.all()
            if not course_lists.exists():
                return Response({'message': 'No course lists found.'}, status=404)
            serializer = CourseListSerializer(course_lists, many=True)
            return Response({'CourseList': serializer.data}, status=200)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name="dispatch")
class QuePdfView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            queryset = QuePdf.objects.all()
            serializer = QuePdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name="dispatch")
class QuePdfSubView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            sub = request.data.get("sub")
            course_name = request.data.get("course_name")

            # Single fetch using only fields needed [web:27]
            course = CourseList.objects.only('id', 'name').filter(name=course_name).first()
            if not course:
                return Response({"error": "Invalid course name"}, status=status.HTTP_400_BAD_REQUEST)

            # Filter with explicit fields; .all() redundant after filter [web:27]
            queryset = QuePdf.objects.filter(sub=sub, course_id=course.id)
            serializer = QuePdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name="dispatch")
class QuePdfGetSubView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            course_name = request.data.get("course_name")
            sem = request.data.get("sem")
            # Filter with join by name; distinct preserved as in original [web:27]
            queryset = Subject.objects.filter(course_obj__name=course_name, sem=sem).distinct()
            serializer = SubjectSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class AnsPdfUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            name = user.username
            content = request.data.get("content")
            file = request.FILES.get("pdf")
            qid = request.data.get("id")

            if not file:
                return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            # Minimal fetch of QuePdf to ensure FK valid [web:27]
            que_pdf_obj = QuePdf.objects.only('id').get(id=qid)

            token = os.getenv("BLOB_READ_WRITE_TOKEN")
            if not token:
                return Response(
                    {"error": "Vercel Blob token is missing. Please check your environment variables."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            try:
                blob = put(f"AnsPdf/{file.name}", file.read())
            except Exception as upload_error:
                return Response({"error": f"Upload failed: {str(upload_error)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            ans_pdf = AnsPdf.objects.create(que_pdf=que_pdf_obj, name=name, contant=content, pdf=blob["url"])

            cache.delete(user_key(user))
            serializer = AnsPdfSerializer(ans_pdf)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except QuePdf.DoesNotExist:
            return Response({"error": "Invalid question reference"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name="dispatch")
class AnsPdfView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            qid = request.data.get("id")
            # Narrow query to FK filter; serializer controls fields [web:27]
            queryset = AnsPdf.objects.filter(que_pdf=qid).select_related('que_pdf')
            serializer = AnsPdfSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class QuePdfAddView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            name = request.data.get("name")
            sub = request.data.get("sub")
            choose = request.data.get("choose")
            sem = request.data.get("sem")
            pdf = request.FILES.get("pdf")
            course_id = request.data.get("course_id", 1)
            username = request.user.username

            # Upload PDF to blob storage (same logic) [web:27]
            try:
                blob = put(f"QuePdf/{choose}/sem {sem}/{pdf.name}", pdf.read(),options={'allowOverwrite': True})
            except Exception as upload_error:
                return Response({"error": f"Upload failed: {str(upload_error)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                "username": username
            })

            # Invalidate user cache key as before [web:27]
            cache.delete(user_key(request.user))

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
