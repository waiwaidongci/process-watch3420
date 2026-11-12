"""已部署数据库的幂等结构升级；新库仍由 SQLAlchemy metadata 建表。"""
from sqlalchemy import inspect,text

MIGRATION_STATEMENTS=[
    "ALTER TABLE investigations ADD COLUMN IF NOT EXISTS kind VARCHAR NOT NULL DEFAULT 'initial'",
    "ALTER TABLE investigations ADD COLUMN IF NOT EXISTS subject_id INTEGER REFERENCES investigations(id)",
    "ALTER TABLE investigations ADD COLUMN IF NOT EXISTS superseded_by INTEGER REFERENCES investigations(id)",
    "ALTER TABLE investigations ADD COLUMN IF NOT EXISTS superseded_at VARCHAR NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS investigation_run_kind_status_idx ON investigations (run_id, kind, status)",
]
# 旧库可能因“任意一份获批即可导出”遗留多份批准记录；先回填取代关系，再建唯一生效索引。
BACKFILL_STATEMENTS=[
    """UPDATE investigations i SET superseded_by=latest.id, superseded_at=''
       FROM (SELECT run_id, MAX(id) AS id FROM investigations WHERE status='approved' GROUP BY run_id) latest
       WHERE i.run_id=latest.run_id AND i.status='approved' AND i.id<>latest.id AND i.superseded_by IS NULL""",
    "CREATE UNIQUE INDEX IF NOT EXISTS investigation_open_reconsideration_idx ON investigations (run_id) WHERE kind='reconsideration' AND status='submitted'",
    "CREATE UNIQUE INDEX IF NOT EXISTS investigation_effective_idx ON investigations (run_id) WHERE status='approved' AND superseded_by IS NULL",
]

def upgrade_schema(engine):
    if engine.dialect.name!="postgresql":return
    with engine.begin() as conn:
        if not inspect(conn).has_table("investigations"):return
        for statement in MIGRATION_STATEMENTS+BACKFILL_STATEMENTS:
            conn.execute(text(statement))
