from django.urls import path
from . import views

urlpatterns = [
    path("presigned-url/", views.PresignedUploadURLView.as_view()),
    path("confirm/", views.ConfirmUploadView.as_view()),
    path("retry/<int:upload_id>/", views.RetryUploadView.as_view()),
    path("uploads/<int:upload_id>/", views.DeleteUploadView.as_view()),
    path("uploads/<int:upload_id>/document-type/", views.UpdateUploadDocumentTypeView.as_view()),
    path("reports/<int:report_pk>/", views.AnalystReportDetailView.as_view()),
    path("<str:qfs_symbol>/generate/", views.GenerateAnalystReportView.as_view()),
    path("<str:qfs_symbol>/reports/", views.GetAnalystReportView.as_view()),
    path("<str:qfs_symbol>/", views.UserUploadsView.as_view()),
]
