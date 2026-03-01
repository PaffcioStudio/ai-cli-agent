"""
Image Tasks Pipeline - konwersja i przetwarzanie obrazków.

OBSŁUGUJE:
- PNG/JPG/WebP/BMP/TIFF → ICO (favicon generator, multi-size)
- Konwersja formatów (PNG→WebP, WebP→PNG, JPG↔PNG, itd.)
- Kompresja (lossy dla JPG/WebP, lossless dla PNG optipng-style)
- Resize / crop / thumbnail
- Batch processing wielu plików
- Metadane (strip EXIF, show info)

ZALEŻNOŚCI:
- Pillow (pip install Pillow) - główna biblioteka
- optipng (apt/binary) - opcjonalna kompresja PNG
- cwebp (apt) - opcjonalna konwersja WebP
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from enum import Enum


class ImageToolStatus(Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    BROKEN = "broken"


class ImageTaskError(Exception):
    pass


class ImagePipeline:
    """
    Pipeline dla zadań przetwarzania obrazków.
    
    Workflow:
    1. Check tools (Pillow, optipng, cwebp)
    2. Ensure tools (install jeśli brak)
    3. Process (convert, resize, compress, batch)
    4. Report
    """

    SUPPORTED_INPUT_FORMATS = {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp",
        ".tiff", ".tif", ".gif", ".ico"
    }

    SUPPORTED_OUTPUT_FORMATS = {
        "png", "jpg", "jpeg", "webp", "ico",
        "bmp", "tiff", "gif"
    }

    # Rozmiary dla multi-size ICO
    ICO_SIZES = [16, 32, 48, 64, 128, 256]

    def __init__(self, logger=None):
        self.logger = logger
        self._pillow_available = None

    # =====================================================================
    # TOOL MANAGEMENT
    # =====================================================================

    def check_pillow(self) -> Tuple[ImageToolStatus, Optional[str]]:
        """Sprawdź czy Pillow jest dostępne"""
        try:
            from PIL import Image
            import PIL
            return (ImageToolStatus.AVAILABLE, PIL.__version__)
        except ImportError:
            return (ImageToolStatus.MISSING, None)

    def ensure_pillow(self) -> Dict:
        """Zainstaluj Pillow jeśli brak"""
        status, version = self.check_pillow()

        if status == ImageToolStatus.AVAILABLE:
            return {"success": True, "action": "none", "message": f"Pillow already available ({version})"}

        try:
            result = subprocess.run(
                ["pip", "install", "--break-system-packages", "Pillow"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return {"success": True, "action": "installed_pip", "message": "Pillow installed via pip"}
            else:
                # Fallback: pip3
                result2 = subprocess.run(
                    ["pip3", "install", "--break-system-packages", "Pillow"],
                    capture_output=True, text=True, timeout=120
                )
                if result2.returncode == 0:
                    return {"success": True, "action": "installed_pip3", "message": "Pillow installed via pip3"}
                return {"success": False, "action": "pip_failed", "message": result.stderr[:200]}
        except Exception as e:
            return {"success": False, "action": "exception", "message": str(e)}

    def check_tool(self, tool_name: str) -> Tuple[ImageToolStatus, Optional[str]]:
        """Sprawdź narzędzie zewnętrzne (optipng, cwebp)"""
        if not shutil.which(tool_name):
            return (ImageToolStatus.MISSING, None)
        try:
            result = subprocess.run(
                [tool_name, "--version"], capture_output=True, text=True, timeout=5
            )
            version = result.stdout.split("\n")[0][:50] if result.stdout else "ok"
            return (ImageToolStatus.AVAILABLE, version)
        except Exception:
            return (ImageToolStatus.AVAILABLE, "ok")

    def ensure_tool(self, tool_name: str) -> Dict:
        """Zainstaluj narzędzie systemowe"""
        status, _ = self.check_tool(tool_name)
        if status == ImageToolStatus.AVAILABLE:
            return {"success": True, "action": "none", "message": f"{tool_name} already available"}

        try:
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", tool_name],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                return {"success": True, "action": "installed_apt", "message": f"{tool_name} installed via apt"}
            return {"success": False, "action": "apt_failed", "message": result.stderr[:200]}
        except Exception as e:
            return {"success": False, "action": "exception", "message": str(e)}

    def _get_pil(self):
        """Lazy import PIL"""
        status, _ = self.check_pillow()
        if status != ImageToolStatus.AVAILABLE:
            raise ImageTaskError("Pillow not available - run ensure_pillow() first")
        from PIL import Image
        return Image

    @staticmethod
    def _resampling(name: str = "lanczos"):
        """
        Zwróć stałą resamplingową kompatybilną z Pillow 9 i 10+.
        Pillow 10 przeniosło Image.LANCZOS → Image.Resampling.LANCZOS.
        """
        from PIL import Image
        mapping = {
            "lanczos": "LANCZOS",
            "bilinear": "BILINEAR",
            "bicubic": "BICUBIC",
            "nearest": "NEAREST",
            "box": "BOX",
            "hamming": "HAMMING",
        }
        attr = mapping.get(name.lower(), "LANCZOS")
        # Pillow 10+
        if hasattr(Image, "Resampling"):
            return getattr(Image.Resampling, attr)
        # Pillow 9 i starsze
        return getattr(Image, attr)

    # =====================================================================
    # CORE OPERATIONS
    # =====================================================================

    def convert_to_ico(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        sizes: Optional[List[int]] = None
    ) -> Dict:
        """
        Konwertuj obraz na ICO (favicon).
        
        Args:
            input_path: plik źródłowy (PNG zalecany)
            output_path: ścieżka wyjściowa (domyślnie same_dir/favicon.ico)
            sizes: lista rozmiarów (domyślnie [16,32,48,64,128,256])
        
        Returns:
            {"success": bool, "filepath": Path, "sizes": List[int], "size_kb": float}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if output_path is None:
            output_path = input_path.parent / "favicon.ico"
        output_path = Path(output_path)

        if sizes is None:
            sizes = self.ICO_SIZES

        try:
            img = Image.open(input_path).convert("RGBA")

            icon_images = []
            for size in sizes:
                resized = img.resize((size, size), self._resampling("lanczos"))
                icon_images.append(resized)

            icon_images[0].save(
                output_path,
                format="ICO",
                sizes=[(s, s) for s in sizes],
                append_images=icon_images[1:]
            )

            size_kb = round(output_path.stat().st_size / 1024, 2)

            return {
                "success": True,
                "filepath": output_path,
                "sizes": sizes,
                "size_kb": size_kb
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert_format(
        self,
        input_path: Path,
        output_format: str,
        output_path: Optional[Path] = None,
        quality: int = 85,
        lossless: bool = False
    ) -> Dict:
        """
        Konwertuj obraz między formatami.
        
        Args:
            input_path: plik źródłowy
            output_format: "webp", "png", "jpg", "bmp", "tiff"
            output_path: ścieżka wyjściowa (domyślnie same dir, nowe rozszerzenie)
            quality: jakość 1-100 (dla jpg/webp)
            lossless: bezstratna konwersja (dla webp)
        
        Returns:
            {"success": bool, "filepath": Path, "size_kb": float, "reduction_pct": float}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        fmt = output_format.lower().lstrip(".")
        if fmt == "jpg":
            fmt = "jpeg"

        if fmt not in self.SUPPORTED_OUTPUT_FORMATS:
            return {"success": False, "error": f"Unsupported output format: {output_format}"}

        if output_path is None:
            ext = "jpg" if fmt == "jpeg" else fmt
            output_path = input_path.with_suffix(f".{ext}")
        output_path = Path(output_path)

        try:
            img = Image.open(input_path)
            original_size = input_path.stat().st_size

            save_kwargs = {}

            if fmt == "jpeg":
                img = img.convert("RGB")
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True

            elif fmt == "webp":
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                save_kwargs["quality"] = quality
                save_kwargs["lossless"] = lossless
                save_kwargs["method"] = 6

            elif fmt == "png":
                save_kwargs["optimize"] = True

            img.save(output_path, format=fmt.upper(), **save_kwargs)

            new_size = output_path.stat().st_size
            size_kb = round(new_size / 1024, 2)
            reduction_pct = round((1 - new_size / original_size) * 100, 1) if original_size > 0 else 0

            return {
                "success": True,
                "filepath": output_path,
                "size_kb": size_kb,
                "original_size_kb": round(original_size / 1024, 2),
                "reduction_pct": reduction_pct
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compress_image(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        quality: int = 80,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        use_optipng: bool = True
    ) -> Dict:
        """
        Kompresuj obraz (TinyPNG-style).
        
        Args:
            input_path: plik źródłowy
            output_path: ścieżka wyjściowa (domyślnie nadpisuje)
            quality: jakość 1-100 (dla jpg/webp)
            max_width: maksymalna szerokość (proporcjonalne skalowanie)
            max_height: maksymalna wysokość (proporcjonalne skalowanie)
            use_optipng: użyj optipng dla PNG jeśli dostępne
        
        Returns:
            {"success": bool, "filepath": Path, "size_kb": float, "reduction_pct": float, "dimensions": tuple}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if output_path is None:
            output_path = input_path
        output_path = Path(output_path)

        original_size = input_path.stat().st_size

        try:
            img = Image.open(input_path)
            original_dims = img.size
            fmt = input_path.suffix.lower().lstrip(".")

            # Resize jeśli potrzeba
            if max_width or max_height:
                img = self._resize_to_fit(img, max_width, max_height)

            save_kwargs = {}

            if fmt in ("jpg", "jpeg"):
                img = img.convert("RGB")
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
                fmt_pil = "JPEG"

            elif fmt == "webp":
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6
                fmt_pil = "WEBP"

            elif fmt == "png":
                save_kwargs["optimize"] = True
                fmt_pil = "PNG"

            else:
                fmt_pil = fmt.upper()

            img.save(output_path, format=fmt_pil, **save_kwargs)

            # Opcjonalne optipng dla PNG
            if fmt == "png" and use_optipng:
                optipng_status, _ = self.check_tool("optipng")
                if optipng_status == ImageToolStatus.AVAILABLE:
                    subprocess.run(
                        ["optipng", "-o2", "-quiet", str(output_path)],
                        capture_output=True, timeout=60
                    )

            new_size = output_path.stat().st_size
            size_kb = round(new_size / 1024, 2)
            reduction_pct = round((1 - new_size / original_size) * 100, 1) if original_size > 0 else 0

            return {
                "success": True,
                "filepath": output_path,
                "size_kb": size_kb,
                "original_size_kb": round(original_size / 1024, 2),
                "reduction_pct": reduction_pct,
                "dimensions": img.size,
                "original_dimensions": original_dims
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resize_image(
        self,
        input_path: Path,
        width: Optional[int] = None,
        height: Optional[int] = None,
        output_path: Optional[Path] = None,
        keep_aspect: bool = True,
        resample: str = "lanczos"
    ) -> Dict:
        """
        Zmień rozmiar obrazu.
        
        Args:
            input_path: plik źródłowy
            width: docelowa szerokość (None = proporcjonalna)
            height: docelowa wysokość (None = proporcjonalna)
            output_path: ścieżka wyjściowa
            keep_aspect: zachowaj proporcje
            resample: algorytm ("lanczos", "bilinear", "bicubic", "nearest")
        
        Returns:
            {"success": bool, "filepath": Path, "dimensions": tuple, "size_kb": float}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if not width and not height:
            return {"success": False, "error": "Specify width or height"}

        if output_path is None:
            stem = input_path.stem
            suffix = input_path.suffix
            dims = f"{width or 'auto'}x{height or 'auto'}"
            output_path = input_path.parent / f"{stem}_{dims}{suffix}"
        output_path = Path(output_path)

        resample_map = {
            "lanczos": self._resampling("lanczos"),
            "bilinear": self._resampling("bilinear"),
            "bicubic": self._resampling("bicubic"),
            "nearest": self._resampling("nearest")
        }
        resample_filter = resample_map.get(resample.lower(), self._resampling("lanczos"))

        try:
            img = Image.open(input_path)
            orig_w, orig_h = img.size

            if keep_aspect:
                img = self._resize_to_fit(img, width, height, resample_filter)
            else:
                target_w = width or orig_w
                target_h = height or orig_h
                img = img.resize((target_w, target_h), resample_filter)

            fmt = input_path.suffix.lstrip(".").upper()
            if fmt == "JPG":
                fmt = "JPEG"

            save_kwargs = {}
            if fmt == "JPEG":
                img = img.convert("RGB")
                save_kwargs["quality"] = 90
                save_kwargs["optimize"] = True

            img.save(output_path, format=fmt, **save_kwargs)

            size_kb = round(output_path.stat().st_size / 1024, 2)

            return {
                "success": True,
                "filepath": output_path,
                "dimensions": img.size,
                "original_dimensions": (orig_w, orig_h),
                "size_kb": size_kb
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def crop_image(
        self,
        input_path: Path,
        x: int,
        y: int,
        width: int,
        height: int,
        output_path: Optional[Path] = None
    ) -> Dict:
        """
        Wytnij fragment obrazu.
        
        Args:
            input_path: plik źródłowy
            x, y: lewy górny róg (piksele)
            width, height: wymiary obszaru
            output_path: ścieżka wyjściowa
        
        Returns:
            {"success": bool, "filepath": Path, "dimensions": tuple, "size_kb": float}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if output_path is None:
            stem = input_path.stem
            suffix = input_path.suffix
            output_path = input_path.parent / f"{stem}_crop{suffix}"
        output_path = Path(output_path)

        try:
            img = Image.open(input_path)
            img_w, img_h = img.size

            # Walidacja
            if x < 0 or y < 0 or x + width > img_w or y + height > img_h:
                return {
                    "success": False,
                    "error": f"Crop region ({x},{y},{x+width},{y+height}) outside image bounds ({img_w}x{img_h})"
                }

            cropped = img.crop((x, y, x + width, y + height))

            fmt = input_path.suffix.lstrip(".").upper()
            if fmt == "JPG":
                fmt = "JPEG"

            save_kwargs = {}
            if fmt == "JPEG":
                cropped = cropped.convert("RGB")
                save_kwargs["quality"] = 90

            cropped.save(output_path, format=fmt, **save_kwargs)

            size_kb = round(output_path.stat().st_size / 1024, 2)

            return {
                "success": True,
                "filepath": output_path,
                "dimensions": cropped.size,
                "size_kb": size_kb
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_info(self, input_path: Path) -> Dict:
        """
        Pobierz informacje o obrazie (format, wymiary, rozmiar, tryb, EXIF).
        
        Returns:
            {"success": bool, "format": str, "dimensions": tuple, "mode": str, ...}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"File not found: {input_path}"}

        try:
            img = Image.open(input_path)
            size_kb = round(input_path.stat().st_size / 1024, 2)

            info = {
                "success": True,
                "filepath": input_path,
                "format": img.format or input_path.suffix.lstrip(".").upper(),
                "dimensions": img.size,
                "mode": img.mode,
                "size_kb": size_kb,
                "has_transparency": img.mode in ("RGBA", "LA") or "transparency" in img.info,
                "dpi": img.info.get("dpi"),
            }

            # EXIF jeśli dostępne
            try:
                from PIL.ExifTags import TAGS
                # _getexif() jest prywatne i niedostępne w Pylance - używamy getattr dla bezpieczeństwa
                get_exif = getattr(img, "_getexif", None)
                exif_data = get_exif() if get_exif else None
                if exif_data:
                    exif = {}
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if isinstance(value, bytes):
                            continue
                        exif[tag] = str(value)[:100]
                    info["exif"] = exif
            except Exception:
                pass

            return info

        except Exception as e:
            return {"success": False, "error": str(e)}

    def strip_metadata(self, input_path: Path, output_path: Optional[Path] = None) -> Dict:
        """
        Usuń EXIF i inne metadane z obrazu.
        
        Returns:
            {"success": bool, "filepath": Path, "size_kb": float, "reduction_kb": float}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if output_path is None:
            output_path = input_path
        output_path = Path(output_path)

        original_size = input_path.stat().st_size

        try:
            img = Image.open(input_path)
            # Stwórz nowy obraz bez metadanych
            clean = Image.new(img.mode, img.size)
            # img.getdata() zwraca ImagingCore - konwertuj jawnie na listę
            pixel_data = list(img.getdata())  # type: ignore[arg-type]
            clean.putdata(pixel_data)

            fmt = (img.format or input_path.suffix.lstrip(".")).upper()
            if fmt == "JPG":
                fmt = "JPEG"

            save_kwargs = {}
            if fmt == "JPEG":
                clean = clean.convert("RGB")
                save_kwargs["quality"] = 95

            clean.save(output_path, format=fmt, **save_kwargs)

            new_size = output_path.stat().st_size

            return {
                "success": True,
                "filepath": output_path,
                "size_kb": round(new_size / 1024, 2),
                "original_size_kb": round(original_size / 1024, 2),
                "reduction_kb": round((original_size - new_size) / 1024, 2)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =====================================================================
    # BATCH PROCESSING
    # =====================================================================

    def batch_convert(
        self,
        input_paths: List[Path],
        output_format: str,
        output_dir: Optional[Path] = None,
        quality: int = 85,
        progress_callback=None
    ) -> Dict:
        """
        Batch konwersja wielu plików.
        
        Args:
            input_paths: lista plików do konwersji
            output_format: format wyjściowy
            output_dir: katalog wyjściowy (domyślnie same dir co input)
            quality: jakość 1-100
            progress_callback: opcjonalna funkcja (current, total, path)
        
        Returns:
            {"success": bool, "processed": int, "failed": int, "results": List[Dict]}
        """
        results = []
        processed = 0
        failed = 0

        for i, input_path in enumerate(input_paths):
            if progress_callback:
                progress_callback(i + 1, len(input_paths), input_path)

            input_path = Path(input_path)

            if output_dir:
                ext = "jpg" if output_format.lower() in ("jpg", "jpeg") else output_format.lower()
                out_path = Path(output_dir) / f"{input_path.stem}.{ext}"
            else:
                out_path = None

            result = self.convert_format(input_path, output_format, out_path, quality)
            result["input"] = str(input_path)

            if result["success"]:
                processed += 1
            else:
                failed += 1

            results.append(result)

        return {
            "success": failed == 0,
            "processed": processed,
            "failed": failed,
            "total": len(input_paths),
            "results": results
        }

    def batch_compress(
        self,
        input_paths: List[Path],
        output_dir: Optional[Path] = None,
        quality: int = 80,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> Dict:
        """
        Batch kompresja wielu plików.
        
        Returns:
            {"success": bool, "processed": int, "failed": int, "total_saved_kb": float, "results": List[Dict]}
        """
        results = []
        processed = 0
        failed = 0
        total_saved = 0.0

        for input_path in input_paths:
            input_path = Path(input_path)

            if output_dir:
                out_path = Path(output_dir) / input_path.name
            else:
                out_path = None

            result = self.compress_image(input_path, out_path, quality, max_width, max_height)
            result["input"] = str(input_path)

            if result["success"]:
                processed += 1
                saved = result.get("original_size_kb", 0) - result.get("size_kb", 0)
                total_saved += max(0, saved)
            else:
                failed += 1

            results.append(result)

        return {
            "success": failed == 0,
            "processed": processed,
            "failed": failed,
            "total": len(input_paths),
            "total_saved_kb": round(total_saved, 2),
            "results": results
        }

    def generate_favicon_set(self, input_path: Path, output_dir: Optional[Path] = None) -> Dict:
        """
        Wygeneruj kompletny zestaw favicon (ICO + PNG w różnych rozmiarach).
        
        Tworzy:
        - favicon.ico (multi-size: 16,32,48,64)
        - favicon-16x16.png
        - favicon-32x32.png
        - favicon-180x180.png (Apple Touch Icon)
        - favicon-192x192.png (Android)
        - favicon-512x512.png (PWA)
        
        Returns:
            {"success": bool, "files": List[Path], "output_dir": Path}
        """
        Image = self._get_pil()
        input_path = Path(input_path)

        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}

        if output_dir is None:
            output_dir = input_path.parent
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        files = []
        errors = []

        try:
            img = Image.open(input_path).convert("RGBA")

            # Multi-size ICO
            ico_result = self.convert_to_ico(
                input_path,
                output_dir / "favicon.ico",
                sizes=[16, 32, 48, 64]
            )
            if ico_result["success"]:
                files.append(ico_result["filepath"])
            else:
                errors.append(f"ICO: {ico_result.get('error')}")

            # PNG w różnych rozmiarach
            png_sizes = [
                (16, "favicon-16x16.png"),
                (32, "favicon-32x32.png"),
                (180, "apple-touch-icon.png"),
                (192, "favicon-192x192.png"),
                (512, "favicon-512x512.png"),
            ]

            for size, filename in png_sizes:
                resized = img.resize((size, size), self._resampling("lanczos"))
                out_path = output_dir / filename
                resized.save(out_path, format="PNG", optimize=True)
                files.append(out_path)

            return {
                "success": len(errors) == 0,
                "files": files,
                "output_dir": output_dir,
                "errors": errors
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # =====================================================================
    # HELPERS
    # =====================================================================

    def _resize_to_fit(
        self,
        img,
        max_width: Optional[int],
        max_height: Optional[int],
        resample=None
    ):
        """Zmień rozmiar zachowując proporcje"""
        if resample is None:
            resample = self._resampling("lanczos")

        orig_w, orig_h = img.size

        if not max_width and not max_height:
            return img

        if max_width and not max_height:
            ratio = max_width / orig_w
            new_size = (max_width, int(orig_h * ratio))

        elif max_height and not max_width:
            ratio = max_height / orig_h
            new_size = (int(orig_w * ratio), max_height)

        else:
            ratio_w = max_width / orig_w
            ratio_h = max_height / orig_h
            ratio = min(ratio_w, ratio_h)
            new_size = (int(orig_w * ratio), int(orig_h * ratio))

        return img.resize(new_size, resample)

    def format_report(self, results: List[Dict], operation: str) -> str:
        """Sformatuj raport z operacji"""
        lines = [f"{'=' * 40}"]
        lines.append(f"Image {operation} Report")
        lines.append(f"{'=' * 40}")

        for r in results:
            if r.get("success"):
                fp = r.get("filepath", r.get("input", "?"))
                size_kb = r.get("size_kb", "?")
                reduction = r.get("reduction_pct")

                if reduction is not None:
                    lines.append(f"✓ {Path(fp).name} → {size_kb} KB (-{reduction}%)")
                else:
                    dims = r.get("dimensions")
                    dims_str = f" {dims[0]}x{dims[1]}" if dims else ""
                    lines.append(f"✓ {Path(fp).name}{dims_str} ({size_kb} KB)")
            else:
                src = r.get("input", r.get("filepath", "?"))
                lines.append(f"✗ {Path(str(src)).name}: {r.get('error', 'unknown error')}")

        return "\n".join(lines)