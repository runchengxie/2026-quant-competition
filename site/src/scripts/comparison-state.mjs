const arms={equity:['equal_weight','reversal','ridge','elastic_net'],crypto:['buy_hold_equal_weight','fixed60_weekly','trend_weekly','matched_weekly']};
const costs={equity:[0,20,40],crypto:[0,35,50]};

function marketFacts(facts,market){
 if(!Object.hasOwn(arms,market)||facts[market]?.currency!==(market==='equity'?'USD':'USDT'))throw new RangeError('Unsupported comparison market or currency');
 return facts[market];
}

export function selectComparison(facts,{market,window,fee,delay}){
 const data=marketFacts(facts,market);
 if(!costs[market].includes(fee)||![0,1].includes(delay)||typeof window!=='string')throw new RangeError('Unsupported comparison selection');
 const rows=data.accounts.filter(row=>row.window===window&&row.fee_bps===fee&&row.delay===delay);
 if(rows.length!==4||new Set(rows.map(row=>row.arm)).size!==4||rows.some(row=>!arms[market].includes(row.arm)))throw new RangeError('Incomplete comparison selection');
 return arms[market].map(arm=>rows.find(row=>row.arm===arm));
}

export function costSeries(facts,{market,window,delay}){
 marketFacts(facts,market);
 const selections=costs[market].map(fee=>selectComparison(facts,{market,window,fee,delay}));
 return {fees:[...costs[market]],series:arms[market].map(arm=>({arm,values:selections.map(rows=>{
  const row=rows.find(item=>item.arm===arm);
  return row.status==='completed'?100*row.metrics.net_return:null;
 })}))};
}

export function pairedSummary(facts,{market,fee,delay}){
 const data=marketFacts(facts,market),windows=[...new Set(data.accounts.map(row=>row.window))];
 const candidate=market==='equity'?'ridge':'trend_weekly',baseline=market==='equity'?'equal_weight':'buy_hold_equal_weight';
 let comparable=0,wins=0;
 for(const window of windows){
  const rows=selectComparison(facts,{market,window,fee,delay}),left=rows.find(row=>row.arm===candidate),right=rows.find(row=>row.arm===baseline);
  if(left.status!=='completed'||right.status!=='completed')continue;
  comparable++;if(left.metrics.net_return>right.metrics.net_return)wins++;
 }
 return {requested:windows.length,comparable,blocked:windows.length-comparable,wins};
}
