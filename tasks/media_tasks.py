"""
Media Tasks Pipeline - pobieranie i konwersja mediów.

FILOZOFIA:
- Jawne kroki, zero magii
- Walidacja środowiska PRZED wykonaniem
- Cleanup tylko po sukcesie
- Raportowanie konkretne, bez gadania

OBSŁUGUJE:
- YouTube (yt-dlp)
- Konwersja audio (ffmpeg)
- Walidacja narzędzi
- Fallback instalacji
"""

import subprocess
import shutil
import re
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from enum import Enum


class ToolStatus(Enum):
    """Status narzędzia zewnętrznego"""
    AVAILABLE = "available"
    MISSING = "missing"
    OUTDATED = "outdated"
    BROKEN = "broken"


class MediaTaskError(Exception):
    """Błąd podczas zadania medialnego"""
    pass


class MediaPipeline:
    """
    Pipeline dla zadań multimedialnych.
    
    Workflow:
    1. Check tools (yt-dlp, ffmpeg)
    2. Ensure tools (install/update jeśli brak)
    3. Download media
    4. Convert (opcjonalnie)
    5. Cleanup
    6. Report
    """
    
    REQUIRED_TOOLS = {
        "yt-dlp": {
            "min_version": "2023.01.01",
            "install_methods": ["apt", "pip", "github"],
            "check_cmd": ["yt-dlp", "--version"]
        },
        "ffmpeg": {
            "min_version": "4.0",
            "install_methods": ["apt"],
            "check_cmd": ["ffmpeg", "-version"]
        }
    }
    
    def __init__(self, work_dir: Optional[Path] = None, logger=None):
        """
        Args:
            work_dir: katalog roboczy (auto-detect lub ~/Pobrane/ai-downloads)
            logger: opcjonalny logger
        """
        if work_dir is None:
            self.work_dir = self.detect_download_dir()
        else:
            self.work_dir = Path(work_dir)
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.work_dir / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)
        
        self.logger = logger

    def detect_download_dir(self) -> Path:
        """
        Wykryj katalog pobierania użytkownika.
        
        Kolejność:
        1. XDG_DOWNLOAD_DIR (standard Linux)
        2. ~/Pobrane (polski system)
        3. ~/Downloads (angielski system)
        4. Fallback: ~/Downloads/ai-downloads
        
        Returns:
            Path do katalogu ai-downloads
        """
        import os
        
        # 1. XDG standard
        xdg_download = os.environ.get('XDG_DOWNLOAD_DIR')
        if xdg_download:
            xdg_path = Path(xdg_download)
            if xdg_path.exists():
                return xdg_path / "ai-downloads"
        
        # 2. Polski system
        pobrane = Path.home() / "Pobrane"
        if pobrane.exists() and pobrane.is_dir():
            return pobrane / "ai-downloads"
        
        # 3. Angielski system
        downloads = Path.home() / "Downloads"
        if downloads.exists() and downloads.is_dir():
            return downloads / "ai-downloads"
        
        # 4. Fallback - utwórz Downloads
        fallback = Path.home() / "Downloads" / "ai-downloads"
        return fallback
    
    # === TOOL MANAGEMENT ===
    
    def check_tool(self, tool_name: str) -> Tuple[ToolStatus, Optional[str]]:
        """
        Sprawdź status narzędzia.
        
        Returns:
            (status, version/error)
        """
        if tool_name not in self.REQUIRED_TOOLS:
            return (ToolStatus.BROKEN, f"Unknown tool: {tool_name}")
        
        tool_config = self.REQUIRED_TOOLS[tool_name]
        
        # Sprawdź czy istnieje
        if not shutil.which(tool_name):
            return (ToolStatus.MISSING, None)
        
        # Sprawdź wersję
        try:
            result = subprocess.run(
                tool_config["check_cmd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return (ToolStatus.BROKEN, result.stderr[:200])
            
            # Wyciągnij wersję
            version = self._extract_version(result.stdout)
            
            if not version:
                return (ToolStatus.AVAILABLE, "unknown version")
            
            # Sprawdź czy wystarczająco nowa
            min_version = tool_config.get("min_version")
            if min_version and self._compare_versions(version, min_version) < 0:
                return (ToolStatus.OUTDATED, version)
            
            return (ToolStatus.AVAILABLE, version)
        
        except subprocess.TimeoutExpired:
            return (ToolStatus.BROKEN, "timeout checking version")
        except Exception as e:
            return (ToolStatus.BROKEN, str(e))
    
    def _extract_version(self, output: str) -> Optional[str]:
        """Wyciągnij wersję z output"""
        # Szukaj wzorców: 2023.12.31, 4.4.2, v1.2.3
        patterns = [
            r'(\d{4}\.\d{2}\.\d{2})',  # yt-dlp: 2023.12.31
            r'version (\d+\.\d+\.?\d*)',  # ffmpeg: version 4.4.2
            r'v?(\d+\.\d+\.?\d*)'  # ogólny
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
        
        return None
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Porównaj wersje.
        
        Returns:
            -1 jeśli v1 < v2
             0 jeśli v1 == v2
             1 jeśli v1 > v2
        """
        # Normalizuj (usuń 'v', zamień . na listy)
        v1_parts = [int(x) for x in v1.replace('v', '').split('.')]
        v2_parts = [int(x) for x in v2.replace('v', '').split('.')]
        
        # Pad do tej samej długości
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += [0] * (max_len - len(v1_parts))
        v2_parts += [0] * (max_len - len(v2_parts))
        
        # Porównaj
        for a, b in zip(v1_parts, v2_parts):
            if a < b:
                return -1
            elif a > b:
                return 1
        
        return 0
    
    def ensure_tool(self, tool_name: str, method: str = "auto") -> Dict:
        """
        Upewnij się że narzędzie jest dostępne.
        Instaluje/aktualizuje jeśli brak.
        
        Args:
            tool_name: nazwa narzędzia
            method: metoda instalacji (auto/apt/pip/github)
        
        Returns:
            {"success": bool, "action": str, "message": str}
        """
        status, version = self.check_tool(tool_name)
        
        if status == ToolStatus.AVAILABLE:
            return {
                "success": True,
                "action": "none",
                "message": f"{tool_name} already available (version {version})"
            }
        
        if status == ToolStatus.OUTDATED:
            # Tylko ostrzeżenie, nie wymuszamy aktualizacji
            return {
                "success": True,
                "action": "warn",
                "message": f"{tool_name} is outdated ({version}), but will work"
            }
        
        # MISSING lub BROKEN - trzeba zainstalować
        tool_config = self.REQUIRED_TOOLS[tool_name]
        install_methods = tool_config["install_methods"]
        
        if method == "auto":
            # Spróbuj w kolejności
            for m in install_methods:
                result = self._try_install(tool_name, m)
                if result["success"]:
                    return result
            
            # Wszystkie metody failnęły
            return {
                "success": False,
                "action": "install_failed",
                "message": f"Failed to install {tool_name} (tried: {', '.join(install_methods)})"
            }
        else:
            # Konkretna metoda
            return self._try_install(tool_name, method)
    
    def _try_install(self, tool_name: str, method: str) -> Dict:
        """Spróbuj zainstalować narzędzie daną metodą"""
        
        if self.logger:
            self.logger.info(f"Trying to install {tool_name} via {method}")
        
        try:
            if method == "apt":
                result = subprocess.run(
                    ["sudo", "apt", "install", "-y", tool_name],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minut
                )
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "action": "installed_apt",
                        "message": f"Installed {tool_name} via apt"
                    }
                else:
                    return {
                        "success": False,
                        "action": "apt_failed",
                        "message": result.stderr[:200]
                    }
            
            elif method == "pip":
                result = subprocess.run(
                    ["pip", "install", "--break-system-packages", tool_name],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "action": "installed_pip",
                        "message": f"Installed {tool_name} via pip"
                    }
                else:
                    return {
                        "success": False,
                        "action": "pip_failed",
                        "message": result.stderr[:200]
                    }
            
            elif method == "github":
                # Specjalne dla yt-dlp
                if tool_name == "yt-dlp":
                    return self._install_ytdlp_github()
                else:
                    return {
                        "success": False,
                        "action": "unsupported",
                        "message": f"GitHub install not supported for {tool_name}"
                    }
            
            else:
                return {
                    "success": False,
                    "action": "unknown_method",
                    "message": f"Unknown install method: {method}"
                }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "action": "timeout",
                "message": f"Installation timeout for {tool_name}"
            }
        except Exception as e:
            return {
                "success": False,
                "action": "exception",
                "message": str(e)
            }
    
    def _install_ytdlp_github(self) -> Dict:
        """Instaluj yt-dlp z GitHub release"""
        try:
            # Pobierz najnowszy release
            result = subprocess.run(
                [
                    "curl", "-L",
                    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
                    "-o", "/tmp/yt-dlp"
                ],
                capture_output=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "action": "download_failed",
                    "message": "Failed to download yt-dlp from GitHub"
                }
            
            # Chmod +x
            subprocess.run(["chmod", "+x", "/tmp/yt-dlp"], check=True)
            
            # Przenieś do ~/.local/bin
            local_bin = Path.home() / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            
            shutil.move("/tmp/yt-dlp", local_bin / "yt-dlp")
            
            return {
                "success": True,
                "action": "installed_github",
                "message": f"Installed yt-dlp to {local_bin}/yt-dlp"
            }
        
        except Exception as e:
            return {
                "success": False,
                "action": "exception",
                "message": str(e)
            }
    
    # === MEDIA OPERATIONS ===
    
    def download_media(self, url: str, output_format: str = "best", audio_only: bool = False) -> Dict:
        """
        Pobierz media z URL.
        
        Args:
            url: URL do pobrania
            output_format: format wideo (best/worst/720p/1080p)
            audio_only: tylko audio (bez wideo)
        
        Returns:
            {
                "success": bool,
                "filepath": Path,
                "title": str,
                "size_mb": float,
                "duration": str
            }
        """
        # Sprawdź yt-dlp
        status, version = self.check_tool("yt-dlp")
        if status not in [ToolStatus.AVAILABLE, ToolStatus.OUTDATED]:
            raise MediaTaskError("yt-dlp not available - run ensure_tool first")
        
        # Zbuduj komendę
        output_template = str(self.tmp_dir / "%(title)s.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",  # ZAWSZE pojedyncze wideo
            "-o", output_template,
        ]
        
        if audio_only:
            cmd.extend(["-x", "--audio-format", "best"])
        else:
            cmd.extend(["-f", output_format])
        
        cmd.append(url)
        
        if self.logger:
            self.logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minut
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr[:500]
                }
            
            # Znajdź pobrany plik
            downloaded = self._find_latest_file(self.tmp_dir)
            
            if not downloaded or not downloaded.exists():
                return {
                    "success": False,
                    "error": "Downloaded file not found"
                }
            
            # Sprawdź rozmiar
            size_mb = downloaded.stat().st_size / (1024 * 1024)
            
            if size_mb < 0.01:  # < 10 KB = coś nie tak
                return {
                    "success": False,
                    "error": f"Downloaded file too small ({size_mb:.2f} MB)"
                }
            
            # Wyciągnij metadane z output
            title = self._extract_title_from_output(result.stdout)
            duration = self._extract_duration_from_output(result.stdout)
            
            return {
                "success": True,
                "filepath": downloaded,
                "title": title or downloaded.stem,
                "size_mb": round(size_mb, 2),
                "duration": duration or "unknown"
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Download timeout (>10 minutes)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def convert_to_audio(self, video_path: Path, audio_format: str = "mp3", bitrate: str = "192k") -> Dict:
        """
        Konwertuj wideo do audio.
        
        Args:
            video_path: ścieżka do wideo
            audio_format: format audio (mp3/m4a/opus)
            bitrate: bitrate (128k/192k/320k)
        
        Returns:
            {
                "success": bool,
                "filepath": Path,
                "size_mb": float
            }
        """
        # Sprawdź ffmpeg
        status, version = self.check_tool("ffmpeg")
        if status not in [ToolStatus.AVAILABLE, ToolStatus.OUTDATED]:
            raise MediaTaskError("ffmpeg not available - run ensure_tool first")
        
        if not video_path.exists():
            return {
                "success": False,
                "error": f"Video file not found: {video_path}"
            }
        
        # Output path
        output_path = video_path.with_suffix(f".{audio_format}")
        
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # no video
            "-acodec", "libmp3lame" if audio_format == "mp3" else "copy",
            "-ab", bitrate,
            "-y",  # overwrite
            str(output_path)
        ]
        
        if self.logger:
            self.logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minut
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr[:500]
                }
            
            # Sprawdź output
            if not output_path.exists():
                return {
                    "success": False,
                    "error": "Converted file not found"
                }
            
            size_mb = output_path.stat().st_size / (1024 * 1024)
            
            if size_mb < 0.01:
                return {
                    "success": False,
                    "error": f"Converted file too small ({size_mb:.2f} MB)"
                }
            
            return {
                "success": True,
                "filepath": output_path,
                "size_mb": round(size_mb, 2)
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Conversion timeout (>5 minutes)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup(self, files: List[Path]):
        """
        Usuń pliki tymczasowe.
        Bezpieczne - usuwa tylko jeśli w tmp_dir.
        """
        removed = []
        
        for file_path in files:
            try:
                # Bezpieczeństwo - tylko w tmp_dir
                if not str(file_path).startswith(str(self.tmp_dir)):
                    if self.logger:
                        self.logger.warning(f"Skipping cleanup outside tmp_dir: {file_path}")
                    continue
                
                if file_path.exists():
                    file_path.unlink()
                    removed.append(str(file_path))
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Cleanup failed for {file_path}: {e}")
        
        return removed
    
    def move_to_destination(self, file_path: Path, dest_dir: Path, new_name: Optional[str] = None) -> Path:
        """
        Przenieś plik do docelowego katalogu.
        
        Args:
            file_path: plik źródłowy
            dest_dir: katalog docelowy
            new_name: nowa nazwa (opcjonalnie)
        
        Returns:
            Path do nowego pliku
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        if new_name:
            dest_path = dest_dir / new_name
        else:
            dest_path = dest_dir / file_path.name
        
        # Unikaj nadpisania
        counter = 1
        original_dest = dest_path
        while dest_path.exists():
            stem = original_dest.stem
            suffix = original_dest.suffix
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        shutil.move(str(file_path), str(dest_path))
        
        return dest_path
    
    # === HELPERS ===
    
    def _find_latest_file(self, directory: Path) -> Optional[Path]:
        """Znajdź najnowszy plik w katalogu"""
        files = [f for f in directory.iterdir() if f.is_file()]
        
        if not files:
            return None
        
        return max(files, key=lambda f: f.stat().st_mtime)
    
    def _extract_title_from_output(self, output: str) -> Optional[str]:
        """Wyciągnij tytuł z output yt-dlp"""
        # [download] Destination: ...
        match = re.search(r'\[download\] Destination: (.+)', output)
        if match:
            return Path(match.group(1)).stem
        
        return None
    
    def _extract_duration_from_output(self, output: str) -> Optional[str]:
        """Wyciągnij czas trwania z output"""
        # [download]   0.0% of ~10.00MiB at  1.00MiB/s ETA 00:10
        match = re.search(r'ETA (\d{2}:\d{2})', output)
        if match:
            return match.group(1)
        
        return None
    
    def format_report(self, download_result: Dict, convert_result: Optional[Dict] = None, final_path: Optional[Path] = None) -> str:
        """Sformatuj końcowy raport"""
        lines = []
        
        if download_result.get("success"):
            lines.append(f"✓ Pobrano: {download_result['title']}")
            lines.append(f"  Rozmiar: {download_result['size_mb']} MB")
            
            if download_result.get("duration"):
                lines.append(f"  Czas trwania: {download_result['duration']}")
        
        if convert_result and convert_result.get("success"):
            lines.append(f"✓ Przekonwertowano do MP3 (192 kbps)")
            lines.append(f"  Rozmiar: {convert_result['size_mb']} MB")
        
        if final_path:
            lines.append(f"📁 Lokalizacja: {final_path}")
        
        return "\n".join(lines)