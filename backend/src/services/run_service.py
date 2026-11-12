import csv,io
from redis import Redis
from fastapi import HTTPException
from ..config.settings import REDIS_URL
from ..models import ControlRun,Baseline
from ..utils.serialize import record
from .audit_service import log
from .investigation_service import effective_investigation,latest_reconsideration,reconsideration_state,export_hold
queue=Redis.from_url(REDIS_URL,decode_responses=True)

def serialize_run(db,row):
    data=record(row)
    effective=effective_investigation(db,row.id)
    reconsideration=latest_reconsideration(db,row.id)
    data["effective_investigation_id"]=effective.id if effective else None
    data["reconsideration_status"]=reconsideration_state(db,row.id)
    data["export_hold"]=export_hold(db,row.id)
    data["export_allowed"]=row.status=="completed" and effective is not None and not data["export_hold"]
    if reconsideration:
        data["reconsideration_id"]=reconsideration.id
        data["reconsideration_title"]=reconsideration.title
    else:
        data["reconsideration_id"]=None
        data["reconsideration_title"]=""
    return data

def list_runs(db):return [serialize_run(db,r) for r in db.query(ControlRun).order_by(ControlRun.id.desc())]
def get_run(db,rid):
    row=db.get(ControlRun,rid)
    if not row:raise HTTPException(404,"运行不存在")
    return row

def create_run(db,data,user):
    if not db.get(Baseline,data.baseline_id):raise HTTPException(404,"基线不存在")
    row=ControlRun(**data.model_dump(),owner=user.name)
    db.add(row);db.flush();log(db,user.email,"control.enqueue",row.id);db.commit()
    try:queue.rpush("process:jobs",row.id)
    except Exception:
        row.status="failed";row.error="队列不可用，请重新提交";db.commit();raise HTTPException(503,row.error)
    return serialize_run(db,row)

def export_run(db,rid,actor=None):
    row=get_run(db,rid)
    if row.status!="completed":raise HTTPException(409,"运行尚未完成")
    effective=effective_investigation(db,rid)
    if not effective:raise HTTPException(403,"调查尚未经负责人批准，不能导出")
    state=reconsideration_state(db,rid)
    if state=="submitted":raise HTTPException(409,"该运行有未决复议，导出已暂停；复议获批后恢复")
    if state=="rejected":raise HTTPException(409,"该运行的复议已退回，导出仍暂停；需新的复议获批后恢复")
    if actor:log(db,actor,"run.export",rid);db.commit()
    out=io.StringIO();writer=csv.writer(out)
    # 档案头明确当前生效结论与复议状态，确保导出文件自身可辨明。
    writer.writerow(['# effective_investigation','INV-%d'%effective.id])
    writer.writerow(['# effective_title',effective.title])
    writer.writerow(['# effective_owner',effective.owner])
    writer.writerow(['# effective_reviewer',effective.reviewer])
    writer.writerow(['# effective_reviewed_at',effective.reviewed_at])
    writer.writerow(['# reconsideration_status',state])
    writer.writerow(['sequence','time','thickness','moving_range','ewma','ewma_lower','ewma_upper','signals','input_hash'])
    for p in row.result['points']:writer.writerow([p['sequence'],p['measured_at'],p['value'],p['moving_range'],p['ewma'],p['ewma_lower'],p['ewma_upper'],'|'.join(p['signals']),row.result['input_hash']])
    return out.getvalue(),{"X-Effective-Investigation":str(effective.id),"X-Reconsideration-Status":state}
