from sqlalchemy import ForeignKey,Index,text
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class Investigation(Base):
    __tablename__="investigations"
    __table_args__=(
        Index("investigation_run_kind_status_idx","run_id","kind","status"),
        Index(
            "investigation_open_reconsideration_idx",
            "run_id",
            unique=True,
            postgresql_where=text("kind='reconsideration' AND status='submitted'"),
            sqlite_where=text("kind='reconsideration' AND status='submitted'"),
        ),
        Index(
            "investigation_effective_idx",
            "run_id",
            unique=True,
            postgresql_where=text("status='approved' AND superseded_by IS NULL"),
            sqlite_where=text("status='approved' AND superseded_by IS NULL"),
        ),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("control_runs.id"))
    title:Mapped[str]
    finding:Mapped[str]
    action:Mapped[str]
    status:Mapped[str]=mapped_column(default="submitted")
    # initial: 首次调查；reconsideration: 对当前生效结论发起的复议
    kind:Mapped[str]=mapped_column(default="initial")
    # 复议所针对的生效调查（仅 kind=reconsideration 时有值）
    subject_id:Mapped[int|None]=mapped_column(ForeignKey("investigations.id"),nullable=True)
    # 被更新的批准结论取代后保留原记录，仅标记取代关系
    superseded_by:Mapped[int|None]=mapped_column(ForeignKey("investigations.id"),nullable=True)
    superseded_at:Mapped[str]=mapped_column(default="")
    owner:Mapped[str]
    reviewer:Mapped[str]=mapped_column(default="")
    review_note:Mapped[str]=mapped_column(default="")
    created_at:Mapped[str]=mapped_column(default=now)
    reviewed_at:Mapped[str]=mapped_column(default="")
