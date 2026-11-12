import {FormEvent,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {Download,Check,Undo2,Flag} from 'lucide-react';
import {useProcessData} from '../hooks/useProcess';
import {useAuth} from '../stores/auth';
import {useAction} from '../hooks/useAction';
import {submitInvestigation,startReconsideration,reviewInvestigation} from '../api/investigations';
import {download} from '../api/client';
import {Notice} from '../components/common/Notice';
import {RunSummary} from '../components/RunSummary';
import {ReleaseStatus} from '../components/ReleaseStatus';
import {ReviewStatus,InvestigationKind} from '../constants/enums';
import {time} from '../utils/format';
import {Investigation} from '../types/domain';

export function Reviews(){
  const s=useProcessData(),{user}=useAuth(),a=useAction(),[params]=useSearchParams();
  const [selected,setSelected]=useState(Number(params.get('run'))||0);
  const [title,setTitle]=useState(''),[finding,setFinding]=useState(''),[action,setAction]=useState('');
  const [notes,setNotes]=useState<Record<number,string>>({}),[subject,setSubject]=useState(0);
  const runs=s.runs.filter(r=>r.status==='completed'),run=runs.find(r=>r.id===selected)||runs[0];
  const records=run?s.investigations.filter(i=>i.run_id===run.id):[];
  const effective=records.find(i=>i.effective);
  const pending=records.find(i=>i.kind==='reconsideration'&&i.status==='submitted');
  // 存在生效结论时，新调查只能作为复议提交，默认指向当前生效结论。
  const target=subject||effective?.id||0;
  const canEdit=user?.role==='admin'||user?.role==='analyst';
  const canSubmit=canEdit&&!pending;

  function submit(e:FormEvent){
    e.preventDefault();
    a.execute(async()=>{
      try{
        if(target)await startReconsideration(target,{title,finding,action});
        else await submitInvestigation({run_id:run!.id,title,finding,action});
        setTitle('');setFinding('');setAction('');setSubject(0);
      }finally{await s.refresh()}
    });
  }
  function decide(i:Investigation,status:'approved'|'rejected'){
    a.execute(async()=>{try{await reviewInvestigation(i.id,{status,review_note:notes[i.id]})}finally{await s.refresh()}});
  }
  function reconsider(i:Investigation){
    setSubject(i.id);
    setTitle(`对 INV-${i.id} 的复议`);
    document.querySelector<HTMLInputElement>('input[aria-label="调查标题"]')?.focus();
  }
  function changeRun(id:number){setSelected(id);setSubject(0)}

  return <div className="page">
    <div className="page-title"><div><p className="eyebrow">INVESTIGATION & RELEASE / 05</p><h1>调查与复核<span>审批的是研究记录，不是对过程能力的保证。</span></h1></div></div>
    <Notice message={s.error||a.error} retry={s.refresh}/>
    <label>关联运行<select aria-label="关联运行" value={run?.id||''} onChange={e=>changeRun(Number(e.target.value))}>{runs.map(r=><option key={r.id} value={r.id}>#{r.id} / {r.name}</option>)}</select></label>
    {run&&<RunSummary run={run}/>}
    {run&&<section className="release-panel">
      <div className="release-heading"><span className="eyebrow">EFFECTIVE & RELEASE / 生效与导出</span><button className="primary" disabled={!run.export_allowed||a.busy} onClick={()=>a.execute(async()=>{await download(`/runs/${run.id}/export`,`process-run-${run.id}.csv`)})}><Download size={14}/>{run.export_allowed?'下载生效档案 CSV':'导出暂停'}</button></div>
      <ReleaseStatus run={run} investigations={records}/>
    </section>}
    <div className="reviews-grid">
      <section className="investigation-form">
        <h2>{target?'发起复议':'提交调查记录'}</h2>
        {pending&&<p className="reconsider-note"><Flag size={14}/>已有待复核复议 INV-{pending.id}；该运行导出已暂停。请先完成该复议，退回后可再次发起。</p>}
        {!canEdit?<p className="role-note">观察员可阅读调查、当前生效结论与复议状态；导出开放时可下载对应运行的CSV。</p>:
          !canSubmit?null:<form onSubmit={submit}>
            {target&&<p className="reconsider-note"><Flag size={14}/>对 INV-{target} 发起复议：提交即暂停本运行导出；复议获批后才替换生效结论，退回则保持暂停。原调查与档案保留。</p>}
            <label>调查标题<input aria-label="调查标题" minLength={2} value={title} onChange={e=>setTitle(e.target.value)} required placeholder="例如：T-03 后段均值偏移调查"/></label>
            <label>信号判断<textarea aria-label="信号判断" minLength={8} value={finding} onChange={e=>setFinding(e.target.value)} required placeholder="说明信号位置、基线适用性及能力解释边界。"/></label>
            <label>复查动作<textarea aria-label="复查动作" minLength={8} value={action} onChange={e=>setAction(e.target.value)} required placeholder="记录下一步采样或工艺检查，不自动控制设备。"/></label>
            <button className="primary" disabled={a.busy||!run}>{target?'提交复议并暂停导出':'提交负责人复核'}</button>
          </form>}
      </section>
      <section className="investigation-list">
        <h2>复核档案</h2>
        <p className="caption">{records.length} 份调查记录 / 同一运行仅一份生效结论；被取代的批准记录继续留档。</p>
        {records.map(i=><article key={i.id} className={i.effective?'is-effective':i.superseded?'is-superseded':undefined}>
          <div className="investigation-title">
            <span className="eyebrow">INV-{i.id} / RUN-{i.run_id}{i.kind==='reconsideration'?` / 复议对 INV-${i.subject_id}`:''}</span>
            <span className="archive-flags">
              {i.effective&&<span className="review-badge effective">当前生效</span>}
              {i.superseded&&<span className="review-badge superseded">已被取代{i.superseded_by?` · INV-${i.superseded_by}`:''}</span>}
              {i.kind==='reconsideration'&&<span className="review-badge reconsideration">{InvestigationKind.reconsideration}</span>}
              <span className={'review-badge '+i.status}>{ReviewStatus[i.status as keyof typeof ReviewStatus]}</span>
            </span>
          </div>
          <h3>{i.title}</h3>
          <p><b>判断</b>{i.finding}</p>
          <p><b>动作</b>{i.action}</p>
          <small>{i.owner} · {time(i.created_at)}</small>
          {i.status==='submitted'&&user?.role==='admin'&&(effective&&i.kind!=='reconsideration'?
            <div className="approval-form">
              <p className="role-note">该调查早于当前生效结论；不能直接替换生效结论，请退回或另发起复议。</p>
              <label>复核意见<textarea aria-label={'复核意见 '+i.id} value={notes[i.id]||''} onChange={e=>setNotes(n=>({...n,[i.id]:e.target.value}))} minLength={8} placeholder="至少8字，记录退回依据。"/></label>
              <button className="outline" disabled={a.busy||(notes[i.id]||'').length<8} onClick={()=>decide(i,'rejected')}><Undo2 size={14}/>退回调查</button>
            </div>:
            <div className="approval-form">
              <label>复核意见<textarea aria-label={'复核意见 '+i.id} value={notes[i.id]||''} onChange={e=>setNotes(n=>({...n,[i.id]:e.target.value}))} minLength={8} placeholder="至少8字，记录批准或退回依据。"/></label>
              <div>
                <button className="primary" disabled={a.busy||(notes[i.id]||'').length<8} onClick={()=>decide(i,'approved')}><Check size={14}/>{i.kind==='reconsideration'?'批准复议并替换结论':'批准归档'}</button>
                <button className="outline" disabled={a.busy||(notes[i.id]||'').length<8} onClick={()=>decide(i,'rejected')}><Undo2 size={14}/>{i.kind==='reconsideration'?'退回复议':'退回调查'}</button>
              </div>
              <small>两位负责人同时复核时只接受首个决定；后到请求会被拒绝。</small>
            </div>)}
          {i.status!=='submitted'&&<div className="review-note"><b>{i.reviewer}</b><p>{i.review_note}</p></div>}
          {i.effective&&canEdit&&!pending&&<button className="text-link" onClick={()=>reconsider(i)}><Flag size={14}/>对此生效结论发起复议</button>}
        </article>)}
        {!records.length&&<p className="empty">此运行尚无调查。分析师提交记录后，负责人可审批，批准后开放导出；批准后的相反结论须以复议提交，并立即暂停导出。</p>}
      </section>
    </div>
  </div>;
}
