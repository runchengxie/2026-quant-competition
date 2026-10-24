import * as echarts from 'echarts/core';
import {BarChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {formatResearchNumber} from './incremental-state.mjs';
echarts.use([BarChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,CanvasRenderer]);

export function mountPredictive(root){
 const facts=JSON.parse(root.dataset.predictiveFacts);
 const {locale,t}=JSON.parse(root.querySelector('[data-predictive-config]').textContent);
 const chart=echarts.init(root.querySelector('[data-predictive-chart]'));
 const number={format:value=>formatResearchNumber(value,locale)};
 const ids=['ridge','elastic_net','constant_zero','session_return_rank'];
 function render(){
  const probe=document.createElement('span');probe.style.visibility='hidden';root.append(probe);
  const resolve=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const ink=resolve('--ink'),line=resolve('--line');probe.remove();root.dataset.chartInk=ink;
  const selected=chart.getOption()?.legend?.[0]?.selected;
  chart.setOption({animation:false,aria:{enabled:true},color:['#267b69','#668dbe','#b39c69','#b66e67'],textStyle:{color:ink},grid:{left:55,right:15,bottom:65,top:70},legend:{type:'scroll',textStyle:{color:ink},selected},tooltip:{trigger:'axis',renderMode:'richText',valueFormatter:v=>v==null?t.undefined:number.format(v)},xAxis:{type:'category',data:facts.folds.map(f=>`${f.start}\n${f.end}`),axisLabel:{color:ink}},yAxis:{type:'value',name:'Rank IC',axisLabel:{color:ink},splitLine:{lineStyle:{color:line}}},series:ids.map(id=>({type:'bar',name:t.models[id],data:facts.folds.map(f=>f.models.find(m=>m.model===id).metrics.mean_daily_ic)}))},{notMerge:true});
 }
 render();root.dataset.predictiveReady='true';
 new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
 const resize=()=>chart.resize();new ResizeObserver(resize).observe(root);window.addEventListener('resize',resize);
}
