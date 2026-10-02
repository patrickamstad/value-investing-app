from rest_framework import serializers
from .models import UserUpload, AnalystReport
from . import s3_service


class UserUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserUpload
        fields = ["id", "s3_key", "file_name", "file_type", "uploaded_at", "status", "ocr_s3_key", "retry_count", "error_message", "document_type"]
        read_only_fields = ["id", "uploaded_at", "status", "ocr_s3_key", "retry_count", "error_message"]


class AnalystReportSerializer(serializers.ModelSerializer):
    source_upload_ids = serializers.SerializerMethodField()
    presigned_url     = serializers.SerializerMethodField()

    class Meta:
        model  = AnalystReport
        fields = ["id", "status", "created_at", "source_upload_ids", "presigned_url"]

    def get_source_upload_ids(self, obj):
        return list(obj.source_uploads.values_list("id", flat=True))

    def get_presigned_url(self, obj):
        if obj.status == AnalystReport.Status.DONE and obj.pdf_s3_key:
            return s3_service.generate_presigned_get_url(obj.pdf_s3_key, expiry=3600)
        return None
