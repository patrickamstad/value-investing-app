import boto3
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from quickfs_dj.models import TradedCompanies
from .models import UserUpload, AnalystReport
from .serializers import UserUploadSerializer, AnalystReportSerializer
from .tasks import process_uploaded_file, generate_analyst_report


class PresignedUploadURLView(APIView):
    def post(self, request):
        qfs_symbol = request.data.get("qfs_symbol")
        file_name = request.data.get("file_name")
        file_type = request.data.get("file_type")

        s3_key = f"user-uploads/{qfs_symbol}/user_{request.user.id}/{file_name}"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": s3_key,
                "ContentType": file_type,
            },
            ExpiresIn=300,
        )

        return Response({"presigned_url": presigned_url, "s3_key": s3_key})


class ConfirmUploadView(APIView):
    def post(self, request):
        qfs_symbol = request.data.get("qfs_symbol")
        s3_key = request.data.get("s3_key")
        file_name = request.data.get("file_name")
        file_type = request.data.get("file_type")
        document_type = request.data.get("document_type") or None

        if document_type and document_type not in UserUpload.DocumentType.values:
            return Response({"error": "Invalid document_type."}, status=status.HTTP_400_BAD_REQUEST)

        company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)

        upload = UserUpload.objects.create(
            user=request.user,
            qfs_symbol=company,
            s3_key=s3_key,
            file_name=file_name,
            file_type=file_type,
            document_type=document_type,
        )

        process_uploaded_file.delay(upload.pk)

        serializer = UserUploadSerializer(upload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserUploadsView(APIView):
    def get(self, request, qfs_symbol):
        uploads = UserUpload.objects.filter(
            user=request.user,
            qfs_symbol__qfs_symbol=qfs_symbol,
        )
        serializer = UserUploadSerializer(uploads, many=True)
        return Response(serializer.data)


class RetryUploadView(APIView):
    def post(self, request, upload_id):
        try:
            upload = UserUpload.objects.get(pk=upload_id, user=request.user)
        except UserUpload.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if upload.status != UserUpload.Status.FAILED:
            return Response({"error": "File is not in failed state."}, status=status.HTTP_400_BAD_REQUEST)

        if upload.retry_count >= 3:
            return Response({"error": "Max retries reached."}, status=status.HTTP_400_BAD_REQUEST)

        upload.retry_count += 1
        upload.status = UserUpload.Status.UPLOADED
        upload.error_message = None
        upload.save()

        process_uploaded_file.delay(upload.pk)

        serializer = UserUploadSerializer(upload)
        return Response(serializer.data)


class GenerateAnalystReportView(APIView):
    def post(self, request, qfs_symbol):
        company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)

        # check if there is already an analyst report in progress
        in_flight = AnalystReport.objects.filter(
            user=request.user,
            qfs_symbol=company,
            status__in=[AnalystReport.Status.PENDING, AnalystReport.Status.GENERATING],
        ).exists()
        if in_flight:
            return Response(
                {"detail": "A report is already being generated for this company."},
                status=status.HTTP_409_CONFLICT,
            )

        report = AnalystReport.objects.create(user=request.user, qfs_symbol=company)
        
        # hand off report generation to celery queue
        generate_analyst_report.delay(report.pk)
        return Response(AnalystReportSerializer(report).data, status=status.HTTP_202_ACCEPTED)


class GetAnalystReportView(APIView):
    def get(self, request, qfs_symbol):
        reports = AnalystReport.objects.filter(
            user=request.user,
            qfs_symbol__qfs_symbol=qfs_symbol,
        )
        return Response(AnalystReportSerializer(reports, many=True).data)


class DeleteUploadView(APIView):
    def delete(self, request, upload_id):
        try:
            upload = UserUpload.objects.get(pk=upload_id, user=request.user)
        except UserUpload.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        report_in_flight = AnalystReport.objects.filter(
            user=request.user,
            status__in=[AnalystReport.Status.PENDING, AnalystReport.Status.GENERATING],
            source_uploads=upload,
        ).exists()
        if report_in_flight:
            return Response(
                {"detail": "Cannot delete a file while an analyst report using it is being generated."},
                status=status.HTTP_409_CONFLICT,
            )

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        keys_to_delete = [k for k in [upload.s3_key, upload.ocr_s3_key, upload.llm_s3_key] if k]
        if keys_to_delete:
            s3_client.delete_objects(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Delete={"Objects": [{"Key": k} for k in keys_to_delete]},
            )

        upload.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnalystReportDetailView(APIView):
    def get(self, request, report_pk):
        try:
            report = AnalystReport.objects.get(pk=report_pk, user=request.user)
        except AnalystReport.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AnalystReportSerializer(report).data)


class UpdateUploadDocumentTypeView(APIView):
    def patch(self, request, upload_id):
        try:
            upload = UserUpload.objects.get(pk=upload_id, user=request.user)
        except UserUpload.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        document_type = request.data.get("document_type")
        if not document_type:
            return Response({"error": "document_type is required."}, status=status.HTTP_400_BAD_REQUEST)
        if document_type not in UserUpload.DocumentType.values:
            return Response({"error": "Invalid document_type."}, status=status.HTTP_400_BAD_REQUEST)

        upload.document_type = document_type
        upload.save(update_fields=["document_type"])

        return Response(UserUploadSerializer(upload).data)
