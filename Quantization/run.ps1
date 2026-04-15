# ============================================================================
# run.ps1  —  Run the quantization pipeline using the pre-built image
# Run from the project root:  .\Quantization\run.ps1
#
# First run:  downloads TinyLlama + creates adapter + quantizes (~5 min)
# Later runs: skips everything already done — just uploads (~1-2 min)
#
# Named volumes used (persist between runs):
#   neura_workspace  — base model, adapter, GGUF files
# ============================================================================

param(
    [switch]$ForceReQuantize  # Pass -ForceReQuantize to delete GGUFs and re-run quantization
)

# Check Docker is running
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check image exists
$image = docker images -q neura-quantize 2>$null
if (-not $image) {
    Write-Host "ERROR: neura-quantize image not found." -ForegroundColor Red
    Write-Host "Build it first with:  .\Quantization\build_image.ps1" -ForegroundColor Cyan
    exit 1
}

if ($ForceReQuantize) {
    Write-Host "ForceReQuantize: removing existing GGUF artifacts..." -ForegroundColor Yellow
    docker run --rm -v "neura_workspace:/workspace" alpine sh -c `
        "rm -f /workspace/gguf_output/*.gguf /workspace/gguf_output/*.sig /workspace/gguf_output/manifest.json"
    Write-Host "Artifacts cleared. Pipeline will re-quantize." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting pipeline (skips already-completed steps)..." -ForegroundColor Cyan

docker run --rm -it `
    -v "${PWD}/Quantization:/app" `
    -v "neura_workspace:/workspace" `
    neura-quantize `
    bash /app/run_pipeline_docker.sh

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Pipeline complete!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Pipeline failed. Check output above." -ForegroundColor Red
}
