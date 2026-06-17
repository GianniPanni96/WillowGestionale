from __future__ import annotations

import contextlib
import io
import os
import re
import runpy
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"
INSTALLATION_PATH_ENV_VAR = "GESTIONALE_INSTALLATION_PATH"
PATCH_EXECUTABLE_TIMEOUT_SECONDS = 30 * 60


@dataclass(frozen=True)
class PatchScriptResult:
    patch_version: tuple[int, int, int]
    patch_folder: Path
    script_path: Path
    success: bool
    output: str
    error: str = ""


class patchLauncher:
    """Discovers and runs versioned Python or executable patches."""

    PATCH_DIR_RE = re.compile(r"^Patch[\s_-]+v?([0-9][0-9._-]*)$", re.IGNORECASE)
    VERSION_TOKEN_RE = re.compile(r"v?\d+(?:[._-]?\d+)*", re.IGNORECASE)

    def __init__(self, patches_root: str | Path | None = None, logger=None):
        self.logger = logger
        self.patches_root = Path(patches_root) if patches_root else self._resolve_patches_root()

    @staticmethod
    def _resolve_patches_root() -> Path:
        """Cerca Patches/ accanto a installer.exe (mondo unificato post-migrazione).

        Le patches NON sono bundled in installer.exe: vivono accanto a esso nel
        package di installazione. In modalita' dev (non-frozen) cerca nel repo.
        """
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "Patches")

        candidates.append(Path(__file__).resolve().parent.parent / "Patches")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @classmethod
    def extract_version_token(cls, value: str | Path | None) -> str:
        if value is None:
            return ""
        text = str(value)
        path = Path(text)
        searchable = path.stem if path.suffix.lower() == ".exe" else path.name
        match = cls.VERSION_TOKEN_RE.search(searchable)
        return match.group(0) if match else ""

    @classmethod
    def normalize_version(cls, value: str | Path | tuple[int, ...] | None) -> tuple[int, int, int] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            parts = list(value)
        else:
            token = cls.extract_version_token(value)
            if not token:
                return None
            token = token.lower().lstrip("v").replace("-", ".").replace("_", ".")
            if "." in token:
                parts = [int(p) for p in token.split(".") if p != ""]
            elif len(token) == 3:
                parts = [int(token[0]), int(token[1]), int(token[2])]
            elif len(token) == 2:
                parts = [0, int(token[0]), int(token[1])]
            else:
                parts = [int(token)]

        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    @staticmethod
    def version_to_string(version: tuple[int, int, int] | None) -> str:
        return ".".join(str(part) for part in version) if version is not None else "sconosciuta"

    @classmethod
    def find_existing_executable(cls, install_folder: str | Path) -> Path | None:
        root = Path(install_folder)
        if not root.exists():
            return None

        exes = [p for p in root.glob("*.exe") if p.is_file()]
        if not exes:
            return None

        preferred = [
            p for p in exes
            if "installer" not in p.name.lower()
            and ("willow" in p.name.lower() or "gestionale" in p.name.lower())
        ]
        candidates = preferred or [p for p in exes if "installer" not in p.name.lower()] or exes

        def _sort_key(path: Path):
            version = cls.normalize_version(path.name) or (-1, -1, -1)
            return version, path.stat().st_mtime

        return max(candidates, key=_sort_key)

    def iter_patch_folders(self) -> list[tuple[tuple[int, int, int], Path]]:
        if not self.patches_root.exists():
            return []

        folders = []
        for child in self.patches_root.iterdir():
            if not child.is_dir():
                continue
            match = self.PATCH_DIR_RE.match(child.name)
            if not match:
                continue
            version = self.normalize_version(match.group(1))
            if version is not None:
                folders.append((version, child))
        return sorted(folders, key=lambda item: item[0])

    def required_patch_folders(
        self,
        installed_version: str | tuple[int, int, int] | None,
        target_version: str | tuple[int, int, int] | None,
    ) -> list[tuple[tuple[int, int, int], Path]]:
        installed = self.normalize_version(installed_version)
        target = self.normalize_version(target_version)

        required = []
        for patch_version, folder in self.iter_patch_folders():
            if installed is not None and patch_version <= installed:
                continue
            if target is not None and patch_version > target:
                continue
            required.append((patch_version, folder))
        return required

    def count_required_patches(
        self,
        installed_version: str | tuple[int, int, int] | None,
        target_version: str | tuple[int, int, int] | None = None,
    ) -> int:
        return sum(
            len(self._patch_files_in_folder(folder))
            for _, folder in self.required_patch_folders(installed_version, target_version)
        )

    def launch_required_patches(
        self,
        installed_version: str | tuple[int, int, int] | None,
        target_version: str | tuple[int, int, int] | None,
        install_folder: str | Path,
        data_folder: str | Path,
        step_cb: Callable[[str, bool], None] | None = None,
    ) -> list[PatchScriptResult]:
        os.environ[DB_PATH_ENV_VAR] = str(Path(data_folder).resolve())
        os.environ[INSTALLATION_PATH_ENV_VAR] = str(Path(install_folder).resolve())

        results: list[PatchScriptResult] = []
        folders = self.required_patch_folders(installed_version, target_version)
        if not folders:
            if step_cb:
                step_cb("Nessuna patch richiesta", True)
            return results

        for patch_version, folder in folders:
            patch_files = self._patch_files_in_folder(folder)
            if not patch_files and step_cb:
                step_cb(f"Nessuno script in {folder.name}", True)

            for patch_path in patch_files:
                result = self._run_patch_file(patch_version, folder, patch_path, install_folder, data_folder)
                results.append(result)
                label_version = self.version_to_string(patch_version)
                if step_cb:
                    step_cb(
                        f"Patch v{label_version}: {patch_path.name}",
                        result.success,
                    )
                if self.logger:
                    log_method = self.logger.info if result.success else self.logger.error
                    log_method(
                        "Patch %s/%s success=%s output=%r error=%r",
                        folder.name,
                        patch_path.name,
                        result.success,
                        result.output,
                        result.error,
                    )
                if not result.success:
                    break
            if results and not results[-1].success:
                break

        return results

    @staticmethod
    def _patch_files_in_folder(folder: Path) -> list[Path]:
        supported_suffixes = {".py", ".exe"}
        return sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in supported_suffixes),
            key=lambda path: (path.suffix.lower() != ".py", path.name.lower()),
        )

    def _run_patch_file(
        self,
        patch_version: tuple[int, int, int],
        patch_folder: Path,
        patch_path: Path,
        install_folder: str | Path,
        data_folder: str | Path,
    ) -> PatchScriptResult:
        suffix = patch_path.suffix.lower()
        if suffix == ".py":
            return self._run_python_script(patch_version, patch_folder, patch_path, install_folder)
        if suffix == ".exe":
            return self._run_executable_patch(
                patch_version,
                patch_folder,
                patch_path,
                install_folder,
                data_folder,
            )
        return PatchScriptResult(
            patch_version,
            patch_folder,
            patch_path,
            False,
            "",
            f"Tipo patch non supportato: {patch_path.suffix}",
        )

    def _run_python_script(
        self,
        patch_version: tuple[int, int, int],
        patch_folder: Path,
        script_path: Path,
        install_folder: str | Path,
    ) -> PatchScriptResult:
        stdout = io.StringIO()
        old_argv = sys.argv[:]
        old_path = sys.path[:]
        sys.argv = [str(script_path)]

        import_roots = [
            str(Path(install_folder).resolve()),
            str(self.patches_root.resolve()),
            str(patch_folder.resolve()),
            str(Path(__file__).resolve().parent),
            str(Path(__file__).resolve().parent.parent),
        ]
        for root in reversed(import_roots):
            if root not in sys.path:
                sys.path.insert(0, root)

        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
                runpy.run_path(str(script_path), run_name="__main__")
            return PatchScriptResult(patch_version, patch_folder, script_path, True, stdout.getvalue())
        except SystemExit as exc:
            code = exc.code
            success = code in (0, None)
            error = "" if success else f"SystemExit({code})"
            return PatchScriptResult(
                patch_version,
                patch_folder,
                script_path,
                success,
                stdout.getvalue(),
                error,
            )
        except Exception as exc:
            return PatchScriptResult(
                patch_version,
                patch_folder,
                script_path,
                False,
                stdout.getvalue(),
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
        finally:
            sys.argv = old_argv
            sys.path = old_path

    def _run_executable_patch(
        self,
        patch_version: tuple[int, int, int],
        patch_folder: Path,
        executable_path: Path,
        install_folder: str | Path,
        data_folder: str | Path,
    ) -> PatchScriptResult:
        env = os.environ.copy()
        env[DB_PATH_ENV_VAR] = str(Path(data_folder).resolve())
        env[INSTALLATION_PATH_ENV_VAR] = str(Path(install_folder).resolve())

        try:
            result = subprocess.run(
                [str(executable_path)],
                cwd=str(patch_folder),
                env=env,
                capture_output=True,
                text=True,
                timeout=PATCH_EXECUTABLE_TIMEOUT_SECONDS,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            if result.returncode == 0:
                return PatchScriptResult(patch_version, patch_folder, executable_path, True, output)
            return PatchScriptResult(
                patch_version,
                patch_folder,
                executable_path,
                False,
                output,
                f"Exit code {result.returncode}",
            )
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(part for part in (exc.stdout or "", exc.stderr or "") if part)
            return PatchScriptResult(
                patch_version,
                patch_folder,
                executable_path,
                False,
                output,
                f"Timeout dopo {PATCH_EXECUTABLE_TIMEOUT_SECONDS} secondi",
            )
        except Exception as exc:
            return PatchScriptResult(
                patch_version,
                patch_folder,
                executable_path,
                False,
                "",
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
