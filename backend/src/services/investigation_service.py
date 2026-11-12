from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from ..models import Investigation,ControlRun
from ..utils.serialize import record
from ..utils.clock import now
from .audit_service import log

# 同一运行同时只允许一条待复核的复议；库层部分唯一索引与业务校验各一道。
def pending_reconsideration(db,run_id):
    return db.query(Investigation).filter_by(run_id=run_id,kind="reconsideration",status="submitted").first()

def effective_investigation(db,run_id):
    """当前生效结论：最近一次批准且未被后续批准取代的调查。"""
    return (db.query(Investigation)
        .filter_by(run_id=run_id,status="approved")
        .filter(Investigation.superseded_by.is_(None))
        .order_by(Investigation.id.desc()).first())

def latest_reconsideration(db,run_id):
    return (db.query(Investigation)
        .filter_by(run_id=run_id,kind="reconsideration")
        .order_by(Investigation.id.desc()).first())

def reconsideration_state(db,run_id):
    rec=latest_reconsideration(db,run_id)
    return rec.status if rec else "none"

def export_hold(db,run_id):
    """复议待复核或其被退回时导出暂停；只有复议获批才解除。"""
    return reconsideration_state(db,run_id) in ("submitted","rejected")

def investigation_view(row,effective_id=None):
    data=record(row)
    data["effective"]=row.id==effective_id
    data["is_effective"]=data["effective"]
    # 兼容旧库中同一运行存在多份批准记录的情况：仅最新一份生效，其余按已被取代展示。
    data["superseded"]=bool(row.superseded_by) or (row.status=="approved" and effective_id is not None and row.id!=effective_id)
    data["reconsideration_state"]=row.status if row.kind=="reconsideration" else "none"
    return data

def list_investigations(db):
    rows=db.query(Investigation).order_by(Investigation.id.desc()).all()
    effective={}
    for row in rows:
        if row.status=="approved" and row.superseded_by is None and row.run_id not in effective:
            effective[row.run_id]=row.id
    return [investigation_view(row,effective.get(row.run_id)) for row in rows]

def _lock_run(db,run_id):
    return db.query(ControlRun).filter_by(id=run_id).with_for_update().first()

def _ensure_completed(run):
    if not run or run.status!="completed":raise HTTPException(409,"只能对已完成运行建立调查")

def _new_reconsideration(db,run,subject,data,user):
    if pending_reconsideration(db,run.id):
        raise HTTPException(409,"该运行已有待复核的复议，请先完成该复议")
    row=Investigation(run_id=run.id,title=data.title,finding=data.finding,action=data.action,
        owner=user.name,status="submitted",kind="reconsideration",subject_id=subject.id)
    db.add(row);db.flush()
    log(db,user.email,"investigation.reconsider",row.id)
    return row

def create_investigation(db,data,user):
    run=_lock_run(db,data.run_id);_ensure_completed(run)
    # 运行已有生效结论时，新的调查即为复议；提交即暂停导出，直到复议获批。
    subject=effective_investigation(db,run.id)
    try:
        if subject:
            row=_new_reconsideration(db,run,subject,data,user)
        else:
            row=Investigation(**data.model_dump(),owner=user.name,status="submitted",kind="initial")
            db.add(row);db.flush()
            log(db,user.email,"investigation.submit",row.id)
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"该运行已有待复核的复议，请先完成该复议")
    effective=effective_investigation(db,row.run_id)
    return investigation_view(row,effective.id if effective else None)

def create_reconsideration(db,subject_id,data,user):
    subject=db.get(Investigation,subject_id)
    if not subject:raise HTTPException(404,"调查记录不存在")
    run=_lock_run(db,subject.run_id);_ensure_completed(run)
    subject=db.query(Investigation).filter_by(id=subject_id).with_for_update().populate_existing().first()
    current=effective_investigation(db,subject.run_id)
    if not current or current.id!=subject.id:
        raise HTTPException(409,"只能对当前生效结论发起复议")
    try:
        row=_new_reconsideration(db,run,subject,data,user)
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"该运行已有待复核的复议，请先完成该复议")
    return investigation_view(row,current.id)

def review_investigation(db,iid,data,user):
    row=db.get(Investigation,iid)
    if not row:raise HTTPException(404,"调查记录不存在")
    # 按运行串行化复核，保证同一运行的“生效结论”唯一；再锁调查记录，
    # 两位负责人同时提交相反意见时，后到的请求只能看到已复核状态并收到 409。
    _lock_run(db,row.run_id)
    row=db.query(Investigation).filter_by(id=iid).with_for_update().populate_existing().first()
    if row.status!="submitted":raise HTTPException(409,"该调查已复核，仅接受首个决定")
    if data.status=="approved" and row.kind!="reconsideration":
        # 已有生效结论时，只能由针对该结论的复议获批来替换，旧待复核调查不能绕过复议。
        if effective_investigation(db,row.run_id):
            raise HTTPException(409,"该运行已有生效结论，须发起复议并获批后才能替换")
    decided=now()
    if data.status=="approved":
        # 先取代旧批准，再写入本次批准，避免出现两份同时生效的批准记录。
        superseded=(db.query(Investigation)
            .filter(Investigation.run_id==row.run_id,
                Investigation.status=="approved",
                Investigation.id!=row.id,
                Investigation.superseded_by.is_(None))
            .update({"superseded_by":row.id,"superseded_at":decided},synchronize_session="fetch"))
        if superseded:log(db,user.email,"investigation.superseded",row.id)
    # 条件更新是最后一道“首个决定”闸门：即使数据库不支持行锁，
    # 第二个相反意见也无法把已复核记录改回 submitted 后再覆盖。
    claimed=(db.query(Investigation)
        .filter_by(id=iid,status="submitted")
        .update({"status":data.status,"review_note":data.review_note,
            "reviewer":user.name,"reviewed_at":decided},synchronize_session="fetch"))
    if not claimed:
        db.rollback();raise HTTPException(409,"该调查已复核，仅接受首个决定")
    log(db,user.email,"investigation."+data.status,row.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"该运行已有生效结论，请先完成复议")
    effective=effective_investigation(db,row.run_id)
    return investigation_view(row,effective.id if effective else None)
