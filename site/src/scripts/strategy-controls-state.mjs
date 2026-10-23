/** Reviewed window aggregates only. No account replay or joining cash-reset folds. */
const ARMS={US:['ew_daily','ew_monthly','ew_monthly_buffer20','mom20_daily','mom20_monthly','mom20_monthly_buffer20'],crypto:['ew_legacy','trend200_legacy','trend200_vol40_legacy','trend200_fixed60_legacy','trend200_vol40_strict','ew_fixed60','ew_vol40_strict','ew_trend_gross_matched']};
const FEES={US:[20,40],crypto:[0,10,25]};
const COMPARISONS={ew_monthly_buffer20:['ew_monthly'],mom20_monthly_buffer20:['mom20_monthly'],trend200_fixed60_legacy:['trend200_legacy','ew_fixed60'],trend200_vol40_strict:['trend200_legacy','ew_vol40_strict','ew_trend_gross_matched']};
const METRICS=['periods','net_return','gross_return','cost_drag','volatility','sharpe','max_drawdown','turnover','total_costs','mean_daily_turnover','mean_exposure','flat_days'];
const RESTRICTIONS=['fixed_current_selection','retrospective_not_untouched_oos','lagged_close_proxy','independent_cash_windows','no_terminal_liquidation','not_execution_authorization','US_split_adjusted_not_total_return','USDT_not_USD'];
const hash=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join('|')===[...keys].sort().join('|');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const close=(a,b)=>finite(a)&&finite(b)&&Math.abs(a-b)<=1e-12;
const day=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
const reject=()=>{throw Error('Invalid strategy controls snapshot');};

function method(market,arm){
 let parameters={};
 if(market==='US'){
  parameters={signal:arm.startsWith('mom20')?'momentum_20d':'equal_weight',schedule:arm.includes('monthly')?'monthly':'daily'};
  if(arm.endsWith('buffer20'))Object.assign(parameters,{buffer_l1:.2,include_cash:true,scheduled_cash_exit:true});
 }else if(arm.endsWith('strict')||arm==='ew_trend_gross_matched'){
  parameters={lookback_days:20,annual_target:.4,annual_periods:365,leverage_cap:1,zero_volatility:'cash',sample_ddof:1};
  if(arm==='ew_trend_gross_matched')parameters.exposure_source_arm='trend200_vol40_strict';
 }else if(arm==='ew_fixed60')parameters={multiplier:.6};
 return {market,arm_id:arm,parameters,role:arm==='trend200_fixed60_legacy'?'post_hoc_diagnostic':'retrospective_control'};
}

export function validateControlsSnapshot(s){
 if(!exact(s,['schema','status','as_of','code_commit','plan_sha256','coverage','methods','results','pairs','blockers','restrictions'])||s.schema!=='competition.public_strategy_controls.v1'||!['measured','readiness_only'].includes(s.status)||!hash(s.plan_sha256)||typeof s.code_commit!=='string'||!/^[a-f0-9]{40}$/.test(s.code_commit))reject();
 if(typeof s.as_of!=='string'||!/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(s.as_of)||!Number.isFinite(Date.parse(s.as_of)))reject();
 const c=s.coverage;if(!exact(c,['requested_jobs','completed_jobs','blocked_jobs'])||Object.values(c).some(v=>!Number.isInteger(v)||v<0||v>512)||c.requested_jobs<1||c.completed_jobs+c.blocked_jobs!==c.requested_jobs)reject();
 const methods=Object.entries(ARMS).flatMap(([market,arms])=>arms.map(arm=>method(market,arm)));
 if(stable(s.methods)!==stable(methods)||stable(s.restrictions)!==stable(RESTRICTIONS)||!Array.isArray(s.results)||!Array.isArray(s.pairs)||!Array.isArray(s.blockers)||new Set(s.blockers).size!==s.blockers.length||s.blockers.some(v=>!['PUBLICATION_PERMISSION_UNVERIFIED','INCOMPLETE_CONTROLS_RUN'].includes(v)))reject();
 if(s.status==='readiness_only'){if(s.results.length||s.pairs.length||!s.blockers.length)reject();return s;}
 if(s.blockers.length||c.blocked_jobs||s.results.length!==c.requested_jobs)reject();
 const byId=new Map(),conditions=new Set();
 for(const r of s.results){
  if(!exact(r,['job_id','market','arm_id','fee_bps','quote_currency','start','end','metrics'])||!hash(r.job_id)||byId.has(r.job_id)||!ARMS[r.market]?.includes(r.arm_id)||!FEES[r.market].includes(r.fee_bps)||r.quote_currency!==(r.market==='US'?'USD':'USDT')||!day(r.start)||!day(r.end)||r.start>r.end||r.end>new Date(s.as_of).toISOString().slice(0,10))reject();
  const identity=stable([r.market,r.arm_id,r.fee_bps,r.start,r.end]);if(conditions.has(identity))reject();conditions.add(identity);byId.set(r.job_id,r);
  const m=r.metrics;if(!exact(m,METRICS)||METRICS.some(k=>k!=='sharpe'&&!finite(m[k]))||m.periods!==(r.market==='US'?63:90)||!Number.isInteger(m.flat_days)||m.flat_days<0||m.flat_days>m.periods||m.net_return< -1||m.gross_return< -1||['volatility','max_drawdown','turnover','total_costs','mean_daily_turnover','mean_exposure'].some(k=>m[k]<0)||m.max_drawdown>1||m.mean_exposure>1+1e-12||!close(m.cost_drag,m.gross_return-m.net_return)||(m.volatility===0?m.sharpe!==null:!finite(m.sharpe)))reject();
 }
 const expected=new Set(s.results.flatMap(r=>(COMPARISONS[r.arm_id]??[]).map(control=>stable([r.job_id,control])))),seen=new Set(),pairIds=new Set();
 for(const p of s.pairs){
  if(!exact(p,['market','fee_bps','start','end','candidate_job_id','control_job_id','pair_id','candidate_arm','control_arm','net_return_change','drawdown_change','turnover_change','exposure_change'])||!hash(p.pair_id)||pairIds.has(p.pair_id))reject();pairIds.add(p.pair_id);
  const a=byId.get(p.candidate_job_id),b=byId.get(p.control_job_id),identity=stable([p.candidate_job_id,p.control_arm]);
  if(!a||!b||!expected.has(identity)||seen.has(identity)||p.candidate_arm!==a.arm_id||p.control_arm!==b.arm_id||['market','fee_bps','start','end'].some(k=>a[k]!==b[k]||p[k]!==a[k])||[['net_return_change','net_return'],['drawdown_change','max_drawdown'],['turnover_change','mean_daily_turnover'],['exposure_change','mean_exposure']].some(([delta,metric])=>!close(p[delta],a.metrics[metric]-b.metrics[metric])))reject();seen.add(identity);
 }
 if(seen.size!==expected.size)reject();return s;
}

export function selectControls(snapshot,selection){
 if(snapshot.status!=='measured'||!selection||!ARMS[selection.market]||typeof selection.feeBps!=='number'||!FEES[selection.market].includes(selection.feeBps))return [];
 return snapshot.results.filter(r=>r.market===selection.market&&r.fee_bps===selection.feeBps&&(!selection.armId||r.arm_id===selection.armId)&&(!selection.windowStart||r.start===selection.windowStart));
}
export function selectControlPairs(snapshot,selection){const ids=new Set(selectControls(snapshot,selection).map(r=>r.job_id));return snapshot.pairs.filter(p=>ids.has(p.candidate_job_id));}
const median=values=>{const a=[...values].sort((a,b)=>a-b);return a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2;};
export function controlsHighlights(snapshot){
 if(snapshot.status!=='measured')return [];
 return [
  {market:'US',feeBps:20,armId:'ew_monthly_buffer20',control:'ew_monthly'},
  {market:'crypto',feeBps:25,armId:'trend200_vol40_strict',control:'ew_trend_gross_matched'}
 ].flatMap(selection=>{
  const pairs=selectControlPairs(snapshot,selection).filter(p=>p.control_arm===selection.control);
  return pairs.length?[{...selection,windows:pairs.length,returnWins:pairs.filter(p=>p.net_return_change>0).length,
   drawdownWins:pairs.filter(p=>p.drawdown_change<0).length,medianReturnChange:median(pairs.map(p=>p.net_return_change))}]:[];
 });
}
export function summarizeControls(snapshot,selection){
 const groups=new Map();for(const row of selectControls(snapshot,selection)){if(!groups.has(row.arm_id))groups.set(row.arm_id,[]);groups.get(row.arm_id).push(row);}
 return [...groups].map(([arm,rows])=>({arm_id:arm,fee_bps:selection.feeBps,count:rows.length,net_return:median(rows.map(r=>r.metrics.net_return)),max_drawdown:median(rows.map(r=>r.metrics.max_drawdown)),volatility:median(rows.map(r=>r.metrics.volatility)),turnover:median(rows.map(r=>r.metrics.mean_daily_turnover)),exposure:median(rows.map(r=>r.metrics.mean_exposure))}));
}
export function compareControlCosts(snapshot,selection){if(!ARMS[selection?.market])return [];return FEES[selection.market].flatMap(fee=>summarizeControls(snapshot,{...selection,feeBps:fee}));}
