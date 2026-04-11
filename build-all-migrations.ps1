param(
  [string]$MigrationsDir = "supabase/migrations",
  [string]$OutFile = "supabase/all_migrations.sql"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $MigrationsDir)) {
  throw "Migrations directory not found: $MigrationsDir"
}

$allSqlFiles = @(Get-ChildItem -LiteralPath $MigrationsDir -File -Filter "*.sql")

# Standalone bootstrap duplicate of timestamped migrations; including it re-runs RLS/tables at the end
# and can drift from the canonical chain. Keep the file in repo for reference, omit from bundle.
$excludeNames = @(
  "Extraction To Fine-Tuning Data Migration.sql"
)
$files = @($allSqlFiles | Where-Object { $excludeNames -notcontains $_.Name })

if (-not $files -or $files.Count -eq 0) {
  throw "No .sql files found under: $MigrationsDir (after exclusions)"
}

function Get-MigrationSortKey([string]$name) {
  $m = [regex]::Match($name, '^(?<ts>\d{14,})_')
  if ($m.Success) {
    return @{ HasTs = 0; Ts = $m.Groups["ts"].Value; Name = $name }
  }
  return @{ HasTs = 1; Ts = ""; Name = $name }
}

$sorted = $files | Sort-Object `
  @{ Expression = { (Get-MigrationSortKey $_.Name).HasTs } ; Ascending = $true }, `
  @{ Expression = { (Get-MigrationSortKey $_.Name).Ts } ; Ascending = $true }, `
  @{ Expression = { (Get-MigrationSortKey $_.Name).Name } ; Ascending = $true }

$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Path $outDir | Out-Null
}

$header = @"
-- ============================================================================
-- GENERATED FILE - DO NOT EDIT BY HAND
-- ============================================================================
-- Source: $MigrationsDir
-- Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")
--
-- This file is a concatenation of all SQL files in $MigrationsDir.
-- Ordering:
--   1) Files starting with a timestamp prefix like 20260408090000_*.sql (ASC)
--   2) Any remaining *.sql files (ASC by name)
--
-- Notes for Supabase SQL editor:
-- - Run as a single script on a clean public schema (recommended: DROP SCHEMA public CASCADE;
--   then CREATE SCHEMA public; restore USAGE/CREATE grants for postgres, anon, authenticated, service_role).
-- - storage.* objects are not dropped by public reset; migrations use DROP POLICY IF EXISTS on storage.objects
--   where policies are created.
-- - Optional: TRUNCATE supabase_migrations.schema_migrations; if you use Supabase migration history.
-- - Excluded from this bundle (by build script): Extraction To Fine-Tuning Data Migration.sql
--   (duplicate bootstrap; same content is covered by timestamped migrations).
-- - After 20260312210000_role_expansion_signup.sql the bundle inserts COMMIT; so new app_role enum
--   labels are visible (PostgreSQL: new enum values cannot be used in the same transaction as ADD VALUE).
-- - Optional manual seed (NOT in this file): supabase/seed_bootstrap_global_admin.sql
-- ============================================================================

"@

# After these files, emit COMMIT so PostgreSQL can use new enum labels in the rest of the bundle
# (ALTER TYPE ... ADD VALUE is not visible until committed; single SQL-editor paste is one xact otherwise).
$commitAfterMigration = @(
  "20260312210000_role_expansion_signup.sql"
)

$sb = [System.Text.StringBuilder]::new()
[void]$sb.Append($header)

foreach ($f in $sorted) {
  $name = $f.Name
  $full = $f.FullName

  [void]$sb.AppendLine("-- ============================================================================")
  [void]$sb.AppendLine("-- BEGIN MIGRATION: $name")
  [void]$sb.AppendLine("-- ============================================================================")

  $content = Get-Content -LiteralPath $full -Raw

  if ($null -ne $content -and $content.Length -gt 0) {
    [void]$sb.Append($content)
    if (-not $content.EndsWith("`n")) {
      [void]$sb.AppendLine()
    }
  }

  [void]$sb.AppendLine()
  [void]$sb.AppendLine("-- ============================================================================")
  [void]$sb.AppendLine("-- END MIGRATION: $name")
  [void]$sb.AppendLine("-- ============================================================================")
  [void]$sb.AppendLine()

  if ($commitAfterMigration -contains $name) {
    [void]$sb.AppendLine("-- ---------------------------------------------------------------------------")
    [void]$sb.AppendLine("-- BUNDLE ONLY: commit so new app_role enum values are usable in statements below.")
    [void]$sb.AppendLine("-- ---------------------------------------------------------------------------")
    [void]$sb.AppendLine("COMMIT;")
    [void]$sb.AppendLine()
  }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$outPath = if ([System.IO.Path]::IsPathRooted($OutFile)) { $OutFile } else { Join-Path (Get-Location) $OutFile }
[System.IO.File]::WriteAllText($outPath, $sb.ToString(), $utf8NoBom)

Write-Host "Wrote $($sorted.Count) migrations into $OutFile"
