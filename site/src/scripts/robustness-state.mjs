const metricKeys='periods net_return gross_return cost_drag volatility sharpe max_drawdown turnover total_costs mean_daily_turnover mean_exposure flat_days'.split(' ');
const rowKeys='job_id market arm_id pool_id fee_bps start end status reason metrics benchmark baseline_net_return'.split(' ');
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
const validMetrics=m=>exact(m,metricKeys)&&metricKeys.every(k=>k==='sharpe'&&m[k]===null||finite(m[k]));
const fail=()=>{throw new Error('Invalid robustness snapshot');};
export const median=values=>{const a=[...values].sort((a,b)=>a-b);return a.length?(a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2):null;};

export function validateRobustnessSnapshot(value){
 const keys='schema status as_of code_commit plan_sha256 coverage results us_pairs crypto_pairs capacity blockers restrictions'.split(' ');
 if(!exact(value,keys)||value.schema!=='competition.public_strategy_robustness.v1'||!['measured','readiness_only'].includes(value.status))fail();
 const c=value.coverage;
 if(!exact(c,'requested_jobs completed_jobs blocked_jobs requested_capacity_checks completed_capacity_checks'.split(' '))||Object.values(c).some(n=>!Number.isInteger(n)||n<0)||c.requested_jobs!==114||c.requested_capacity_checks!==288||c.completed_jobs+c.blocked_jobs!==114)fail();
 for(const key of ['results','us_pairs','crypto_pairs','capacity','blockers','restrictions'])if(!Array.isArray(value[key]))fail();
 if(value.status==='readiness_only'){
  if(['results','us_pairs','crypto_pairs','capacity'].some(k=>value[k].length))fail();return value;
 }
 if(value.results.length!==114||value.capacity.length!==c.completed_capacity_checks||value.capacity.length>288)fail();
 const ids=new Map();let complete=0;
 for(const row of value.results){
  if(!exact(row,rowKeys)||typeof row.job_id!=='string'||!/^[a-f0-9]{64}$/.test(row.job_id)||ids.has(row.job_id)||!['US','crypto'].includes(row.market)||!Number.isInteger(row.fee_bps)||!(row.market==='US'?[20,40]:[35,50]).includes(row.fee_bps))fail();
  if(row.market==='US'&&(!['exclude_nvda','exclude_three','fixed_six'].includes(row.pool_id)||row.arm_id!=='ew_monthly'))fail();
  if(row.market==='crypto'&&(row.pool_id!=='existing_eight'||!['trend200_vol40_strict','ew_trend_gross_matched'].includes(row.arm_id)))fail();
  if(row.status==='completed'){
   if(!validMetrics(row.metrics)||!finite(row.baseline_net_return)||row.reason!==null||(row.market==='US'?!validMetrics(row.benchmark):row.benchmark!==null))fail();complete++;
  }else if(row.status!=='blocked'||row.metrics!==null||row.benchmark!==null||row.baseline_net_return!==null||typeof row.reason!=='string')fail();
  ids.set(row.job_id,row);
 }
 if(complete!==c.completed_jobs||value.results.filter(r=>r.market==='US').length!==66||value.results.filter(r=>r.market==='crypto').length!==48)fail();
 for(const pair of value.us_pairs){
  const row=ids.get(pair.job_id);if(!row||row.market!=='US'||pair.fee_bps!==row.fee_bps||pair.start!==row.start||!finite(pair.net_return_change)||!finite(pair.drawdown_change)||!finite(pair.spy_net_return_change))fail();
 }
 for(const pair of value.crypto_pairs){
  const a=ids.get(pair.candidate_job_id),b=ids.get(pair.control_job_id);
  if(!a||!b||a.market!=='crypto'||b.market!=='crypto'||a.fee_bps!==b.fee_bps||pair.fee_bps!==a.fee_bps||a.start!==b.start||!finite(pair.net_return_change)||!finite(pair.drawdown_change))fail();
 }
 const capacityIds=new Set();
 for(const row of value.capacity){
  const identity=`${row.job_id}|${row.notional_usdt}|${row.threshold}`;
  if(!exact(row,'job_id notional_usdt threshold status max_participation breach_days unavailable_days ex_post execution_eligible'.split(' '))||ids.get(row.job_id)?.market!=='crypto'||capacityIds.has(identity)||![10000,100000,1000000].includes(row.notional_usdt)||![.01,.05].includes(row.threshold)||row.ex_post!==true||row.execution_eligible!==false||!(row.max_participation===null||finite(row.max_participation)&&row.max_participation>=0)||!Number.isInteger(row.breach_days)||row.breach_days<0||!Number.isInteger(row.unavailable_days)||row.unavailable_days<0)fail();
  capacityIds.add(identity);
 }
 return value;
}

export function selectRobustness(snapshot,{market='US',feeBps,windowStart}={}){
 validateRobustnessSnapshot(snapshot);
 if(!['US','crypto'].includes(market))throw new Error('Unknown robustness market');
 return snapshot.results.filter(r=>r.market===market&&(feeBps===undefined||r.fee_bps===feeBps)&&(!windowStart||r.start===windowStart));
}

export function summarizeRobustness(snapshot,selection={}){
 const rows=selectRobustness(snapshot,selection),ids=new Set(rows.map(r=>r.job_id));
 const pairs=(selection.market==='crypto'?snapshot.crypto_pairs:snapshot.us_pairs).filter(p=>ids.has(p.job_id??p.candidate_job_id));
 const groups=new Map();
 for(const row of rows){
  const poolId=row.market==='US'?row.pool_id:'trend_vs_matched',key=`${poolId}|${row.fee_bps}`;
  if(!groups.has(key))groups.set(key,{poolId,feeBps:row.fee_bps,requested:new Set(),values:[]});
  groups.get(key).requested.add(row.start);
 }
 for(const pair of pairs){
  const row=rows.find(r=>r.job_id===(pair.job_id??pair.candidate_job_id));
  const poolId=row.market==='US'?row.pool_id:'trend_vs_matched';
  const key=`${poolId}|${pair.fee_bps}`;
  groups.get(key).values.push(pair);
 }
 return [...groups.values()].map(g=>({poolId:g.poolId,feeBps:g.feeBps,requestedWindows:g.requested.size,blockedWindows:g.requested.size-g.values.length,windows:g.values.length,returnWins:g.values.filter(p=>p.net_return_change>0).length,drawdownWins:g.values.filter(p=>p.drawdown_change<0).length,medianReturnChange:median(g.values.map(p=>p.net_return_change)),medianDrawdownChange:median(g.values.map(p=>p.drawdown_change))}));
}

export function robustnessHeadlines(snapshot){
 return [{market:'US',...summarizeRobustness(snapshot,{market:'US',feeBps:20}).find(g=>g.poolId==='exclude_three')},{market:'crypto',...summarizeRobustness(snapshot,{market:'crypto',feeBps:50})[0]}];
}

export function capacitySummary(snapshot,{notionalUsdt=100000,threshold=.01}={}){
 validateRobustnessSnapshot(snapshot);
 const rows=snapshot.capacity.filter(r=>r.notional_usdt===notionalUsdt&&r.threshold===threshold);
 const finiteRows=rows.filter(r=>finite(r.max_participation));
 return {accounts:rows.length,breachingAccounts:rows.filter(r=>r.breach_days>0).length,unavailableAccounts:rows.filter(r=>r.unavailable_days>0).length,maxParticipation:finiteRows.length?Math.max(...finiteRows.map(r=>r.max_participation)):null};
}
