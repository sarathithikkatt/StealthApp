"""
Background worker to perform OCR on images.
"""
from PyQt6.QtGui import QPixmap
from stealthapp.ai.base import OCRScanner
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

class OCRWorker(OCRScanner):
    # OCRWorker will be a long-lived QObject that runs scans on request.
    # It might use internal threads or be moved to a thread.
    
    def __init__(self, parent=None):
        super().__init__(parent)

    def scan(self, pixmap: QPixmap):
        # We need a copy of the image data since QPixmap cannot be safely used across threads
        from PyQt6.QtCore import QBuffer, QIODevice
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        success = pixmap.save(buffer, "PNG")
        if not success:
            logger.error("Failed to save pixmap to buffer")
            img_bytes = b""
        else:
            # Seek to beginning and read all data
            buffer.seek(0)
            img_bytes = buffer.data().data()
            logger.info(f"Pixmap converted to bytes: {len(img_bytes)} bytes, pixmap size: {pixmap.width()}x{pixmap.height()}")

        # Run OCR in a background thread to avoid blocking UI
        import threading
        threading.Thread(target=self._run_ocr, args=(img_bytes,), daemon=True).start()

    def _run_ocr(self, img_bytes: bytes):
        try:
            import pytesseract
            from PIL import Image
            import numpy as np
            import io
            
            if not img_bytes:
                self.error_occurred.emit("Image data is empty")
                return
            
            logger.info(f"OCRWorker started processing image. Data size: {len(img_bytes)} bytes")
            image = Image.open(io.BytesIO(img_bytes))
            logger.info(f"Image opened: mode={image.mode}, size={image.size}")
            
            # Check if image is mostly blank
            img_array = np.array(image)
            if self._is_blank_image(img_array):
                logger.warning("Image appears to be blank or very low content (mostly one color)")
                self.error_occurred.emit("Captured image appears to be blank or transparent. Make sure the target window has visible content.")
                return
            
            text = pytesseract.image_to_string(image)
            text = text.strip()
            
            logger.info(f"OCRWorker extracted {len(text)} characters. Text preview: {text[:100]}")
            if not text:
                logger.warning("Tesseract extracted 0 characters - image may be too light/low contrast or have no readable text")
                self.error_occurred.emit("No text could be extracted. The image might have:\n- Very light/faint text\n- Low contrast\n- Images instead of text\n- Text too small to read")
            else:
                self.text_extracted.emit(text)

        except ImportError:
            self.error_occurred.emit("pytesseract or PIL is not installed. Please run `pip install pytesseract pillow`.")
        except pytesseract.TesseractNotFoundError:
            self.error_occurred.emit("Tesseract is not installed or not in PATH. Please install Tesseract-OCR.")
        except Exception as e:
            logger.error(f"OCRWorker failed: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR failed: {e}")

    @staticmethod
    def _is_blank_image(img_array) -> bool:
        """Check if image is mostly blank (uniform color or very low variance)."""
        try:
            import numpy as np
            # Calculate standard deviation across channels
            # If it's very low, the image is mostly one color
            std_dev = np.std(img_array)
            # Also check if it's mostly white or black
            mean_val = np.mean(img_array)
            logger.info(f"Image statistics: mean={mean_val:.1f}, std_dev={std_dev:.1f}")
            
            # If mostly uniform (low std dev) and either very bright or very dark
            if std_dev < 15 and (mean_val > 240 or mean_val < 15):
                logger.warning(f"Image is mostly uniform: mean={mean_val:.1f}, std_dev={std_dev:.1f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")
            return False
