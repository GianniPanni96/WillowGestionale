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
if (Test-Path build)        { Remove-Item -Recurse -Force build }
if (Test-Path dist)         { Remove-Item -Recurse -Force dist }
if (Test-Path dist_patches) { Remove-Item -Recurse -Force dist_patches }

Write-Host "==> PyInstaller ($Spec)" -ForegroundColor Cyan
& pyinstaller $Spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller fallito" }

$exeName = "WillowGestionale_$($ver.tag).exe"
$exePath = Join-Path "dist" $exeName
if (-not (Test-Path $exePath)) { throw "Eseguibile atteso non trovato: $exePath" }
$sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "    Prodotto : $exePath ($sizeMb MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Build patch executables
# Cerca tutti i file *.spec dentro Patches\Patch *\ e li builda come exe
# standalone, copiando il risultato nell'installer repo alla stessa sottocartella.
# ---------------------------------------------------------------------------
$installerPatchesRoot = "C:\pythonProject\WillowGestionale_installer\Patches"
$patchSpecFiles = Get-ChildItem -Path "Patches" -Recurse -Filter "*.spec" -File |
    Where-Object { $_.DirectoryName -match "Patch[\s_]+v?\d" }

if ($patchSpecFiles.Count -eq 0) {
    Write-Host "==> Nessuno spec patch trovato in Patches\Patch *\" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "==> Build patch executables ($($patchSpecFiles.Count) spec trovati)" -ForegroundColor Cyan

    foreach ($specFile in $patchSpecFiles) {
        $patchFolderName = $specFile.Directory.Name        # es. "Patch v140"
        $specRelPath     = $specFile.FullName
        $distPatchDir    = Join-Path $repoRoot "dist_patches\$patchFolderName"

        Write-Host ""
        Write-Host "  [$patchFolderName] spec: $($specFile.Name)" -ForegroundColor Cyan
        Write-Host "  [$patchFolderName] output dir: $distPatchDir"

        # Crea la distpath dedicata cosi' gli exe non si mescolano con quelli del gestionale
        New-Item -ItemType Directory -Force -Path $distPatchDir | Out-Null

        Write-Host "  [$patchFolderName] avvio pyinstaller..."
        & pyinstaller $specRelPath --distpath $distPatchDir --workpath (Join-Path $repoRoot "build_patches\$patchFolderName") --noconfirm
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("  [{0}] Build FALLITO per {1} -- continuo con gli altri spec." -f $patchFolderName, $specFile.Name)
            continue
        }

        # Trova l'exe prodotto nella distpath
        $producedExes = Get-ChildItem -Path $distPatchDir -Filter "*.exe" -File
        if ($producedExes.Count -eq 0) {
            Write-Warning "  [$patchFolderName] Nessun exe trovato in $distPatchDir dopo la build."
            continue
        }

        # Destinazione nell'installer
        $destDir = Join-Path $installerPatchesRoot $patchFolderName
        if (-not (Test-Path $destDir)) {
            Write-Host "  [$patchFolderName] Creo cartella destinazione: $destDir"
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }

        foreach ($exeFile in $producedExes) {
            $destPath    = Join-Path $destDir $exeFile.Name
            $patchSizeMb = [math]::Round($exeFile.Length / 1MB, 1)
            Write-Host ("  [{0}] Copio {1} ({2} MB) -> {3}" -f $patchFolderName, $exeFile.Name, $patchSizeMb, $destPath) -ForegroundColor Green
            Copy-Item -Path $exeFile.FullName -Destination $destPath -Force
        }

        Write-Host "  [$patchFolderName] OK" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "==> Build patch executables completato." -ForegroundColor Cyan
}

# Pulizia cartelle temporanee patch
if (Test-Path dist_patches)  { Remove-Item -Recurse -Force dist_patches }
if (Test-Path build_patches) { Remove-Item -Recurse -Force build_patches }

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
