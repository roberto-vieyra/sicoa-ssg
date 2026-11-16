import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Settings:
    database_url: str = "sqlite:///./data/sicoa_ssg.db"
    data_dir: Path = field(default_factory=lambda: ROOT / "data")
    cors_origins: list[str] = field(default_factory=lambda: ["http://127.0.0.1:5173"])
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    timezone: str = "America/Mexico_City"
    auto_import: bool = True
    max_upload_bytes: int = 20 * 1024 * 1024

    def today(self):
        return datetime.now(ZoneInfo(self.timezone)).date()

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        data_dir = Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        secret = os.getenv("JWT_SECRET", "")
        if not secret:
            secret_path = data_dir / ".jwt_secret"
            try:
                with secret_path.open("x", encoding="utf-8") as stream:
                    stream.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
            secret = secret_path.read_text(encoding="utf-8").strip()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET debe contener al menos 32 caracteres.")
        origins = os.getenv("CORS_ORIGINS", '["http://127.0.0.1:5173","http://localhost:5173"]')
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./data/sicoa_ssg.db"),
            data_dir=data_dir,
            cors_origins=json.loads(origins) if origins.startswith("[") else origins.split(","),
            jwt_secret=secret,
            jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "480")),
            timezone=os.getenv("APP_TIMEZONE", "America/Mexico_City"),
            auto_import=os.getenv("AUTO_IMPORT", "1") == "1",
        )
