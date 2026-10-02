from django.db import models
from django.conf import settings
from quickfs_dj.models import TradedCompanies


class UserUpload(models.Model):

    class DocumentType(models.TextChoices):
        ANNUAL_REPORT         = "annual_report",         "Annual Report"
        QUARTERLY_REPORT      = "quarterly_report",      "Quarterly Report"
        EARNINGS_CALL         = "earnings_call",         "Earnings Call"
        INVESTOR_PRESENTATION = "investor_presentation", "Investor Presentation"
        ANALYST_REPORT        = "analyst_report",        "Analyst Report"
        NEWS_ARTICLE          = "news_article",          "News Article"
        OTHER                 = "other",                 "Other"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        SCANNING = "scanning", "Scanning Document"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field="qfs_symbol", on_delete=models.CASCADE, db_column="qfs_symbol")
    s3_key = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.UPLOADED)
    ocr_s3_key = models.CharField(max_length=500, null=True, blank=True)
    retry_count   = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    document_type = models.CharField(
        max_length=50, choices=DocumentType.choices, null=True, blank=True
    )

    class Meta:
        unique_together = ("user", "s3_key")


class AnalystReport(models.Model):

    class Status(models.TextChoices):
        PENDING    = "pending",    "Pending"
        GENERATING = "generating", "Generating"
        DONE       = "done",       "Done"
        FAILED     = "failed",     "Failed"

    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    qfs_symbol     = models.ForeignKey(
        TradedCompanies, to_field="qfs_symbol", on_delete=models.CASCADE, db_column="qfs_symbol"
    )
    status         = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    pdf_s3_key     = models.CharField(max_length=500, null=True, blank=True)
    source_uploads = models.ManyToManyField("UserUpload", blank=True, related_name="analyst_reports")
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
