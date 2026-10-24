import {validateRobustnessSnapshot,summarizeRobustness} from './robustness-state.mjs';

// Presentation-only projection. The original reviewed snapshots stay authoritative.
export function editorialSummary(snapshot,readiness){
 validateRobustnessSnapshot(snapshot);
 const measured=snapshot.status==='measured';
 const range=market=>{
  const rows=snapshot.results.filter(r=>r.market===market);
  return rows.length?{start:rows.map(r=>r.start).sort()[0],end:rows.map(r=>r.end).sort().at(-1)}:null;
 };
 const us=measured?summarizeRobustness(snapshot,{market:'US',feeBps:20}):[];
 return {
  asOf:snapshot.as_of,codeCommit:snapshot.code_commit,planSha256:snapshot.plan_sha256,
  coverage:{...snapshot.coverage},
  observation:{status:readiness.observation.status,observations:readiness.observation.observations,firstEligibleObservationAt:readiness.observation.first_eligible_observation_at},
  us:['exclude_nvda','exclude_three','fixed_six'].map(id=>us.find(g=>g.poolId===id)).filter(Boolean),
  crypto:measured?[35,50].flatMap(feeBps=>summarizeRobustness(snapshot,{market:'crypto',feeBps})):[],
  evidenceRange:{US:range('US'),crypto:range('crypto')},
 };
}
