from pathlib import Path


class Settings:

    APP_NAME = "Hagmartk"

    VERSION = "0.1.0"

    DEBUG = True

    ROOT_DIR = Path(__file__).resolve().parents[2]

    DATA_DIR = ROOT_DIR / "data"

    LOG_DIR = ROOT_DIR / "logs"

    DATABASE_DIR = ROOT_DIR / "database"

    STRATEGIES_DIR = ROOT_DIR / "strategies"


settings = Settings()