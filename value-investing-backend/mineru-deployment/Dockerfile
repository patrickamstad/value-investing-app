# Use the official vllm image for gpu with Volta、Turing、Ampere、Ada Lovelace、Hopper、Blackwell architecture (7.0 <= Compute Capability <= 12.0)
# Compute Capability version query (https://developer.nvidia.com/cuda-gpus)
# support x86_64 architecture and ARM(AArch64) architecture
FROM vllm/vllm-openai:v0.11.2

# Install libgl for opencv support & Noto fonts for Chinese characters
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libgl1 && \
    fc-cache -fv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install mineru latest
# Note: pip cache purge removed — Modal disables pip cache during builds
RUN python3 -m pip install -U 'mineru[core]>=3.0.0' --break-system-packages

# temporary: find the exact path of the file we want to patch
RUN python3 -c "import mineru.backend.pipeline.pipeline_middle_json_mkcontent as m; import inspect; print(inspect.getfile(m))"

# Patch: inject page markers into markdown output - purpose of patch is to insert page numbers in markdown - this is useful for LLM to reference the source where it found the information
COPY pipeline_middle_json_mkcontent.py \
     /usr/local/lib/python3.12/dist-packages/mineru/backend/pipeline/pipeline_middle_json_mkcontent.py

COPY vlm_middle_json_mkcontent.py \
     /usr/local/lib/python3.12/dist-packages/mineru/backend/vlm/vlm_middle_json_mkcontent.py

# Download models and update the configuration file
RUN /bin/bash -c "mineru-models-download -s huggingface -m all"

# Set the entry point to activate the virtual environment and run the command line tool
ENTRYPOINT ["/bin/bash", "-c", "export MINERU_MODEL_SOURCE=local && exec \"$@\"", "--"]