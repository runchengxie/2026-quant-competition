const stockArms=['equal_weight','reversal','ridge','elastic_net'];
const cryptoArms=['buy_hold_equal_weight','fixed60_weekly','trend_weekly','matched_weekly'];

function stock(facts,{horizon,fee,delay,buffer}){
 if(facts.equity?.currency!=='USD'||![5,20].includes(horizon)||![0,20,40].includes(fee)||![0,1].includes(delay)||![0,20].includes(buffer))throw new RangeError('Unsupported holding selection');
 return facts.equity;
}

export function selectHoldings(facts,selection){
 const rows=stock(facts,selection).accounts.filter(r=>r.window===selection.window&&r.horizon===selection.horizon&&r.fee_bps===selection.fee&&r.delay===selection.delay&&r.buffer===(r.arm==='equal_weight'?0:selection.buffer));
 if(rows.length!==4||new Set(rows.map(r=>r.arm)).size!==4||rows.some(r=>!stockArms.includes(r.arm)))throw new RangeError('Incomplete holding selection');
 return stockArms.map(arm=>rows.find(r=>r.arm===arm));
}

export function holdingCosts(facts,selection){
 const chosen=[0,20,40].map(fee=>selectHoldings(facts,{...selection,fee}));
 return {fees:[0,20,40],series:stockArms.map((arm,index)=>({arm,values:chosen.map(rows=>rows[index].metrics===null?null:100*rows[index].metrics.net_return)}))};
}

export function selectModels(facts,{window,horizon}){
 if(facts.equity?.currency!=='USD'||![5,20].includes(horizon))throw new RangeError('Unsupported model selection');
 const rows=facts.equity.models.filter(r=>r.window===window&&r.horizon===horizon);
 if(rows.length!==2||new Set(rows.map(r=>r.model)).size!==2||rows.some(r=>!['ridge','elastic_net'].includes(r.model)))throw new RangeError('Incomplete model selection');
 return ['ridge','elastic_net'].map(model=>rows.find(r=>r.model===model));
}

export function selectAttribution(facts,{window,fee,delay}){
 if(facts.crypto?.currency!=='USDT'||![0,35,50].includes(fee)||![0,1].includes(delay))throw new RangeError('Unsupported attribution selection');
 const rows=facts.crypto.accounts.filter(r=>r.window===window&&r.fee_bps===fee&&r.delay===delay);
 if(rows.length!==4||new Set(rows.map(r=>r.arm)).size!==4||rows.some(r=>!cryptoArms.includes(r.arm)))throw new RangeError('Incomplete attribution selection');
 return cryptoArms.map(arm=>rows.find(r=>r.arm===arm));
}

export function bufferSummary(facts,{horizon,fee,delay}){
 stock(facts,{horizon,fee,delay,buffer:20});
 const rows=facts.equity.accounts.filter(r=>r.horizon===horizon&&r.fee_bps===fee&&r.delay===delay&&r.buffer===20);
 let comparable=0,lowerTurnover=0,higherReturn=0;
 for(const left of rows){
  const right=facts.equity.accounts.find(r=>r.window===left.window&&r.horizon===horizon&&r.fee_bps===fee&&r.delay===delay&&r.buffer===0&&r.arm===left.arm);
  if(left.status!=='completed'||right?.status!=='completed')continue;
  comparable++;if(left.metrics.turnover<right.metrics.turnover)lowerTurnover++;if(left.metrics.net_return>right.metrics.net_return)higherReturn++;
 }
 return {requested:rows.length,comparable,blocked:rows.length-comparable,lowerTurnover,higherReturn};
}
