-- 复议与生效结论：为已有数据库补充调查归档字段。
-- 新库由 SQLAlchemy metadata 建表；已部署库请审查后执行本迁移。
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS kind VARCHAR NOT NULL DEFAULT 'initial';
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS subject_id INTEGER REFERENCES investigations(id);
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS superseded_by INTEGER REFERENCES investigations(id);
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS superseded_at VARCHAR NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS investigation_run_kind_status_idx ON investigations (run_id, kind, status);
-- 同一运行只允许一条待复核复议；复议退回或获批后允许再次发起。
CREATE UNIQUE INDEX IF NOT EXISTS investigation_open_reconsideration_idx
    ON investigations (run_id) WHERE kind='reconsideration' AND status='submitted';
-- 旧库可能曾因“任意一份获批即可导出”而遗留多份批准记录；只保留最新一份为生效结论。
WITH latest AS (
    SELECT run_id, MAX(id) AS id FROM investigations WHERE status='approved' GROUP BY run_id
)
UPDATE investigations i SET superseded_by=latest.id, superseded_at=''
FROM latest
WHERE i.run_id=latest.run_id AND i.status='approved' AND i.id<>latest.id AND i.superseded_by IS NULL;
-- 每个运行至多一份生效结论。
CREATE UNIQUE INDEX IF NOT EXISTS investigation_effective_idx
    ON investigations (run_id) WHERE status='approved' AND superseded_by IS NULL;

