/** Presentation of already published observations, never a new simulation. */
export function capitalCurve(points,currency){
 if(!['USD','HKD','USDT'].includes(currency))throw Error('Unsupported currency');
 if(points.some(p=>!Number.isFinite(p.net_nav)||!Number.isFinite(p.gross_nav)))throw Error('Invalid normalized curve');
 return {currency,initialCapital:10000,points:points.map(p=>({...p,net_capital:p.net_nav*10000,gross_capital:p.gross_nav*10000}))};
}

export function feeWindowCells(study,selection){
 const rows=study.results.filter(r=>r.market===selection.market&&r.strategy===selection.strategy);
 if(new Set(rows.map(r=>r.quote_currency)).size>1)throw Error('Mixed currency heatmap');
 const fees=[...new Set(rows.map(r=>r.cost_bps))].sort((a,b)=>a-b);
 const windows=[...new Set(rows.map(r=>r.start))].sort();
 const cells=windows.flatMap((windowStart,y)=>fees.map((feeBps,x)=>{
  const found=rows.filter(r=>r.start===windowStart&&r.cost_bps===feeBps);
  if(found.length>1)throw Error('Duplicate heatmap condition');
  return {x,y,windowStart,feeBps,result:found[0]?.status==='completed'?found[0]:null};
 }));
 return {fees,windows,cells,currency:rows[0]?.quote_currency??null,coverage:{requested:rows.length,valid:rows.filter(r=>r.status==='completed').length,blocked:rows.filter(r=>r.status!=='completed').length,missing:cells.length-rows.length}};
}
