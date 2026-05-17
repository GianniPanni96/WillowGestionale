# release.ps1
#
# Builda l'eseguibile Windows e lo carica nella GitHub Release del tag corrente.
#
# Prerequisiti:
#   - aver fatto `git pull --tags` su master (la versione viene letta dai tag)
#   - HEAD deve essere esattamente su un tag vX.Y.Z (altrimenti il build sara' "dev")
#   - pyinstaller installato nel venv attivo
#   - gh CLI installato e autenticato (`gh auth login`)
#
# Uso:
#   .\release.ps1                  # spec di default: MainQT_noconsole.spec
#   .\release.ps1 -Spec MainQT.spec
#   .\release.ps1 -SkipUpload      # builda ma non carica

[CmdletBinding()]
param(
    [string]$Spec = "MainQT_noconsole.spec",
    [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host "==> Risolvo la versione da git" -ForegroundColor Cyan
$versionJson = & python -c "import json, build_version as bv; v=bv.resolve_version(); print(json.dumps({'semver':v.semver,'short':v.short,'tag':v.file_name_tag,'is_release':v.is_release}))"
if ($LASTEXITCODE -ne 0) { throw "Risoluzione versione fallita" }
$ver = $versionJson | ConvertFrom-Json
Write-Host "    Versione : $($ver.semver)"
Write-Host "    Exe tag  : $($ver.tag)"
Write-Host "    Release  : $($ver.is_release)"

if (-not $ver.is_release) {
    Write-Warning "Stai buildando off-tag: l'exe avra' versione di sviluppo '$($ver.semver)'."
    if (-not $SkipUpload) {
        Write-Warning "Upload disabilitato automaticamente (off-tag). Usa -SkipUpload per silenziare."
        $SkipUpload = $true
    }
}

Write-Host "==> Pulisco build/ e dist/" -ForegroundColor Cyan
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }

Write-Host "==> PyInstaller ($Spec)" -ForegroundColor Cyan
& pyinstaller $Spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller fallito" }

$exeName = "WillowGestionale_$($ver.tag).exe"
$exePath = Join-Path "dist" $exeName
if (-not (Test-Path $exePath)) { throw "Eseguibile atteso non trovato: $exePath" }
$sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "    Prodotto : $exePath ($sizeMb MB)" -ForegroundColor Green

if ($SkipUpload) {
    Write-Host "==> Upload saltato." -ForegroundColor Yellow
    return
}

$tag = "v$($ver.semver)"
Write-Host "==> Upload su GitHub Release $tag" -ForegroundColor Cyan
& gh release view $tag *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Release $tag inesistente: la creo." -ForegroundColor Yellow
    & gh release create $tag --title $tag --notes "Build automatico."
    if ($LASTEXITCODE -ne 0) { throw "Creazione release fallita" }
}
& gh release upload $tag $exePath --clobber
if ($LASTEXITCODE -ne 0) { throw "Upload fallito" }

Write-Host "==> Fatto. $exeName allegato a $tag." -ForegroundColor Green
