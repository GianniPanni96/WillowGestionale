# release.ps1
#
# Builda il pacchetto di distribuzione completo (gestionale + patch exe +
# installer) e lo carica come ZIP nella GitHub Release del tag corrente.
#
# Output finale:
#   dist/WillowGestionale-vX.Y.Z/
#     installer.exe
#     _internal/
#     WillowGestionale_X_Y.exe
#     Data/
#     Patches/
#       Patch_v030/ ... Patch_v140/
#     README.md
#   dist/WillowGestionale-vX.Y.Z.zip   <- asset caricato su GitHub Release
#
# Prerequisiti:
#   - aver fatto `git pull --tags` su master (la versione viene letta dai tag)
#   - HEAD deve essere esattamente su un tag vX.Y.Z (altrimenti il build sara' "dev")
#   - pyinstaller installato nel venv attivo
#   - gh CLI installato e autenticato (`gh auth login`)
#
# Uso:
#   .\release.ps1                       # spec di default per il gestionale
#   .\release.ps1 -Spec MainQT.spec
#   .\release.ps1 -SkipUpload           # builda ma non carica
#   .\release.ps1 -SkipPatches          # salta build patch exe (utile in test rapidi)

[CmdletBinding()]
param(
    [string]$Spec = "MainQT_noconsole.spec",
    [string]$InstallerSpec = "installer_app.spec",
    [switch]$SkipUpload,
    [switch]$SkipPatches
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
if (Test-Path build)         { Remove-Item -Recurse -Force build }
if (Test-Path dist)          { Remove-Item -Recurse -Force dist }
if (Test-Path dist_patches)  { Remove-Item -Recurse -Force dist_patches }
if (Test-Path build_patches) { Remove-Item -Recurse -Force build_patches }
if (Test-Path build_installer) { Remove-Item -Recurse -Force build_installer }

# ---------------------------------------------------------------------------
# 1) Build gestionale.exe
# ---------------------------------------------------------------------------
Write-Host "==> PyInstaller gestionale ($Spec)" -ForegroundColor Cyan
& pyinstaller $Spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller (gestionale) fallito" }

$exeName = "WillowGestionale_$($ver.tag).exe"
$exePath = Join-Path "dist" $exeName
if (-not (Test-Path $exePath)) { throw "Eseguibile gestionale atteso non trovato: $exePath" }
$sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "    Prodotto : $exePath ($sizeMb MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2) Build patch executables
#    Cerca tutti i file *.spec dentro Patches\Patch *\ e li builda come exe
#    standalone. Il prodotto viene copiato nella stessa sottocartella
#    Patches\Patch_vXXX\ del repo, cosi' poi finisce nel pacchetto.
# ---------------------------------------------------------------------------
if ($SkipPatches) {
    Write-Host "==> Build patch executables saltato (-SkipPatches)" -ForegroundColor Yellow
} else {
    $patchSpecFiles = Get-ChildItem -Path "Patches" -Recurse -Filter "*.spec" -File |
        Where-Object { $_.DirectoryName -match "Patch[\s_]+v?\d" }

    if ($patchSpecFiles.Count -eq 0) {
        Write-Host "==> Nessuno spec patch trovato in Patches\Patch *\" -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "==> Build patch executables ($($patchSpecFiles.Count) spec trovati)" -ForegroundColor Cyan

        foreach ($specFile in $patchSpecFiles) {
            $patchFolderName = $specFile.Directory.Name        # es. "Patch_v140"
            $specRelPath     = $specFile.FullName
            $distPatchDir    = Join-Path $repoRoot "dist_patches\$patchFolderName"

            Write-Host ""
            Write-Host "  [$patchFolderName] spec: $($specFile.Name)" -ForegroundColor Cyan
            Write-Host "  [$patchFolderName] output dir: $distPatchDir"

            New-Item -ItemType Directory -Force -Path $distPatchDir | Out-Null

            Write-Host "  [$patchFolderName] avvio pyinstaller..."
            & pyinstaller $specRelPath --distpath $distPatchDir --workpath (Join-Path $repoRoot "build_patches\$patchFolderName") --noconfirm
            if ($LASTEXITCODE -ne 0) {
                Write-Warning ("  [{0}] Build FALLITO per {1} -- continuo con gli altri spec." -f $patchFolderName, $specFile.Name)
                continue
            }

            $producedExes = Get-ChildItem -Path $distPatchDir -Filter "*.exe" -File
            if ($producedExes.Count -eq 0) {
                Write-Warning "  [$patchFolderName] Nessun exe trovato in $distPatchDir dopo la build."
                continue
            }

            # Copia gli exe prodotti accanto al .py della patch corrispondente.
            $destDir = $specFile.Directory.FullName
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
}

# ---------------------------------------------------------------------------
# 3) Build installer.exe
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "==> PyInstaller installer ($InstallerSpec)" -ForegroundColor Cyan
& pyinstaller $InstallerSpec --noconfirm --workpath (Join-Path $repoRoot "build_installer")
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller (installer) fallito" }

$installerDistDir = Join-Path "dist" "installer"
if (-not (Test-Path $installerDistDir)) { throw "Cartella installer attesa non trovata: $installerDistDir" }
$installerExePath = Join-Path $installerDistDir "installer.exe"
if (-not (Test-Path $installerExePath)) { throw "installer.exe atteso non trovato: $installerExePath" }
Write-Host "    Prodotto : $installerExePath" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4) Assemblaggio pacchetto finale dist/WillowGestionale-vX.Y.Z/
# ---------------------------------------------------------------------------
$packageName = "WillowGestionale-v$($ver.semver)"
$packageRoot = Join-Path "dist" $packageName
Write-Host ""
Write-Host "==> Assemblo pacchetto $packageRoot" -ForegroundColor Cyan

if (Test-Path $packageRoot) { Remove-Item -Recurse -Force $packageRoot }
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

# 4a) installer.exe + _internal/
Write-Host "    Copio installer.exe + _internal/"
Copy-Item -Path (Join-Path $installerDistDir "*") -Destination $packageRoot -Recurse -Force

# 4b) gestionale.exe
Write-Host "    Copio $exeName"
Copy-Item -Path $exePath -Destination $packageRoot -Force

# 4c) Data/
Write-Host "    Copio Data/"
Copy-Item -Path "Data" -Destination $packageRoot -Recurse -Force

# 4d) Patches/ (solo .py e .exe, niente .spec)
Write-Host "    Copio Patches/ (filtrate)"
$patchesDest = Join-Path $packageRoot "Patches"
New-Item -ItemType Directory -Force -Path $patchesDest | Out-Null
foreach ($child in Get-ChildItem -Path "Patches" -Force) {
    if ($child.PSIsContainer) {
        $childDest = Join-Path $patchesDest $child.Name
        New-Item -ItemType Directory -Force -Path $childDest | Out-Null
        Get-ChildItem -Path $child.FullName -File | Where-Object {
            $_.Extension -in '.py', '.exe'
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $childDest -Force
        }
    } elseif ($child.Extension -in '.py', '.exe') {
        Copy-Item -Path $child.FullName -Destination $patchesDest -Force
    }
}

# 4e) README pacchetto (generato da template)
$readmeTemplate = Join-Path $repoRoot "DOCS\installer_README_template.md"
$readmeDest = Join-Path $packageRoot "README.md"
if (Test-Path $readmeTemplate) {
    $readmeContent = (Get-Content -Path $readmeTemplate -Raw) -replace '\{\{VERSION\}\}', $ver.semver
    Set-Content -Path $readmeDest -Value $readmeContent -Encoding UTF8
    Write-Host "    README generato da template"
} else {
    Write-Warning "    Template README non trovato: $readmeTemplate (skippato)"
}

$packageSizeMb = [math]::Round(((Get-ChildItem -Path $packageRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum) / 1MB, 1)
Write-Host "    Pacchetto pronto ($packageSizeMb MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 5) ZIP
# ---------------------------------------------------------------------------
$zipPath = Join-Path "dist" "$packageName.zip"
Write-Host ""
Write-Host "==> Creo ZIP: $zipPath" -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "    ZIP pronto ($zipSizeMb MB)" -ForegroundColor Green

# Pulizia cartelle temporanee installer
if (Test-Path build_installer) { Remove-Item -Recurse -Force build_installer }

# ---------------------------------------------------------------------------
# 6) Upload su GitHub Release
# ---------------------------------------------------------------------------
if ($SkipUpload) {
    Write-Host "==> Upload saltato." -ForegroundColor Yellow
    return
}

$tag = "v$($ver.semver)"
Write-Host ""
Write-Host "==> Upload su GitHub Release $tag" -ForegroundColor Cyan
& gh release view $tag *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Release $tag inesistente: la creo." -ForegroundColor Yellow
    & gh release create $tag --title $tag --notes "Build automatico."
    if ($LASTEXITCODE -ne 0) { throw "Creazione release fallita" }
}
& gh release upload $tag $zipPath --clobber
if ($LASTEXITCODE -ne 0) { throw "Upload ZIP fallito" }

Write-Host "==> Fatto. $packageName.zip allegato a $tag." -ForegroundColor Green
