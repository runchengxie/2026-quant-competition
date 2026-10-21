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

function uniqueResult(rows){
 if(rows.length>1)throw Error('Duplicate result for comparison condition');
 return rows[0]??null;
}
function compatibleWindow(a,b){
 return ['market','start','end','quote_currency','plan_sha256','accounting_model','sessions','periods_per_year','benchmark'].every(key=>a[key]===b[key]);
}

/** At most three strategies under one reference condition; unknowns remain unavailable. */
export function compareStrategies(study,series,selection,strategies){
 const ids=[...new Set(strategies.filter(Boolean))];if(ids.length>3)throw Error('Select at most three strategies');
 const candidates=selectResults(study,selection);
 const start=selection.windowStart??candidates[0]?.start;
 const reference=uniqueResult(candidates.filter(r=>r.start===start));
 if(!reference)return {reference:null,entries:[]};
 const entries=ids.map(strategy=>{
  const candidate=uniqueResult(selectResults(study,{...selection,strategy}).filter(r=>r.start===reference.start&&r.end===reference.end));
  const result=candidate&&compatibleWindow(reference,candidate)?candidate:null;
  return {strategy,result,curve:result?selectSeries(series,result.job_id):null};
 });
 const grid=entries.find(e=>e.curve)?.curve.points.map(p=>p.date);
 for(const entry of entries){
  if(entry.curve&&(entry.curve.points.length!==grid.length||entry.curve.points.some((p,i)=>p.date!==grid[i])))entry.curve=null;
 }
 return {reference,entries};
}

/** All declared fees, intersected on identical windows and accounting inputs. */
export function summarizeFeeRobustness(study,selection){
 const rows=study.results.filter(r=>r.status==='completed'&&r.market===selection.market&&r.strategy===selection.strategy);
 const fees=[...new Set(rows.map(r=>r.cost_bps))].sort((a,b)=>a-b);
 if(new Set(rows.map(r=>r.quote_currency)).size>1)throw Error('Mixed currency fee summary');
 const key=r=>JSON.stringify([r.start,r.end,r.plan_sha256,r.accounting_model,r.quote_currency,r.sessions,r.periods_per_year,r.benchmark,r.products]);
 const groups=fees.map(fee=>{const group=new Map();for(const row of rows.filter(r=>r.cost_bps===fee)){const id=key(row);if(group.has(id))throw Error('Duplicate result for fee window');group.set(id,row);}return group;});
 const union=new Set(groups.flatMap(g=>[...g.keys()]));
 const common=[...union].filter(k=>groups.every(g=>g.has(k)));
 return {matchedWindows:common.length,excludedWindows:union.size-common.length,fees:fees.map((feeBps,i)=>{
  const matched=common.map(k=>groups[i].get(k));
  return {feeBps,summary:summarizeWindows({results:matched},{...selection,feeBps}),positiveNetCount:matched.filter(r=>r.net_return>0).length};
 })};
}
