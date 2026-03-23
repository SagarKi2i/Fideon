param(
  [string]$InputPath = "../frontend/src/assets/fideon-logo.png",
  [string]$OutputPath = "./build/icon-256.png",
  [int]$Size = 256
)

$ErrorActionPreference = "Stop"

$resolvedInput = Resolve-Path -Path $InputPath
$resolvedOutputDir = Split-Path -Parent $OutputPath

if (!(Test-Path $resolvedOutputDir)) {
  New-Item -ItemType Directory -Path $resolvedOutputDir | Out-Null
}

Add-Type -AssemblyName System.Drawing

$src = [System.Drawing.Image]::FromFile($resolvedInput.Path)
try {
  $dst = New-Object System.Drawing.Bitmap($Size, $Size)
  $g = [System.Drawing.Graphics]::FromImage($dst)
  try {
    $g.Clear([System.Drawing.Color]::Transparent)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

    # Keep aspect ratio, center in a square canvas.
    $scale = [Math]::Min($Size / $src.Width, $Size / $src.Height)
    $newW = [int]([Math]::Round($src.Width * $scale))
    $newH = [int]([Math]::Round($src.Height * $scale))
    $x = [int]([Math]::Floor(($Size - $newW) / 2))
    $y = [int]([Math]::Floor(($Size - $newH) / 2))

    $g.DrawImage($src, $x, $y, $newW, $newH)
  } finally {
    $g.Dispose()
  }

  $dst.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
  $src.Dispose()
}

Write-Host "Generated icon: $OutputPath ($Size x $Size)"

