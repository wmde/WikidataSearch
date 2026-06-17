"""Initialize database tables before starting the web server."""

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text

from wikidatasearch.services.logger.database import Base, Logger, UserAgents, engine


def sync_indexes() -> None:
    """Create model indexes and drop obsolete managed indexes."""
    inspector = sqlalchemy_inspect(engine)
    managed_tables = (Logger.__table__, UserAgents.__table__)

    # Create missing indexes
    for table in managed_tables:
        if not inspector.has_table(table.name):
            continue
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)

    # Drop obsolete indexes
    with engine.begin() as conn:
        for table in managed_tables:
            if not inspector.has_table(table.name):
                continue

            existing_indexes = {index["name"] for index in inspector.get_indexes(table.name)}
            declared_index_names = {index.name for index in table.indexes}

            obsolete_indexes = sorted(
                index_name
                for index_name in existing_indexes
                if index_name.startswith(f"ix_{table.name}_") and index_name not in declared_index_names
            )
            for index_name in obsolete_indexes:
                conn.execute(text(f"DROP INDEX {index_name} ON {table.name}"))


def initialize_database():
    """Create tables if they do not already exist."""
    try:
        user_agent_history_exists = sqlalchemy_inspect(engine).has_table(UserAgents.__tablename__)

        Base.metadata.create_all(engine)

        if not user_agent_history_exists:
            print("Building user agent history from existing request logs...")
            UserAgents.build_from_requests()

        sync_indexes()
        return True
    except Exception as e:
        print(f"Error while initializing labels database: {e}")
        return False


if __name__ == "__main__":
    """Run database initialization as a standalone startup step."""
    raise SystemExit(0 if initialize_database() else 1)
