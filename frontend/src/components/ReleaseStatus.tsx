import {Run,Investigation} from '../types/domain';
import {ReconsiderationStatus} from '../constants/enums';
import {time} from '../utils/format';

export function releaseNote(run:Pick<Run,'effective_investigation_id'|'reconsideration_status'|'reconsideration_id'>,compact=false){
  if(!run.effective_investigation_id)return compact?'尚无生效结论，导出关闭。':'尚无生效结论；需先批准一份调查，导出才开放。';
  if(run.reconsideration_status==='submitted')return compact?`复议 INV-${run.reconsideration_id} 待复核；导出暂停。`:`复议 INV-${run.reconsideration_id} 待复核；导出已暂停，复议获批后才恢复。`;
  if(run.reconsideration_status==='rejected')return compact?`复议 INV-${run.reconsideration_id} 已退回；导出保持暂停。`:`复议 INV-${run.reconsideration_id} 已退回；导出保持暂停，原生效结论与档案仍保留。`;
  if(run.reconsideration_status==='approved')return compact?`复议 INV-${run.reconsideration_id} 已获批；导出开放。`:`复议 INV-${run.reconsideration_id} 已获批，已替换生效结论；导出开放。`;
  return compact?'无复议；当前结论可导出。':'无复议；当前生效结论可导出。';
}

export function ReleaseStatus({run,investigations}:{run:Run;investigations:Investigation[]}){
  const effective=investigations.find(i=>i.run_id===run.id&&i.effective);
  return <div className="release-status">
    <div><span>当前生效结论</span><b>{effective?`INV-${effective.id} · ${effective.title}`:'尚无生效结论'}</b><small>{effective?`${effective.reviewer} 于 ${time(effective.reviewed_at)} 批准`:'尚未批准任何调查。'}</small></div>
    <div><span>复议状态</span><b className={run.export_hold?'alert':'safe'}>{ReconsiderationStatus[run.reconsideration_status as keyof typeof ReconsiderationStatus]}</b><small>{releaseNote(run)}</small></div>
  </div>;
}
