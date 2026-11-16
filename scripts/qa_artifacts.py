"""Prepara una copia temporal del libro real para las evidencias y el servidor de Chromium."""

import argparse
import os
import secrets
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import select

from backend.app.core.config import ROOT, Settings
from backend.app.db.models import Oficio
from backend.app.db.session import make_engine, session_factory
from backend.app.main import bootstrap, create_app
from backend.app.services.excel_sync import export_excel
from backend.app.services.pdf_generator import acuse_entrega_pdf, alertas_pdf, volante_pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=int, metavar="PUERTO")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    source = os.environ.get("BASE_XLSX_PATH")
    candidates = [Path(source)] if source else [ROOT / "Base.xlsx", ROOT / "data/Base.xlsx"]
    book = next((p for p in candidates if p.is_file()), None)
    if book is None:
        parser.error("Se necesita el libro real en data/Base.xlsx, Base.xlsx o BASE_XLSX_PATH.")
    out = ROOT / "work/qa"
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="sesion-", dir=out) as temporary:
        directory = Path(temporary)
        shutil.copyfile(book, directory / "Base.xlsx")
        settings = Settings(
            database_url=f"sqlite:///{directory / 'pruebas.db'}",
            data_dir=directory,
            jwt_secret=secrets.token_urlsafe(48),
        )
        if args.serve:
            if not (ROOT / "frontend/dist/index.html").is_file():
                parser.error("Primero compile el frontend con npm run build.")
            uvicorn.run(create_app(settings), host=args.host, port=args.serve)
            return
        engine = make_engine(settings)
        sessions = session_factory(engine)
        try:
            bootstrap(engine, sessions, settings)
            with sessions() as db:
                records = list(db.scalars(select(Oficio).order_by(Oficio.id)))
                reference = settings.today()
                (out / "volante.pdf").write_bytes(volante_pdf(records[-1], reference))
                (out / "alertas.pdf").write_bytes(alertas_pdf(records, reference))
                (out / "entrega.pdf").write_bytes(acuse_entrega_pdf(records, reference))
                (out / "correspondencia.xlsx").write_bytes(export_excel(records, reference))
                print(f"{len(records)} oficios procesados. Evidencias en {out}")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
