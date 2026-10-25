import * as echarts from 'echarts/core';
import {BarChart,LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {selectHoldings,holdingCosts,selectModels,selectAttribution,bufferSummary} from './low-turnover-state.mjs';
echarts.use([BarChart,LineChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,CanvasRenderer]);

export function mountLowTurnover(root){
 const facts=JSON.parse(root.dataset.ltFacts),market=root.dataset.ltMarket,view=root.dataset.ltView;
 const {locale,t}=JSON.parse(root.querySelector('[data-lt-config]').textContent);
 const primary=echarts.init(root.querySelector('[data-lt-chart=primary]')),secondary=echarts.init(root.querySelector('[data-lt-chart=secondary]'));
 const fmt=(v,digits=2)=>v==null?t.unavailable:new Intl.NumberFormat(locale,{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(v);
 const substitute=(text,values)=>Object.entries(values).reduce((result,[key,value])=>result.replaceAll(`{${key}}`,String(value)),text);
 function render(){
  const window=root.querySelector('[data-lt-window]').value,horizon=Number(root.querySelector('[data-lt-horizon]')?.value??5),fee=Number(root.querySelector('[data-lt-fee]')?.value??20),delay=Number(root.querySelector('[data-lt-delay]')?.value??0),buffer=Number(root.querySelector('[data-lt-buffer]')?.value??20);
  Object.assign(root.dataset,{ltWindow:window,ltHorizon:String(horizon),ltFee:String(fee),ltDelay:String(delay),ltBuffer:String(buffer)});
  root.querySelectorAll('[data-lt-account]').forEach(row=>row.hidden=row.dataset.window!==window||Number(row.dataset.fee)!==fee||Number(row.dataset.delay)!==delay||(market==='equity'&&(Number(row.dataset.horizon)!==horizon||Number(row.dataset.buffer)!==(row.dataset.arm==='equal_weight'?0:buffer))));
  root.querySelectorAll('[data-lt-model]').forEach(row=>row.hidden=row.dataset.window!==window||Number(row.dataset.horizon)!==horizon);
  const probe=document.createElement('span');probe.style.cssText='visibility:hidden;position:absolute';root.append(probe);
  const resolve=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};const ink=resolve('--ink'),line=resolve('--line'),surface=resolve('--surface');probe.remove();root.dataset.ltInk=ink;
  const common={animation:false,aria:{enabled:true},color:['#668dbe','#267b69','#b39c69','#b66e67'],textStyle:{color:ink},tooltip:{trigger:'axis',renderMode:'richText',backgroundColor:surface,textStyle:{color:ink}},grid:{containLabel:true,left:15,right:30,top:45,bottom:35}};
  const category=rows=>({type:'category',inverse:true,data:rows.map(r=>t.arms[r.arm??r.model]),axisLabel:{color:ink,fontSize:11}});
  const value=(name='%')=>({type:'value',name,axisLabel:{color:ink,formatter:v=>fmt(v)},splitLine:{lineStyle:{color:line}}});
  const bars=(chart,rows,values,label,unit='%')=>chart.setOption({...common,xAxis:value(unit),yAxis:category(rows),series:[{name:label,type:'bar',barMaxWidth:26,data:values.map((v,i)=>({value:v,itemStyle:{color:common.color[i]}}))}]},{notMerge:true});
  if(market==='crypto'){
   const rows=selectAttribution(facts,{window,fee,delay});
   const selected=primary.getOption()?.legend?.[0]?.selected;
   primary.setOption({...common,grid:{...common.grid,top:90},legend:{type:'scroll',textStyle:{color:ink},selected},xAxis:value(),yAxis:category(rows),series:['market','exposure','selection','cost'].map(key=>({name:t[key],type:'bar',stack:'pnl',barMaxWidth:25,data:rows.map(r=>100*r.components[key])}))},{notMerge:true});
   bars(secondary,rows,rows.map(r=>100*r.mean_post_trade_exposure),t.exposureChart);
  }else if(view==='factor'){
   const rows=selectModels(facts,{window,horizon});
   bars(primary,rows,rows.map(r=>r.metrics?.mean_daily_ic??null),t.ic,'IC');
   bars(secondary,rows,rows.map(r=>r.metrics?.mean_daily_mse??null),t.mse,'MSE');
   primary.setOption({xAxis:{axisLabel:{formatter:v=>fmt(v,3)}}});secondary.setOption({xAxis:{axisLabel:{formatter:v=>fmt(v,4)}}});
  }else{
   const rows=selectHoldings(facts,{window,horizon,fee,delay,buffer}),costs=holdingCosts(facts,{window,horizon,delay,buffer});
   bars(primary,rows,rows.map(r=>r.metrics===null?null:100*r.metrics.net_return),t.return);
   const selected=secondary.getOption()?.legend?.[0]?.selected;
   secondary.setOption({...common,grid:{...common.grid,top:90,left:40},legend:{type:'scroll',textStyle:{color:ink},selected},xAxis:{type:'category',data:costs.fees.map(f=>`${f} bps`),axisLabel:{color:ink}},yAxis:value(),series:costs.series.map(r=>({name:t.arms[r.arm],type:'line',connectNulls:false,symbolSize:7,data:r.values}))},{notMerge:true});
   root.querySelector('[data-lt-buffer-summary]').textContent=substitute(t.bufferSummary,bufferSummary(facts,{horizon,fee,delay}));
  }
 }
 root.querySelectorAll('select').forEach(select=>select.addEventListener('change',render));render();root.dataset.ltReady='true';
 new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
 const resize=()=>{primary.resize();secondary.resize();};new ResizeObserver(resize).observe(root);window.addEventListener('resize',resize);
}
