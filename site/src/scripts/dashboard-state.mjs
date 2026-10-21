/** Pure selection over published facts; no portfolio calculation or fold stitching. */
export function selectResults(snapshot,selection) {
  if(!selection || typeof selection.feeBps!=="number" || !Number.isFinite(selection.feeBps)) return [];
  return snapshot.results.filter(row=>row.status==="completed" && row.market===selection.market && row.strategy===selection.strategy && row.cost_bps===selection.feeBps)
    .sort((a,b)=>b.start.localeCompare(a.start));
}

export function selectSeries(snapshot,jobId) {
  return snapshot?.series?.find(curve=>curve.job_id===jobId)??null;
}

export function selectWindowOptions(rows) {
  const windows=new Map(rows.map(row=>[row.start,{start:row.start,end:row.end}]));
  return [...windows.values()].sort((a,b)=>b.start.localeCompare(a.start));
}

function distribution(rows) {
  if(!rows.length) return [];
  const values=rows.map(row=>row.net_return);
  let low=Math.min(...values),high=Math.max(...values);
  if(low===high){low-=.005;high+=.005;}
  const width=(high-low)/6;
  const bins=Array.from({length:6},(_,i)=>({low:low+i*width,high:low+(i+1)*width,count:0}));
  for(const value of values) bins[Math.min(5,Math.floor((value-low)/width))].count++;
  return bins;
}

export function deriveChartModels(study,series,selection) {
  const rows=selectResults(study,selection);
  const selected=selection.windowStart?rows.find(row=>row.start===selection.windowStart)??null:rows[0]??null;
  return {
    rows,selected,curve:selected?selectSeries(series,selected.job_id):null,
    foldReturns:[...rows].reverse(),
    feeSensitivity:selected?study.results.filter(row=>row.status==="completed" && row.market===selected.market && row.strategy===selected.strategy && row.start===selected.start && row.end===selected.end).sort((a,b)=>a.cost_bps-b.cost_bps):[],
    scatter:study.results.filter(row=>row.status==="completed" && row.market===selection.market && row.cost_bps===selection.feeBps),
    histogram:distribution(rows),
  };
}

/** Descriptive statistics over separate published windows, never an account return. */
export function summarizeWindows(snapshot,selection){
 const rows=selectResults(snapshot,selection);if(!rows.length)return null;
 const currencies=new Set(rows.map(r=>r.quote_currency));if(currencies.size!==1)throw Error('Mixed currency summary');
 const median=values=>{const a=values.filter(Number.isFinite).sort((a,b)=>a-b);return !a.length?null:a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2;};
 const excess=rows.map(r=>r.excess_return).filter(Number.isFinite);
 const positiveExcessCount=excess.filter(v=>v>0).length;
 return {count:rows.length,excessCount:excess.length,positiveExcessCount,positiveExcessRate:excess.length?positiveExcessCount/excess.length:null,medianNetReturn:median(rows.map(r=>r.net_return)),medianExcessReturn:median(excess),worstNetReturn:Math.min(...rows.map(r=>r.net_return)),medianCostDrag:median(rows.map(r=>r.cost_drag)),quoteCurrency:rows[0].quote_currency};
}
