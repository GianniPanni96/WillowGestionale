"""
Risolve la versione del prodotto dai tag git e prepara i metadati per PyInstaller.

Esposto tramite due funzioni pubbliche usate dai file .spec:

- resolve_version()      -> oggetto VersionInfo con la versione corrente
- write_version_file()   -> scrive version_info.txt nel formato VSVersionInfo
                            (richiesto da PyInstaller per popolare i dettagli file di Windows)

Logica di risoluzione (in ordine):
  1. variabile d'ambiente WILLOW_VERSION (override esplicito per la CI)
  2. `git describe --tags --long --always --dirty`
     - se HEAD e' esattamente su un tag pulito  -> "1.3.0"
     - altrimenti                               -> "1.3.0+dev.5.gabc1234[.dirty]"
  3. fallback "0.0.0+unknown" (repo senza tag o git assente)

Il SHA e il suffisso "+dev..." NON vengono inseriti nei metadati Windows
(che richiedono solo 4 interi MAJOR.MINOR.PATCH.BUILD); ci finisce solo
"FileVersion"/"ProductVersion" come stringa, dove vale tutto.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_DESCRIBE_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<distance>\d+)-g(?P<sha>[0-9a-f]+))?"
    r"(?P<dirty>-dirty)?$"
)


@dataclass(frozen=True)
class VersionInfo:
    major: int
    minor: int
    patch: int
    distance: int           # numero di commit oltre il tag (0 se HEAD == tag)
    sha: str                # short SHA, "" se HEAD == tag
    dirty: bool             # working tree modificato

    @property
    def is_release(self) -> bool:
        return self.distance == 0 and not self.dirty

    @property
    def semver(self) -> str:
        """Versione stringa completa (usata in ProductVersion stringa e nel CHANGELOG)."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.is_release:
            return base
        suffix = f"+dev.{self.distance}.g{self.sha}" if self.sha else "+dev"
        if self.dirty:
            suffix += ".dirty"
        return base + suffix

    @property
    def short(self) -> str:
        """Versione troncata MAJOR.MINOR per il nome file (es. '1.3')."""
        return f"{self.major}.{self.minor}"

    @property
    def file_name_tag(self) -> str:
        """Suffisso usato nel nome dell'eseguibile (es. '1_3' su Windows-safe)."""
        return f"{self.major}_{self.minor}"

    @property
    def windows_tuple(self) -> tuple[int, int, int, int]:
        """Tupla 4-int richiesta dai campi numerici di VSVersionInfo."""
        return (self.major, self.minor, self.patch, self.distance)


def _run_git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _from_env() -> VersionInfo | None:
    raw = os.environ.get("WILLOW_VERSION")
    if not raw:
        return None
    m = _TAG_RE.match(raw.strip())
    if not m:
        return None
    return VersionInfo(int(m[1]), int(m[2]), int(m[3]), 0, "", False)


def _from_git() -> VersionInfo | None:
    describe = _run_git("describe", "--tags", "--long", "--always", "--dirty", "--match", "v*")
    if not describe:
        return None
    m = _DESCRIBE_RE.match(describe)
    if not m:
        return None
    return VersionInfo(
        major=int(m["major"]),
        minor=int(m["minor"]),
        patch=int(m["patch"]),
        distance=int(m["distance"] or 0),
        sha=m["sha"] or "",
        dirty=bool(m["dirty"]),
    )


def resolve_version() -> VersionInfo:
    return _from_env() or _from_git() or VersionInfo(0, 0, 0, 0, "", False)


_VERSION_FILE_TEMPLATE = """\
# Generato automaticamente da build_version.py - non modificare a mano.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vers},
    prodvers={vers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Willow'),
          StringStruct(u'FileDescription', u'Willow Gestionale'),
          StringStruct(u'FileVersion', u'{semver}'),
          StringStruct(u'InternalName', u'WillowGestionale'),
          StringStruct(u'OriginalFilename', u'WillowGestionale_{short}.exe'),
          StringStruct(u'ProductName', u'Willow Gestionale'),
          StringStruct(u'ProductVersion', u'{semver}'),
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def write_version_file(info: VersionInfo | None = None, dest: Path | None = None) -> Path:
    info = info or resolve_version()
    dest = dest or (_PROJECT_ROOT / "version_info.txt")
    dest.write_text(
        _VERSION_FILE_TEMPLATE.format(
            vers=info.windows_tuple,
            semver=info.semver,
            short=info.file_name_tag,
        ),
        encoding="utf-8",
    )
    return dest


if __name__ == "__main__":
    v = resolve_version()
    path = write_version_file(v)
    print(f"Version: {v.semver}")
    print(f"Exe tag: {v.file_name_tag}  (short {v.short})")
    print(f"Wrote:   {path}")
