import {formatDimension} from './dimensionPlacement';
export const shareToken = new URLSearchParams(location.search).get('share');
export function fileURL(id: string) {return `/api/files/${id}${shareToken ? `?share=${encodeURIComponent(shareToken)}` : ''}`;}
export async function api<T = any>(path: string, method = 'GET', data?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api' + path, {method, signal, headers: data instanceof FormData ? undefined : data === undefined ? undefined : {'Content-Type': 'application/json'}, body: data instanceof FormData ? data : data === undefined ? undefined : JSON.stringify(data)});
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : body.detail?.map((v: any) => v.msg).join(';') || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}
export async function waitJob(id: string, signal?: AbortSignal) {
  for (;;) {
    signal?.throwIfAborted();
    const job = await api(`/jobs/${id}`);
    if (job.status === 'completed') return job.result;
    if (job.status === 'failed' || job.status === 'cancelled') throw new Error(job.error || 'Processing cancelled.');
    await new Promise(resolve => setTimeout(resolve, 700));
  }
}
export type Dimension = {annotation?:{offset:number[];label:number[]};reference_plane?:{origin:number[];normal:number[]};entities?:{kind:string;id:number}[];relation?:string;alternatives?:string[];labelPosition?:number[];id: string; label: string; value_mm: number; type?: string; p1: number[]; p2: number[]; basis: string; method?: string; faces?: number[]};
export type Model = {file_id: string; name: string; format: string; result: any; state?: any; project?: any; editable?: boolean; dirty?:boolean};
export function dimensionValue(d: Dimension, unit: string) {return formatDimension(d.value_mm, d.type, unit);}
