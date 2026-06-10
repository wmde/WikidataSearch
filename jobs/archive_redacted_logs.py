"""Archive redacted request logs to a SQL dump, then delete them."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import String, delete, func, insert, literal, select

from wikidatasearch.services.logger import Logger, engine

ARCHIVE_BATCH_SIZE = 1000


def archive_redacted_requests(output_path: Path, archive_engine=engine) -> int:
    """Archive all currently redacted requests and delete the archived rows.

    The dump is fully written before rows are deleted. If the database transaction
    fails, the dump remains available and the deletion is rolled back.

    Args:
        output_path: Destination SQL dump path. It must not already exist.
        archive_engine: SQLAlchemy engine used for the archive transaction.

    Returns:
        Number of archived and deleted request rows.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"archive already exists: {output_path}")

    archived = 0
    dump_file = None
    try:
        with archive_engine.begin() as connection:
            max_id = connection.scalar(select(func.max(Logger.id)).where(Logger.is_redacted.is_(True)))
        if max_id is None:
            return 0

        while True:
            with archive_engine.begin() as connection:
                rows = list(
                    connection.execute(
                        select(Logger.__table__)
                        .where(Logger.is_redacted.is_(True), Logger.id <= max_id)
                        .order_by(Logger.id)
                        .limit(ARCHIVE_BATCH_SIZE)
                        .with_for_update()
                    ).mappings()
                )
                if not rows:
                    break

                batch = []
                for row in rows:
                    values = {}
                    for column in Logger.__table__.columns:
                        value = row[column.name]
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                            values[column.name] = literal(value, type_=String())
                        else:
                            values[column.name] = literal(value, type_=column.type)
                    batch.append(values)

                statement = insert(Logger.__table__).values(batch)
                dump = (
                    str(
                        statement.compile(
                            dialect=archive_engine.dialect,
                            compile_kwargs={"literal_binds": True},
                        )
                    )
                    + ";\n"
                ).encode("utf-8")

                if dump_file is None:
                    dump_file = output_path.open(mode="xb")
                dump_position = dump_file.tell()
                try:
                    dump_file.write(dump)
                    dump_file.flush()
                    os.fsync(dump_file.fileno())
                except Exception:
                    dump_file.seek(dump_position)
                    dump_file.truncate()
                    raise

                archived_ids = [row["id"] for row in rows]
                connection.execute(delete(Logger.__table__).where(Logger.id.in_(archived_ids)))
                archived += len(rows)
    finally:
        if dump_file is not None:
            dump_file.close()

    return archived


def main() -> None:
    """Archive and delete redacted request logs."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/archives") / f"requests-redacted-{timestamp}.sql",
        help="SQL dump destination; defaults to data/archives/requests-redacted-<timestamp>.sql",
    )
    args = parser.parse_args()

    archived = archive_redacted_requests(args.output)
    print(f"archive complete: archived_rows={archived} output={args.output}")


if __name__ == "__main__":
    main()
