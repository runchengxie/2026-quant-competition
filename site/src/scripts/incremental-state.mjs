export function formatResearchNumber(value,locale='en',missing='Unavailable'){
 return value==null?missing:new Intl.NumberFormat(locale,{maximumSignificantDigits:6}).format(Object.is(value,-0)?0:value);
}
export function equitySeries(facts,model,foldIndex){
 const fold=facts.equity.folds[foldIndex];
 const own=fold.models.find(row=>row.model===model)?.metrics?.daily??[];
 const reference=new Map((fold.models.find(row=>row.model==='reversal')?.metrics?.daily??[]).map(row=>[row.date,row]));
 return {dates:own.map(row=>row.date),differences:own.map(row=>{
  const ref=reference.get(row.date);
  return row.rank_ic==null||ref?.rank_ic==null?null:row.rank_ic-ref.rank_ic;
 }),counts:own.map(row=>row.count)};
}
export function cryptoPoints(facts,fee){
 return facts.crypto.jobs.filter(row=>row.fee_bps===Number(fee)).map(row=>({arm:row.arm,window:row.window_id,value:[row.metrics.turnover,row.metrics.net_return*100]}));
}
