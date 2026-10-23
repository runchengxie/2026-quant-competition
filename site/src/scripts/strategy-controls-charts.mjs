import * as echarts from 'echarts/core';
import {BarChart,ScatterChart,LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,AriaComponent,LegendComponent,DataZoomComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {validateControlsSnapshot,selectControls,selectControlPairs,summarizeControls,compareControlCosts,formatControlChange} from './strategy-controls-state.mjs';
echarts.use([BarChart,ScatterChart,LineChart,GridComponent,TooltipComponent,AriaComponent,LegendComponent,DataZoomComponent,CanvasRenderer]);
const median=values=>{const a=[...values].sort((a,b)=>a-b);return a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2;};

export function mountStrategyControls(root){
 const {locale,t}=JSON.parse(root.querySelector('[data-controls-config]').textContent);
 const snapshot=validateControlsSnapshot(JSON.parse(root.dataset.controlsFacts));
 if(snapshot.status!=='measured')return;
 const controls=Object.fromEntries([...root.querySelectorAll('[data-controls-filter]')].map(n=>[n.dataset.controlsFilter,n]));
 const charts=Object.fromEntries([...root.querySelectorAll('[data-controls-chart]')].map(n=>[n.dataset.controlsChart,echarts.init(n)]));
 const formatter=new Intl.NumberFormat(locale,{maximumFractionDigits:2});
 const show=value=>formatter.format(value*100)+'%';
 const change=value=>formatControlChange(value,locale)+t.percentagePoints;
 const arm=id=>t.arms[id]??id;
 const selection=()=>({market:controls.market.value,feeBps:Number(controls.fee.value),armId:controls.arm.value||undefined,windowStart:controls.window.value||undefined});
 const options=(node,values,wanted,all)=>{node.replaceChildren(...(all?[new Option(all,'')]:[]),...values.map(([v,label])=>new Option(label,String(v))));if(values.some(([v])=>String(v)===wanted)||all&&wanted==='')node.value=wanted;};
 function sync(reset=false){
  const rows=snapshot.results.filter(r=>r.market===controls.market.value),fees=[...new Set(rows.map(r=>r.fee_bps))].sort((a,b)=>a-b);
  options(controls.fee,fees.map(v=>[v,formatter.format(v)]),reset?String(controls.market.value==='US'?20:10):controls.fee.value);
  options(controls.arm,[...new Set(rows.map(r=>r.arm_id))].map(id=>[id,arm(id)]),controls.arm.value,t.allArms);
  options(controls.window,[...new Map(rows.map(r=>[r.start,[r.start,`${r.start} / ${r.end}`]])).values()].sort((a,b)=>a[0].localeCompare(b[0])),controls.window.value,t.allWindows);
 }
 function draw(){
  const selected=selection(),rows=selectControls(snapshot,selected),pairs=selectControlPairs(snapshot,selected),groups=summarizeControls(snapshot,selected),ids=new Set(rows.map(r=>r.job_id));
  root.querySelectorAll('[data-controls-result]').forEach(n=>{n.hidden=!ids.has(JSON.parse(n.dataset.controlsResult).job_id);});
  const body=root.querySelector('[data-controls-summary]');body.replaceChildren();
  for(const g of groups){const tr=document.createElement('tr');[arm(g.arm_id),g.fee_bps,g.count,...['net_return','max_drawdown','volatility','turnover','exposure'].map(k=>show(g[k]))].forEach((value,i)=>{const cell=document.createElement(i?'td':'th');cell.textContent=String(value);tr.append(cell);});body.append(tr);}
  root.querySelector('[data-controls-status]').textContent=t.selected.replace('{count}',formatter.format(rows.length));
  const outcome=!pairs.length?'none':pairs.every(p=>p.net_return_change>0)?'positive':pairs.every(p=>p.net_return_change<0)?'negative':pairs.every(p=>p.net_return_change===0)?'zero':'mixed';
  root.querySelector('[data-controls-selection-conclusion]').textContent=t.outcomes[outcome];
  const pairGroups=new Map();for(const p of pairs){const key=p.candidate_arm+'|'+p.control_arm;if(!pairGroups.has(key))pairGroups.set(key,[]);pairGroups.get(key).push(p);}
  const paired=[...pairGroups.values()].map(values=>({label:`${arm(values[0].candidate_arm)} / ${arm(values[0].control_arm)}`,net:median(values.map(p=>p.net_return_change)),turnover:median(values.map(p=>p.turnover_change))}));
  const probe=document.createElement('span');probe.style.visibility='hidden';root.append(probe);
  const color=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const ink=color('--ink'),line=color('--line'),green=color('--green'),muted=color('--muted'),paper=color('--surface');probe.remove();root.dataset.chartColors=JSON.stringify({ink,line,green,paper});
  const common=id=>({animation:false,textStyle:{color:ink},backgroundColor:'transparent',aria:{enabled:true,label:{description:t.charts[id]}},tooltip:{trigger:'item',renderMode:'richText',backgroundColor:paper,borderColor:line,textStyle:{color:ink}},grid:{left:85,right:20,top:30,bottom:100}});
  const axis={axisLabel:{color:ink,formatter:show},splitLine:{lineStyle:{color:line}}};
  for(const [id,key] of [['paired','net'],['turnover','turnover']])charts[id].setOption({...common(id),xAxis:{type:'category',data:paired.map(p=>p.label),axisLabel:{color:ink,rotate:20,width:130,overflow:'truncate'}},yAxis:{type:'value',...axis,axisLabel:{color:ink,formatter:change}},dataZoom:[{type:'slider',height:16,bottom:0,textStyle:{color:ink}}],series:[{type:'bar',data:paired.map(p=>({name:p.label,value:p[key],itemStyle:{color:p[key]>=0?green:muted}})),tooltip:{valueFormatter:change}}]},true);
  charts.risk.setOption({...common('risk'),grid:{left:65,right:25,top:30,bottom:70},xAxis:{type:'value',name:t.columns.exposure,nameLocation:'middle',nameGap:38,nameTextStyle:{color:ink},...axis},yAxis:{type:'value',...axis},series:[{type:'scatter',symbolSize:14,itemStyle:{color:green},data:groups.map(g=>({name:arm(g.arm_id),value:[g.exposure,g.volatility]})),tooltip:{formatter:p=>`${p.name}\n${t.columns.exposure}: ${show(p.value[0])}\n${t.columns.volatility}: ${show(p.value[1])}`}}]},true);
  const costs=compareControlCosts(snapshot,selected),fees=[...new Set(costs.map(g=>g.fee_bps))].sort((a,b)=>a-b),arms=[...new Set(costs.map(g=>g.arm_id))];
  charts.fees.setOption({...common('fees'),grid:{left:65,right:20,top:30,bottom:95},legend:{type:'scroll',bottom:0,textStyle:{color:ink}},xAxis:{type:'category',data:fees,axisLabel:{color:ink}},yAxis:{type:'value',...axis},series:arms.map(id=>({name:arm(id),type:'line',symbolSize:7,connectNulls:false,data:fees.map(fee=>costs.find(g=>g.arm_id===id&&g.fee_bps===fee)?.net_return??null),tooltip:{valueFormatter:show}}))},true);
  root.dataset.ready='true';
 }
 controls.market.addEventListener('change',()=>{controls.arm.value='';controls.window.value='';sync(true);draw();});
 for(const [key,node] of Object.entries(controls))if(key!=='market')node.addEventListener('change',draw);
 new ResizeObserver(()=>Object.values(charts).forEach(chart=>chart.resize())).observe(root);
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
 sync(true);draw();root.querySelector('[data-controls-filters]').hidden=false;
}
