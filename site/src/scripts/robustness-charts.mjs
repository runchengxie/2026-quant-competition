import * as echarts from 'echarts/core';
import {BarChart,LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,AriaComponent,LegendComponent,DataZoomComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {validateRobustnessSnapshot,selectRobustness,summarizeRobustness,capacitySummary} from './robustness-state.mjs';
import {formatControlChange} from './strategy-controls-state.mjs';

echarts.use([BarChart,LineChart,GridComponent,TooltipComponent,AriaComponent,LegendComponent,DataZoomComponent,CanvasRenderer]);

export function mountRobustness(root){
 const {locale,t}=JSON.parse(root.querySelector('[data-robustness-config]').textContent);
 const snapshot=validateRobustnessSnapshot(JSON.parse(root.dataset.robustnessFacts));
 const controls=Object.fromEntries([...root.querySelectorAll('[data-robustness-filter]')].map(n=>[n.dataset.robustnessFilter,n]));
 const charts=Object.fromEntries(['paired','windows','fees'].map(id=>[id,echarts.init(root.querySelector(`[data-robustness-chart=${id}]`))]));
 const number=new Intl.NumberFormat(locale,{maximumFractionDigits:2});
 const change=value=>value===null?t.notAvailable:formatControlChange(value,locale)+' '+t.pp;
 const method=id=>t.methods[id]??id;
 const selection=()=>({market:controls.market.value,feeBps:Number(controls.fee.value),windowStart:controls.window.value||undefined});
 function sync(reset=false){
  const market=controls.market.value,fees=market==='US'?[20,40]:[35,50],wanted=reset?String(market==='US'?20:50):controls.fee.value;
  controls.fee.replaceChildren(...fees.map(f=>new Option(String(f),String(f))));controls.fee.value=wanted;
  const window=controls.window.value,dates=[...new Set(snapshot.results.filter(r=>r.market===market).map(r=>r.start))].sort();
  controls.window.replaceChildren(new Option(t.allWindows,''),...dates.map(d=>new Option(d,d)));controls.window.value=dates.includes(window)?window:'';
 }
 function draw(){
  const selected=selection(),rows=selectRobustness(snapshot,selected),groups=summarizeRobustness(snapshot,selected),ids=new Set(rows.map(r=>r.job_id));
  root.dataset.selectionFacts=JSON.stringify({selection:selected,groups});
  root.querySelectorAll('[data-robustness-row]').forEach(n=>{n.hidden=!ids.has(n.dataset.robustnessRow);});
  root.querySelector('[data-robustness-status]').textContent=t.selected.replace('{count}',number.format(rows.length));
  const body=root.querySelector('[data-robustness-summary]');body.replaceChildren();
  for(const g of groups){const tr=document.createElement('tr');[method(g.poolId),g.feeBps,`${g.windows} / ${g.requestedWindows}`,`${g.returnWins} / ${g.requestedWindows}`,`${g.drawdownWins} / ${g.requestedWindows}`,change(g.medianReturnChange)].forEach((v,i)=>{const cell=document.createElement(i?'td':'th');cell.textContent=String(v);tr.append(cell);});body.append(tr);}
  const probe=document.createElement('span');probe.hidden=true;root.append(probe);
  const color=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const ink=color('--ink'),line=color('--line'),green=color('--green'),negative=color('--ask'),surface=color('--surface');probe.remove();
  const common=id=>({animation:false,textStyle:{color:ink},backgroundColor:'transparent',aria:{enabled:true,label:{description:t.charts[id]}},tooltip:{trigger:'item',renderMode:'richText',backgroundColor:surface,borderColor:line,textStyle:{color:ink}},grid:{left:85,right:25,top:30,bottom:95}});
  const yAxis={type:'value',axisLabel:{color:ink,formatter:change},splitLine:{lineStyle:{color:line}}};
  const xAxis=data=>({type:'category',data,axisLabel:{color:ink,rotate:15,width:125,overflow:'truncate'}});
  charts.paired.setOption({...common('paired'),xAxis:xAxis(groups.map(g=>method(g.poolId))),yAxis,series:[{type:'bar',data:groups.map(g=>({value:g.medianReturnChange,itemStyle:{color:g.medianReturnChange>=0?green:negative}})),tooltip:{valueFormatter:change}}]},true);
  const pairs=(selected.market==='US'?snapshot.us_pairs:snapshot.crypto_pairs).filter(p=>ids.has(p.job_id??p.candidate_job_id));
  const dates=[...new Set(pairs.map(p=>p.start))].sort(),groupIds=[...new Set(groups.map(g=>g.poolId))];
  charts.windows.setOption({...common('windows'),legend:{type:'scroll',bottom:25,textStyle:{color:ink}},xAxis:xAxis(dates),yAxis,dataZoom:[{type:'slider',height:15,bottom:0,textStyle:{color:ink}}],series:groupIds.map(id=>({name:method(id),type:'bar',data:dates.map(d=>pairs.find(p=>p.start===d&&(selected.market==='crypto'||p.pool_id===id))?.net_return_change??null),tooltip:{valueFormatter:change}}))},true);
  const allCosts=summarizeRobustness(snapshot,{market:selected.market,windowStart:selected.windowStart}),fees=[...new Set(allCosts.map(g=>g.feeBps))].sort((a,b)=>a-b);
  charts.fees.setOption({...common('fees'),legend:{type:'scroll',bottom:5,textStyle:{color:ink}},xAxis:xAxis(fees.map(String)),yAxis,series:[...new Set(allCosts.map(g=>g.poolId))].map(id=>({name:method(id),type:'line',symbolSize:8,connectNulls:false,data:fees.map(f=>allCosts.find(g=>g.poolId===id&&g.feeBps===f)?.medianReturnChange??null),tooltip:{valueFormatter:change}}))},true);
  const capacity=root.querySelector('[data-robustness-capacity]');capacity.hidden=selected.market!=='crypto';
  if(!capacity.hidden){
   if(!charts.capacity)charts.capacity=echarts.init(root.querySelector('[data-robustness-chart=capacity]'));
   const notionalUsdt=Number(root.querySelector('[data-robustness-notional]').value),threshold=Number(root.querySelector('[data-robustness-threshold]').value);
   const summary=capacitySummary(snapshot,{notionalUsdt,threshold});
   root.querySelector('[data-capacity-summary]').textContent=t.capacitySummary.replace('{breaches}',number.format(summary.breachingAccounts)).replace('{accounts}',number.format(summary.accounts)).replace('{missing}',number.format(summary.unavailableAccounts));
   charts.capacity.setOption({...common('capacity'),xAxis:xAxis([10000,100000,1000000].map(n=>number.format(n)+' USDT')),yAxis:{type:'value',min:0,max:48,minInterval:1,axisLabel:{color:ink},splitLine:{lineStyle:{color:line}}},series:[{type:'bar',data:[10000,100000,1000000].map(n=>({value:capacitySummary(snapshot,{notionalUsdt:n,threshold}).breachingAccounts,itemStyle:{color:n===notionalUsdt?negative:green}}))}]},true);
  }
  root.dataset.ready='true';
 }
 controls.market.addEventListener('change',()=>{controls.window.value='';sync(true);draw();});
 for(const [key,node] of Object.entries(controls))if(key!=='market')node.addEventListener('change',draw);
 for(const node of root.querySelectorAll('[data-robustness-notional],[data-robustness-threshold]'))node.addEventListener('change',draw);
 new ResizeObserver(()=>Object.values(charts).forEach(chart=>chart.resize())).observe(root);
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
 sync(true);draw();root.querySelector('[data-robustness-filters]').hidden=false;
}
