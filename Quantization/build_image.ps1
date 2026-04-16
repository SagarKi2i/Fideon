# ============================================================================
# build_image.ps1  —  Build the neura-quantize Docker image (ONE TIME ONLY)
# Run from the project root:  .\Quantization\build_image.ps1
# Takes ~15-20 min the first time, then never again.
# ============================================================================

Write-Host "Building neura-quantize image (this is a one-time ~15 min build)..." -ForegroundColor Cyan
Write-Host "After this, each pipeline run takes only ~1-2 minutes." -ForegroundColor Green

docker build `
    -f Quantization/Dockerfile.quantize `
    -t neura-quantize `
    .

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Image built successfully!" -ForegroundColor Green
    Write-Host "Now run the pipeline with:  .\Quantization\run.ps1" -ForegroundColor Cyan
} else {
    Write-Host "Build failed. Make sure Docker Desktop is running." -ForegroundColor Red
}
