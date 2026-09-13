import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.database.base import Base
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument
from backend.app.models.workflow_step import WorkflowStep
from backend.app.models.user import User
from backend.app.models.query_log import ClinicalQueryLog, QuerySource

SQLITE_PATH = BASE_DIR / "icmr_stw.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"
SUPABASE_URL = "postgresql://postgres.lgkhqfwyoxyhdpbarnkh:harsh_16171819@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

def migrate():
    print("=" * 60)
    print("MIGRATING ICMR-STW AI DATABASE TO SUPABASE POSTGRESQL")
    print("=" * 60)

    if not SQLITE_PATH.exists():
        print(f"[!] Warning: SQLite database {SQLITE_PATH} does not exist.")
        sqlite_engine = None
    else:
        print(f"[*] Reading source SQLite database: {SQLITE_PATH}")
        sqlite_engine = create_engine(SQLITE_URL)

    print(f"[*] Connecting to Supabase PostgreSQL...")
    supabase_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)

    # 1. Create all tables in Supabase
    print("[*] Creating schema tables in Supabase PostgreSQL...")
    Base.metadata.create_all(bind=supabase_engine)
    print("[+] Tables created successfully.")

    if not sqlite_engine:
        print("[!] No SQLite database to migrate from.")
        return

    def to_dict(instance):
        return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}

    SqliteSession = sessionmaker(bind=sqlite_engine)
    SupabaseSession = sessionmaker(bind=supabase_engine)

    with SqliteSession() as src, SupabaseSession() as dst:
        model_classes = [Specialty, Disease, STWDocument, WorkflowStep, User, ClinicalQueryLog, QuerySource]
        for cls in model_classes:
            items = src.query(cls).all()
            print(f"[*] Migrating {len(items)} records for {cls.__tablename__}...")
            for it in items:
                dst.merge(cls(**to_dict(it)))
            dst.commit()

    # Reset PostgreSQL sequence values to max(id)
    print("[*] Synchronizing PostgreSQL sequence values...")
    tables = ["specialties", "diseases", "stw_documents", "workflow_steps", "users", "query_logs", "query_sources"]
    with supabase_engine.begin() as conn:
        for t in tables:
            try:
                conn.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{t}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {t}), 1),
                        true
                    );
                """))
            except Exception as seq_err:
                pass

    # Verify row counts in Supabase
    print("\n" + "=" * 60)
    print("VERIFICATION: ROW COUNTS IN SUPABASE POSTGRESQL")
    print("=" * 60)
    with supabase_engine.connect() as conn:
        for t in tables:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar()
            print(f"  {t:25s}: {cnt} rows")

    print("\n[+] Migration to Supabase PostgreSQL completed successfully!")

if __name__ == "__main__":
    migrate()
