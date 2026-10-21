/** Selection over reviewed aggregates only; no portfolio arithmetic or fold stitching. */
export function selectAblations(snapshot,selection){
 if(!selection||!["US","HK","crypto"].includes(selection.market))return [];
 if(selection.feeBps!==undefined&&(typeof selection.feeBps!=="number"||!Number.isFinite(selection.feeBps)))return [];
 return (snapshot?.results??[]).filter(r=>r.market===selection.market&&(selection.feeBps===undefined||r.cost_bps===selection.feeBps)&&(selection.strategy===undefined||r.strategy===selection.strategy)&&(selection.variantId===undefined||r.variant_id===selection.variantId)&&(selection.windowStart===undefined||r.start===selection.windowStart));
}
const median=values=>{const a=values.filter(v=>typeof v==="number"&&Number.isFinite(v)).sort((a,b)=>a-b);return !a.length?null:a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2;};
export function summarizeAblations(snapshot,selection){
 const rows=selectAblations(snapshot,selection).filter(r=>r.status==="completed");
 if(new Set(rows.map(r=>r.quote_currency)).size>1)throw Error("Mixed currency summary");
 const groups=new Map();
 for(const row of rows){const key=JSON.stringify([row.strategy,row.variant_id,row.cost_bps]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 return [...groups.values()].map(group=>{
  const row=group[0];if(new Set(group.map(r=>r.evidence_role)).size!==1)throw Error("Mixed evidence role");
  return {strategy:row.strategy,variant_id:row.variant_id,evidence_role:row.evidence_role,cost_bps:row.cost_bps,count:group.length,median_net_return:median(group.map(r=>r.net_return)),median_excess_return:median(group.map(r=>r.excess_return)),median_paired_net_change:median(group.map(r=>r.paired_net_change)),median_paired_drawdown_change:median(group.map(r=>r.paired_drawdown_change)),median_daily_turnover:median(group.map(r=>r.mean_daily_oneway_turnover_proxy)),median_exposure:median(group.map(r=>r.mean_exposure))};
 }).sort((a,b)=>a.strategy.localeCompare(b.strategy)||a.variant_id.localeCompare(b.variant_id)||a.cost_bps-b.cost_bps);
}
