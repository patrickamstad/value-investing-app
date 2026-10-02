import subprocess
import modal

image = modal.Image.from_dockerfile("Dockerfile", add_python="3.12").env({"KEEP_PARATEXT": "1"})

app = modal.App("mineru")


@app.function(
    gpu="A10G",
    memory=32768,
    image=image,
    timeout=600,
    scaledown_window=300,
    max_containers=1,
)
# @modal.web_server(port=8000, startup_timeout=300, requires_proxy_auth=True)
@modal.web_server(port=8000, startup_timeout=300)
def mineru_api():
    subprocess.Popen(["mineru-api", "--host", "0.0.0.0", "--port", "8000"])
