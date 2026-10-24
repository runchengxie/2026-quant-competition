import * as echarts from 'echarts/core';
import {LineChart,ScatterChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,AriaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {formatResearchNumber,equitySeries,cryptoPoints} from './incremental-state.mjs';

echarts.use([LineChart,ScatterChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,AriaComponent,CanvasRenderer]);

export function mountIncremental(root){
 const facts=JSON.parse(root.dataset.incrementalFacts);
 const {locale,t}=JSON.parse(root.querySelector('[data-incremental-config]').textContent);
 const view=root.dataset.incrementalView;
 const chart=echarts.init(root.querySelector('[data-incremental-chart]'));
 const fmt=value=>formatResearchNumber(value,locale,t.unavailable);
 function render(){
  const probe=document.createElement('span');probe.style.visibility='hidden';root.append(probe);
  const resolve=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const ink=resolve('--ink'),line=resolve('--line');probe.remove();root.dataset.chartInk=ink;
  const common={animation:false,aria:{enabled:true},color:['#267b69','#668dbe','#b39c69','#b66e67','#967ab2'],textStyle:{color:ink},
   grid:{left:65,right:20,bottom:90,top:65},legend:{type:'scroll',textStyle:{color:ink},selected:chart.getOption()?.legend?.[0]?.selected},
   tooltip:{trigger:'item',renderMode:'richText'},xAxis:{axisLabel:{color:ink}},yAxis:{axisLabel:{color:ink},splitLine:{lineStyle:{color:line}}}};
  if(view==='equity'){
   const model=root.querySelector('[data-model]').value,period=Number(root.querySelector('[data-period]').value);
   const values=equitySeries(facts,model,period);
   root.dataset.chartModel=model;root.dataset.chartPeriod=String(period);
   root.querySelectorAll('[data-equity-row]').forEach(row=>row.hidden=Number(row.dataset.fold)!==period);
   root.querySelectorAll('[data-stratum-row]').forEach(row=>row.hidden=Number(row.dataset.fold)!==period||row.dataset.stratumModel!==model);
   chart.setOption({...common,legend:{show:false},tooltip:{trigger:'axis',renderMode:'richText',formatter:params=>{
    const point=params[0],index=point.dataIndex;
    return `${values.dates[index]}\n${t.difference} ${fmt(values.differences[index])}\n${t.count} ${values.counts[index]}`;
   }},xAxis:{...common.xAxis,type:'category',data:values.dates,axisLabel:{color:ink,formatter:value=>value.slice(5)}},
    yAxis:{...common.yAxis,type:'value',name:t.difference},dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:15,textStyle:{color:ink}}],
    series:[{name:t.models[model],type:'line',connectNulls:false,data:values.differences,symbolSize:5}]},{notMerge:true});
  }else{
   const fee=root.querySelector('[data-fee]').value,window=root.querySelector('[data-window]').value;
   const points=cryptoPoints(facts,fee).filter(row=>window==='all'||row.window===window);
   root.dataset.chartFee=fee;root.dataset.chartWindow=window;
   root.querySelectorAll('[data-crypto-row]').forEach(row=>row.hidden=row.dataset.rowFee!==fee||(window!=='all'&&row.dataset.rowWindow!==window));
   chart.setOption({...common,tooltip:{trigger:'item',renderMode:'richText',formatter:point=>`${point.seriesName}\n${point.data.window}\n${t.turnover} ${fmt(point.value[0])}\n${t.return} ${fmt(point.value[1])}`},
    xAxis:{...common.xAxis,type:'value',name:t.turnover,nameLocation:'middle',nameGap:35},yAxis:{...common.yAxis,type:'value',name:t.return},
    series:Object.keys(t.arms).map(arm=>({name:t.arms[arm],type:'scatter',symbolSize:9,data:points.filter(row=>row.arm===arm).map(row=>({value:row.value,window:row.window}))}))},{notMerge:true});
  }
 }
 root.querySelectorAll('select').forEach(select=>select.addEventListener('change',render));
 render();root.dataset.incrementalReady='true';
 new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
 new ResizeObserver(()=>chart.resize()).observe(root);window.addEventListener('resize',()=>chart.resize());
}
