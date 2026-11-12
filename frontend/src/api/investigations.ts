import {request} from './client';import {Investigation} from '../types/domain';
type InvestigationBody={title:string;finding:string;action:string};
export const getInvestigations=()=>request<Investigation[]>('/investigations');
export const submitInvestigation=(data:InvestigationBody&{run_id:number})=>request<Investigation>('/investigations',{method:'POST',body:JSON.stringify(data)});
export const startReconsideration=(subjectId:number,data:InvestigationBody)=>request<Investigation>(`/investigations/${subjectId}/reconsider`,{method:'POST',body:JSON.stringify(data)});
export const reviewInvestigation=(id:number,data:{status:string;review_note:string})=>request<Investigation>(`/investigations/${id}/review`,{method:'PATCH',body:JSON.stringify(data)});
