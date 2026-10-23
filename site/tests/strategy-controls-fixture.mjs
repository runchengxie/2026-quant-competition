/** Synthetic contract vectors only. Never imported by production pages. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
export function controlsFixture(){
 const base=JSON.parse(readFileSync(new URL('../src/data/strategy-controls.v1.json',import.meta.url),'utf8'));
 const rows=[['US','ew_monthly',20,.02,.03],['US','ew_monthly_buffer20',20,.025,.01],['US','ew_monthly',40,.01,.03],['US','ew_monthly_buffer20',40,.02,.01],['crypto','ew_legacy',10,.04,.02],['crypto','ew_legacy',25,.03,.02]].map(([market,arm,fee,net,turnover],i)=>({
  job_id:'1'.repeat(63)+(i+1).toString(16),market,arm_id:arm,fee_bps:fee,quote_currency:market==='US'?'USD':'USDT',start:'2024-01-02',end:'2024-03-30',
  metrics:{periods:market==='US'?63:90,net_return:net,gross_return:.05,cost_drag:.05-net,volatility:.2,sharpe:.3,max_drawdown:arm.includes('buffer')?.09:.1,turnover:turnover*(market==='US'?63:90),total_costs:.05-net,mean_daily_turnover:turnover,mean_exposure:1,flat_days:0}
 }));
 const pairs=rows.filter(r=>r.arm_id==='ew_monthly_buffer20').map(candidate=>{
  const control=rows.find(r=>r.market===candidate.market&&r.arm_id==='ew_monthly'&&r.fee_bps===candidate.fee_bps);
  const context={market:candidate.market,fee_bps:candidate.fee_bps,start:candidate.start,end:candidate.end,candidate_job_id:candidate.job_id,control_job_id:control.job_id};
  return {...context,pair_id:createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.entries(context).sort(([a],[b])=>a.localeCompare(b))))).digest('hex'),candidate_arm:candidate.arm_id,control_arm:control.arm_id,net_return_change:candidate.metrics.net_return-control.metrics.net_return,drawdown_change:candidate.metrics.max_drawdown-control.metrics.max_drawdown,turnover_change:candidate.metrics.mean_daily_turnover-control.metrics.mean_daily_turnover,exposure_change:0};
 });
 return {...base,status:'measured',as_of:'2025-01-01T00:00:00Z',code_commit:'a'.repeat(40),plan_sha256:'b'.repeat(64),coverage:{requested_jobs:rows.length,completed_jobs:rows.length,blocked_jobs:0},results:rows,pairs,blockers:[]};
}
