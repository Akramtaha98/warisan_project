# Superseded guides

These are the original faculty deployment PDFs, kept as a record of how the
project was first deployed. **They are no longer accurate — follow
`README_DEPLOY.md` in the repository root instead.**

Known errors in these PDFs:

- `Faculty_Shared_Docker_Deployment_BEGINNER.pdf` describes the NVIDIA / RTX 5090 /
  LM Studio architecture, which was entirely replaced by AMD / llama.cpp / Vulkan.
- Both PDFs' **Checkpoint G** tells you to grep the `llm` logs for
  `ggml_vulkan: Found 1 Vulkan devices`. Recent llama.cpp builds no longer print
  that banner, so following this reports a GPU failure on a working machine.
  Use `llama-server --list-devices` instead.
- They state the GPU appears as `RADV GFX1151`. Current Mesa reports this chip as
  `RADV STRIX_HALO`.
