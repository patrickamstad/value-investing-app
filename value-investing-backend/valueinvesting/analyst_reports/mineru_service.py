import asyncio
from pathlib import Path

import httpx
from django.conf import settings


def _headers() -> dict:
    return {
        "Modal-Key": settings.MODAL_KEY,
        "Modal-Secret": settings.MODAL_SECRET,
    }


# Uploading a large PDF can be slow — give write/read plenty of room.
_UPLOAD_TIMEOUT = httpx.Timeout(
    connect=30,   # TCP handshake
    write=120,    # time to finish sending the PDF body
    read=600,     # time to receive the server's response (accounts for Modal cold start + processing)
    pool=10,      # time to acquire a connection from the pool
)

# Result payload can be large (full markdown + JSON) — long read, tiny write.
_RESULT_TIMEOUT = httpx.Timeout(connect=30, write=10, read=600, pool=10)


async def _submit_task(tmp_path: str) -> str:
    async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT, follow_redirects=True) as client:
        response = await client.post(
            f"{settings.MINERU_API_URL}/tasks",
            headers=_headers(),
            files={"files": (Path(tmp_path).name, open(tmp_path, "rb"), "application/octet-stream")},
            data={
                "return_md": "true",
                "return_middle_json": "true",
                "backend": "vlm-auto-engine",
                "table_enable": "true",
                "image_analysis": "true",
                "return_model_output": "true",
                "return_content_list": "true",
            },
        )
    response.raise_for_status()
    return response.json()["task_id"]


_MAX_NOT_FOUND_RETRIES = 10


async def _poll_until_done(task_id: str) -> None:
    not_found_attempts = 0
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            response = await client.get(
                f"{settings.MINERU_API_URL}/tasks/{task_id}",
                headers=_headers(),
            )
            if response.status_code == 404:
                not_found_attempts += 1
                if not_found_attempts >= _MAX_NOT_FOUND_RETRIES:
                    raise RuntimeError(f"MinerU task {task_id} not found after {_MAX_NOT_FOUND_RETRIES} retries")
                await asyncio.sleep(2)
                continue
            response.raise_for_status()
            status = response.json()["status"]

            if status == "completed":
                return
            if status == "failed":
                raise RuntimeError(f"MinerU task failed: {task_id}")

            await asyncio.sleep(2)


async def _fetch_result(task_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_RESULT_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(
            f"{settings.MINERU_API_URL}/tasks/{task_id}/result",
            headers=_headers(),
        )
    response.raise_for_status()
    raw = response.json()
    return next(iter(raw["results"].values()))


async def _extract(tmp_path: str) -> dict:
    task_id = await _submit_task(tmp_path)
    await _poll_until_done(task_id)
    return await _fetch_result(task_id)


def extract(tmp_path: str) -> dict:
    """Synchronous entry point — bridges Celery (sync) to async httpx calls."""
    return asyncio.run(_extract(tmp_path))
