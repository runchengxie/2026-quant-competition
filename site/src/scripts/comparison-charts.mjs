import * as echarts from 'echarts/core';
import {BarChart,LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {selectComparison,costSeries,pairedSummary} from './comparison-state.mjs';
import {formatResearchNumber} from './incremental-state.mjs';

echarts.use([BarChart,LineChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,CanvasRenderer]);

export function mountComparison(root){
 const facts=JSON.parse(root.dataset.comparisonFacts),market=root.dataset.comparisonMarket;
 const {locale,t}=JSON.parse(root.querySelector('[data-comparison-config]').textContent);
 const bars=echarts.init(root.querySelector('[data-cmp-chart="returns"]'));
 const curves=echarts.init(root.querySelector('[data-cmp-chart="costs"]'));
 const fmt=value=>formatResearchNumber(value,locale,t.unavailable);
 const name=arm=>t.arms[arm];
 const substitute=(text,values)=>Object.entries(values).reduce((value,[key,number])=>value.replaceAll(`{${key}}`,String(number)),text);
 function render(){
  const window=root.querySelector('[data-cmp-window]').value,fee=Number(root.querySelector('[data-cmp-fee]').value),delay=Number(root.querySelector('[data-cmp-delay]').value);
  const rows=selectComparison(facts,{market,window,fee,delay}),costs=costSeries(facts,{market,window,delay}),summary=pairedSummary(facts,{market,fee,delay});
  root.dataset.comparisonWindow=window;root.dataset.comparisonFee=String(fee);root.dataset.comparisonDelay=String(delay);
  root.querySelector('[data-cmp-summary]').textContent=substitute(market==='equity'?t.equitySummary:t.cryptoSummary,summary)+(summary.blocked?' '+substitute(t.blockedSummary,summary):'');
  root.querySelectorAll('[data-cmp-row]').forEach(row=>row.hidden=row.dataset.window!==window||Number(row.dataset.fee)!==fee||Number(row.dataset.delay)!==delay);
  const probe=document.createElement('span');probe.style.cssText='visibility:hidden;position:absolute';root.append(probe);
  const resolve=variable=>{probe.style.color=`var(${variable})`;return getComputedStyle(probe).color;};
  const ink=resolve('--ink'),line=resolve('--line'),surface=resolve('--surface');probe.remove();root.dataset.comparisonInk=ink;
  const common={animation:false,aria:{enabled:true},color:['#668dbe','#267b69','#b39c69','#b66e67'],textStyle:{color:ink},tooltip:{trigger:'axis',renderMode:'richText',backgroundColor:surface,textStyle:{color:ink}},grid:{containLabel:true,left:20,right:35,top:35,bottom:35}};
  const values=rows.map(row=>row.status==='completed'?100*row.metrics.net_return:null);
  bars.setOption({...common,xAxis:{type:'value',name:'%',axisLabel:{color:ink,formatter:value=>fmt(value)},splitLine:{lineStyle:{color:line}}},yAxis:{type:'category',inverse:true,data:rows.map(row=>name(row.arm)),axisLabel:{color:ink,fontSize:11}},
   tooltip:{...common.tooltip,formatter:params=>`${params[0].name}\n${t.return} ${params[0].value===null?t.unavailable:fmt(params[0].value)+'%'}`},series:[{name:t.return,type:'bar',barMaxWidth:25,data:values.map((value,index)=>({value,itemStyle:{color:common.color[index]}}))}]},{notMerge:true});
  const selected=curves.getOption()?.legend?.[0]?.selected;
  curves.setOption({...common,grid:{...common.grid,top:90,left:45},legend:{type:'scroll',textStyle:{color:ink},selected},xAxis:{type:'category',data:costs.fees.map(value=>`${value} bps`),axisLabel:{color:ink}},yAxis:{type:'value',name:'%',axisLabel:{color:ink,formatter:value=>fmt(value)},splitLine:{lineStyle:{color:line}}},
   series:costs.series.map(row=>({name:name(row.arm),type:'line',connectNulls:false,symbolSize:7,data:row.values}))},{notMerge:true});
 }
 root.querySelectorAll('select').forEach(select=>select.addEventListener('change',render));
 render();root.dataset.comparisonReady='true';
 new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
 new ResizeObserver(()=>{bars.resize();curves.resize();}).observe(root);
 window.addEventListener('resize',()=>{bars.resize();curves.resize();});
}
