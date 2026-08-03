import logging
from pathlib import Path

from backend.core.config import settings


LOG_FILE = settings.LOG_DIR / "hagmartk.log"

Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


logger = logging.getLogger("Hagmartk")