import * as echarts from "echarts/core";
import {BarChart,ScatterChart} from "echarts/charts";
import {GridComponent,TooltipComponent,AriaComponent,DataZoomComponent} from "echarts/components";
import {CanvasRenderer} from "echarts/renderers";
import {selectAblations,summarizeAblations} from "./ablation-state.mjs";
echarts.use([BarChart,ScatterChart,GridComponent,TooltipComponent,AriaComponent,DataZoomComponent,CanvasRenderer]);

export function mountAblationCharts(root){
 const {locale,t}=JSON.parse(root.querySelector("[data-ablation-config]").textContent);
 const nodes=[...root.querySelectorAll("[data-ablation-id]")];
 const snapshot={results:nodes.map(n=>JSON.parse(n.dataset.facts))};
 const controls=Object.fromEntries([...root.querySelectorAll("[data-ablation-filter]")].map(n=>[n.dataset.ablationFilter,n]));
 const charts=Object.fromEntries([...root.querySelectorAll("[data-ablation-chart]")].map(n=>[n.dataset.ablationChart,echarts.init(n)]));
 const formatter=new Intl.NumberFormat(locale,{maximumFractionDigits:2,minimumFractionDigits:2});
 const show=v=>v===null?"—":formatter.format(v*100)+"%";
 const policy=id=>t.variants[id]??id;
 const label=g=>`${g.strategy} / ${policy(g.variant_id)} / ${g.cost_bps} ${t.costLabel}${g.evidence_role==="post_hoc_diagnostic"?" · "+t.roles.post_hoc_diagnostic:""}`;
 const selection=()=>({market:controls.market.value,feeBps:controls.fee.value===""?undefined:Number(controls.fee.value),strategy:controls.strategy.value||undefined,variantId:controls.variant.value||undefined,windowStart:controls.window.value||undefined});
 function options(node,values,wanted){node.replaceChildren(new Option(t.all,""),...values.map(([value,text])=>new Option(text,String(value))));node.value=["",...values.map(v=>String(v[0]))].includes(wanted)?wanted:"";}
 function sync(resetFee=false){
  const rows=snapshot.results.filter(r=>r.market===controls.market.value&&r.strategy!==null);
  options(controls.fee,[...new Set(rows.map(r=>r.cost_bps))].sort((a,b)=>a-b).map(v=>[v,`${v} ${t.costLabel}`]),resetFee?String(controls.market.value==="US"?20:controls.market.value==="HK"?30:10):controls.fee.value);
  options(controls.strategy,[...new Set(rows.map(r=>r.strategy))].sort().map(v=>[v,v]),controls.strategy.value);
  const available=rows.filter(r=>!controls.strategy.value||r.strategy===controls.strategy.value);
  options(controls.variant,[...new Set(available.map(r=>r.variant_id))].sort().map(v=>[v,policy(v)]),controls.variant.value);
  options(controls.window,[...new Map(available.map(r=>[r.start,[r.start,`${r.start} – ${r.end}`]])).values()].sort((a,b)=>b[0].localeCompare(a[0])),controls.window.value);
 }
 function summary(groups){
  const body=root.querySelector("[data-ablation-summary]");body.replaceChildren();
  for(const g of groups){
   const tr=document.createElement("tr");
   const values=[g.strategy,`${policy(g.variant_id)} · ${t.roles[g.evidence_role]}`,g.cost_bps,g.count,...[g.median_net_return,g.median_excess_return,g.median_paired_net_change,g.median_paired_drawdown_change,g.median_daily_turnover,g.median_exposure].map(show)];
   values.forEach((value,index)=>{const cell=document.createElement(index===0?"th":"td");cell.textContent=String(value);tr.append(cell);});body.append(tr);
  }
 }
 function draw(){
  const selected=selection(),rows=selectAblations(snapshot,selected),groups=summarizeAblations(snapshot,selected),ids=new Set(rows.map(r=>r.job_id));
  nodes.forEach(n=>{n.hidden=!ids.has(n.dataset.ablationId);});
  root.querySelectorAll("[data-ablation-market]").forEach(n=>{n.hidden=n.dataset.ablationMarket!==selected.market;});
  summary(groups);
  root.querySelector("[data-ablation-status]").textContent=t.ready.replace("{count}",new Intl.NumberFormat(locale).format(rows.length));
  // Resolve light-dark() through a styled element before passing colors to Canvas.
  const probe=document.createElement("span");probe.style.visibility="hidden";root.append(probe);
  const resolve=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const ink=resolve("--ink"),line=resolve("--line"),green=resolve("--green"),paper=resolve("--surface");probe.remove();
  root.dataset.chartColors=JSON.stringify({ink,line,green,paper});
  const common={animation:false,textStyle:{color:ink},backgroundColor:"transparent",aria:{enabled:true},tooltip:{trigger:"item",renderMode:"richText",backgroundColor:paper,borderColor:line,textStyle:{color:ink}}};
  const paired=groups.filter(g=>g.median_paired_net_change!==null);
  charts.paired.setOption({...common,grid:{left:55,right:25,top:25,bottom:95},xAxis:{type:"category",data:paired.map(label),axisLabel:{color:ink,rotate:25,width:115,overflow:"truncate"}},yAxis:{type:"value",axisLabel:{color:ink,formatter:v=>formatter.format(v*100)+"%"},splitLine:{lineStyle:{color:line}}},dataZoom:[{type:"inside",filterMode:"none"},{type:"slider",height:16,bottom:0,textStyle:{color:ink}}],series:[{type:"bar",name:t.paired,data:paired.map(g=>({value:g.median_paired_net_change,name:label(g),itemStyle:{color:g.evidence_role==="post_hoc_diagnostic"?"#b37a25":green}})),tooltip:{valueFormatter:show}}]},true);
  charts.risk.setOption({...common,grid:{left:65,right:25,top:30,bottom:65},xAxis:{type:"value",name:t.exposure,nameLocation:"middle",nameGap:35,nameTextStyle:{color:ink},axisLabel:{color:ink,formatter:v=>formatter.format(v*100)+"%"},splitLine:{lineStyle:{color:line}}},yAxis:{type:"value",axisLabel:{color:ink,formatter:v=>formatter.format(v*100)+"%"},splitLine:{lineStyle:{color:line}}},series:[{type:"scatter",name:t.turnover,symbolSize:13,data:groups.filter(g=>g.median_exposure!==null&&g.median_daily_turnover!==null).map(g=>({name:label(g),value:[g.median_exposure,g.median_daily_turnover],itemStyle:{color:g.evidence_role==="post_hoc_diagnostic"?"#b37a25":green}})),tooltip:{valueFormatter:show}}]},true);
  root.querySelector("[data-ablation-chart=paired]").dataset.model=JSON.stringify(groups);
  root.dataset.ready="true";
 }
 controls.market.addEventListener("change",()=>{controls.strategy.value="";controls.variant.value="";controls.window.value="";sync(true);draw();});
 for(const [key,node] of Object.entries(controls))if(key!=="market")node.addEventListener("change",()=>{if(key==="strategy"){controls.variant.value="";sync();}draw();});
 new ResizeObserver(()=>Object.values(charts).forEach(c=>c.resize())).observe(root);
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
 matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw);
 sync(true);draw();root.querySelector("[data-ablation-controls]").hidden=false;
}
