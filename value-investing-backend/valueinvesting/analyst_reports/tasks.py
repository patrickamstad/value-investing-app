import json
import os
import tempfile
from pathlib import Path

from celery import shared_task
from django.conf import settings

from .models import UserUpload
from . import s3_service, mineru_service, llm


@shared_task
def process_uploaded_file(upload_id):
    try:
        upload = UserUpload.objects.get(pk=upload_id)
    except UserUpload.DoesNotExist:
        return  # deleted before the task ran

    if upload.status == UserUpload.Status.DONE:
        return  # redelivered after worker restart — already complete

    upload.status = UserUpload.Status.SCANNING
    upload.save()

    suffix = Path(upload.file_name).suffix
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(tmp_fd)

    try:
        folder = "/".join(upload.s3_key.split("/")[:-1])
        base_name = Path(upload.file_name).stem

        if upload.ocr_s3_key:
            # OCR already succeeded on a previous attempt — reuse the markdown
            s3_service.download_file(upload.ocr_s3_key, tmp_path)
            with open(tmp_path, encoding="utf-8") as f:
                md_content = f.read()
        else:
            # 1. Download file from S3
            s3_service.download_file(upload.s3_key, tmp_path)

            # 2. Extract text via MinerU
            ocr_result = mineru_service.extract(tmp_path)
            md_content = ocr_result["md_content"]

            # 3. Upload extracted markdown to S3
            ocr_s3_key = f"{folder}/mineru/{base_name}.md"
            s3_service.upload_text(md_content, ocr_s3_key)
            upload.ocr_s3_key = ocr_s3_key
            upload.save()

        # 4. Classify document type if not already set by the user
        if not upload.document_type:
            classification = llm.classify(md_content)
            upload.document_type = classification.get("document_type")

        upload.status = UserUpload.Status.DONE
        upload.save()

    except Exception as e:
        try:
            upload.status = UserUpload.Status.FAILED
            upload.error_message = str(e)
            upload.save()
        except Exception:
            pass  # upload was deleted mid-task — nothing to update
        raise

    finally:
        os.unlink(tmp_path)


@shared_task
def generate_analyst_report(report_id):
    from .models import AnalystReport
    from .report_agents.registry import AGENT_REGISTRY
    from .report_agents.final_report import FinalAnalystReportAgent
    from .report_agents.context_bundle import ContextBundle, DocumentContext
    from .pdf_renderer import render_report_to_pdf

    report = AnalystReport.objects.get(pk=report_id)
    report.status = AnalystReport.Status.GENERATING
    report.save()

    try:
        # 1. Fetch all processed uploads for this user + company
        uploads = UserUpload.objects.filter(
            user=report.user,
            qfs_symbol=report.qfs_symbol,
            status=UserUpload.Status.DONE,
        ).exclude(ocr_s3_key__isnull=True).exclude(ocr_s3_key="")

        # 2. Build DocumentContext for each upload (raw markdown only)
        documents = []
        for upload in uploads:
            suffix = Path(upload.file_name).suffix
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(tmp_fd)
            try:
                s3_service.download_file(upload.ocr_s3_key, tmp_path)
                with open(tmp_path, encoding="utf-8") as f:
                    raw_markdown = f.read()
            finally:
                os.unlink(tmp_path)

            documents.append(DocumentContext(
                file_name=upload.file_name,
                document_type=upload.document_type or "other",
                raw_markdown=raw_markdown,
            ))

        # 3. Build context bundle
        bundle = ContextBundle(
            qfs_symbol=report.qfs_symbol_id,
            company_name=report.qfs_symbol_id,
            documents=documents,
            # TODO: wire in financial_metrics, valuation_data, insider_data, shareholder_data
        )

        base_key = f"analyst-reports/{report.qfs_symbol_id}/user_{report.user_id}/report_{report.pk}"

        # 4. Run all registered analysis agents and persist each output
        provider = llm.get_provider(getattr(settings, "LLM_PROVIDER", "gemini"))
        agent_outputs = {}
        for agent_cls in AGENT_REGISTRY:
            agent = agent_cls()
            output = agent.run(bundle, provider)
            agent_outputs[agent.key] = output

            s3_service.upload_text(
                json.dumps(output, indent=2),
                f"{base_key}/agents/{agent.key}.json",
                content_type="application/json",
            )

            map_outputs = getattr(agent, "_map_outputs", None)
            if map_outputs is not None:
                s3_service.upload_text(
                    json.dumps(map_outputs, indent=2),
                    f"{base_key}/agents/{agent.key}_map.json",
                    content_type="application/json",
                )

        # 5. Final report synthesis
        sections = FinalAnalystReportAgent().run(bundle, provider, agent_outputs)

        s3_service.upload_text(
            json.dumps(sections, indent=2),
            f"{base_key}/final_sections.json",
            content_type="application/json",
        )

        # 6. Render to PDF and upload to S3
        pdf_bytes = render_report_to_pdf(sections, company_name=bundle.company_name)
        pdf_s3_key = f"{base_key}/report.pdf"
        s3_service.upload_text(pdf_bytes, pdf_s3_key, content_type="application/pdf")

        # 7. Record which uploads were used and mark done
        report.source_uploads.set(uploads)
        report.pdf_s3_key = pdf_s3_key
        report.status = AnalystReport.Status.DONE
        report.save()

    except Exception:
        report.status = AnalystReport.Status.FAILED
        report.save()
        raise
