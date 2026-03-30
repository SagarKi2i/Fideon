This directory is reserved for:

- Base model checkpoints (references only, not necessarily stored here in full).
- LoRA / QLoRA adapters under `adapters/`.
- Quantized GGUF artifacts or symlinks for deployment.

In a production setup, this folder would be backed by an object store
or model registry, with only lightweight pointers checked into Git.

