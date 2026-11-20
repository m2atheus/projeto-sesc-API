"""Backup online e ensaio de restauração em um arquivo novo."""
import argparse
import logging
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.logging import log, logger

STAMP = "%Y%m%dT%H%M%S%fZ"
NAME = re.compile(r"ws2000-(\d{8}T\d{12}Z)\.sqlite3")


def open_snapshot(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)


def verify(path: Path) -> dict[str, int]:
    with closing(open_snapshot(path)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Falha de integridade no arquivo")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Referência inválida no arquivo")
        if not conn.execute("SELECT version_num FROM alembic_version").fetchone():
            raise ValueError("Banco sem revisão Alembic")
        return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("stations", "observations")}


def snapshot(source: Path, target: Path) -> None:
    with closing(open_snapshot(source)) as reader, closing(sqlite3.connect(target)) as writer:
        reader.backup(writer, pages=256, sleep=0.05)
        # The published artifact is a single closed file, including committed WAL pages.
        writer.execute("PRAGMA journal_mode=DELETE").fetchone()


def publish(source: Path, directory: Path, name: str, *, copy: bool) -> Path:
    final = directory / name
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".ws2000-", delete=False) as temp:
        staging = Path(temp.name)
    try:
        if copy:
            shutil.copyfile(source, staging)
        else:
            snapshot(source, staging)
        verify(staging)
        staging.replace(final)
        return final
    finally:
        staging.unlink(missing_ok=True)


def prune(directory: Path, cutoff: datetime) -> None:
    for item in directory.glob("ws2000-*.sqlite3"):
        match = NAME.fullmatch(item.name)
        if match and item.is_file() and not item.is_symlink():
            try:
                created = datetime.strptime(match[1], STAMP).replace(tzinfo=UTC)
            except ValueError:
                continue
            if created < cutoff:
                item.unlink()


def run_backup(settings: Settings) -> Path:
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("O backup requer um arquivo SQLite")
    source = Path(url.database).resolve(strict=True)
    primary = settings.backup_dir.resolve()
    if primary == source.parent:
        raise ValueError("Separe os diretórios de backup e do banco ativo")
    primary.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    name = f"ws2000-{now.strftime(STAMP)}.sqlite3"
    saved = publish(source, primary, name, copy=False)
    log("backup_saved", file=str(saved))
    cutoff = now - timedelta(days=settings.backup_retention_days)
    prune(primary, cutoff)
    if settings.backup_secondary_dir:
        secondary = settings.backup_secondary_dir.resolve(strict=True)
        if secondary in (primary, source.parent):
            raise ValueError("O destino secundário deve ser independente")
        replica = publish(saved, secondary, name, copy=True)
        log("backup_replicated", file=str(replica))
        prune(secondary, cutoff)
    return saved


def restore_test(source: Path) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="ws2000-restore-") as directory:
        restored = Path(directory) / "restored.db"
        snapshot(source, restored)
        counts = verify(restored)
        if counts != verify(source):
            raise ValueError("Contagens divergentes na restauração")
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-restore", type=Path, metavar="BACKUP")
    parser.add_argument("--log-file", type=Path, help="Arquivo de log rotativo para o agendador")
    args = parser.parse_args()
    try:
        if args.log_file:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            logger.addHandler(RotatingFileHandler(args.log_file, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"))
        if args.test_restore:
            log("restore_verified", **restore_test(args.test_restore))
        else:
            run_backup(Settings())
    except (OSError, sqlite3.Error, ValueError) as exc:
        log("backup_failed", level=logging.ERROR, reason=str(exc))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
