import * as echarts from "echarts/core";
import { LineChart,BarChart,ScatterChart } from "echarts/charts";
import { GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,DatasetComponent,AriaComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { deriveChartModels,selectResults,selectWindowOptions,summarizeWindows } from "./dashboard-state.mjs";

echarts.use([LineChart,BarChart,ScatterChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,DatasetComponent,AriaComponent,CanvasRenderer]);

export async function mountPerformanceDashboard(root){
  const {locale,t}=JSON.parse(root.querySelector("[data-dashboard-config]").textContent);
  const study={results:[...document.querySelectorAll("#study [data-study-id]")].map(node=>JSON.parse(node.dataset.facts))};
  const curves=(await import("../data/real-data-series.v1.json")).default;
  const controls=Object.fromEntries([...root.querySelectorAll("[data-filter]")].map(node=>[node.dataset.filter,node]));
  const nodes=Object.fromEntries([...root.querySelectorAll("[data-chart]")].map(node=>[node.dataset.chart,node]));
  const charts=Object.fromEntries(Object.entries(nodes).map(([key,node])=>[key,echarts.init(node)]));
  const gross=root.querySelector("[data-toggle-gross]");
  const zoom=root.querySelector("[data-zoom-window]");
  const format=new Intl.NumberFormat(locale,{maximumFractionDigits:2,minimumFractionDigits:2});
  const percent=value=>format.format(value*100)+"%";
  const navFormat=new Intl.NumberFormat(locale,{minimumFractionDigits:4,maximumFractionDigits:4});
  const seriesLabel=strategy=>t.strategies[strategy]??strategy;
  let zoomPercent=100,zoomStart=0,zoomEnd=100;
  const selection=()=>({market:controls.market.value,strategy:controls.strategy.value,feeBps:Number(controls.fee.value),windowStart:controls.window.value});
  const options=(node,values,wanted)=>{
    node.replaceChildren(...values.map(({value,label})=>new Option(label,value)));
    node.value=values.some(option=>option.value===wanted)?wanted:values[0]?.value??"";
  };
  function syncControls(reset=false){
    if(reset)controls.market.value="US";
    const market=controls.market.value;
    const rows=study.results.filter(row=>row.market===market&&row.status==="completed");
    const strategies=[...new Set(rows.map(row=>row.strategy))].sort();
    const wanted=reset?"buy_hold":controls.strategy.value;
    options(controls.strategy,strategies.map(value=>({value,label:seriesLabel(value)})),strategies.includes(wanted)?wanted:(market==="crypto"?"equal_weight":"buy_hold"));
    const fees=[...new Set(rows.map(row=>row.cost_bps))].sort((a,b)=>a-b);
    options(controls.fee,fees.map(value=>({value:String(value),label:`${value} bps`})),reset?"20":(fees.includes(Number(controls.fee.value))?controls.fee.value:String(market==="HK"?30:market==="crypto"?10:20)));
    const windows=selectWindowOptions(selectResults(study,selection()));
    options(controls.window,windows.map(w=>({value:w.start,label:`${w.start} – ${w.end}`})),reset?"":controls.window.value);
  }
  function palette(){
    const probe=document.createElement("span");probe.style.visibility="hidden";root.append(probe);
    const resolve=name=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
    const colors={ink:resolve("--ink"),muted:resolve("--muted"),line:resolve("--line"),paper:resolve("--surface")};
    probe.remove();return colors;
  }
  let colors;
  function base(){
    const p=colors??palette();
    return {animation:false,aria:{enabled:true},backgroundColor:"transparent",color:["#39a886","#6e9fe7","#e5a456","#ca86bd","#8cbf72"],textStyle:{color:p.ink,fontFamily:"Segoe UI, Microsoft YaHei, sans-serif"},grid:{left:58,right:22,top:40,bottom:64},tooltip:{trigger:"axis",renderMode:"richText",backgroundColor:p.paper,textStyle:{color:p.ink}},legend:{textStyle:{color:p.muted},top:0},xAxis:{type:"category",axisLabel:{color:p.muted,hideOverlap:true},axisLine:{lineStyle:{color:p.line}}},yAxis:{type:"value",axisLabel:{color:p.muted},splitLine:{lineStyle:{color:p.line}}}};
  }
  function set(key,patch){charts[key].setOption({...base(),...patch},{notMerge:true});}
  function render(){
    colors=palette();
    const model=deriveChartModels(study,curves,selection());
    const row=model.selected;
    if(!row){root.querySelector("[data-chart-status]").textContent=t.empty;return;}
    root.querySelector("[data-dashboard-selected]").dataset.facts=JSON.stringify(row);
    for(const node of root.querySelectorAll("[data-metric]")){
      const value=row[node.dataset.metric];
      node.textContent=value===null?"—":node.dataset.metric==="sharpe"?format.format(value):percent(value);
    }
    root.querySelector("[data-selection-note]").textContent=`${row.quote_currency} · ${row.start} – ${row.end} · ${row.sessions} ${t.periods}`;
    const summary=summarizeWindows(study,selection());
    const stability=root.querySelector("[data-stability]");stability.dataset.count=String(summary.count);stability.dataset.summary=JSON.stringify(summary);
    for(const node of stability.querySelectorAll("[data-stability-metric]")){const key=node.dataset.stabilityMetric;node.textContent=key==="count"?String(summary.count):summary[key]===null?"—":percent(summary[key]);}
    root.querySelector("[data-stability-denominator]").textContent=`${summary.excessCount} ${t.insights.denominator}`;
    root.querySelector("[data-strategy-description]").textContent=t.descriptions[row.market==="crypto"&&row.strategy==="equal_weight"?"crypto_equal_weight":row.strategy];
    root.dataset.grossVisible=String(gross.checked);
    const points=model.curve?.points??[];
    nodes.nav.dataset.points=JSON.stringify(points);
    root.querySelector("[data-curve-unavailable]").hidden=Boolean(model.curve);
    zoom.disabled=!model.curve;
    nodes.nav.dataset.range=JSON.stringify({start:zoomStart,end:zoomEnd});
    const dataZoom=[{type:"inside",start:zoomStart,end:zoomEnd},{type:"slider",start:zoomStart,end:zoomEnd,height:18,bottom:5}];
    set("nav",{tooltip:{...base().tooltip,valueFormatter:value=>navFormat.format(value)},xAxis:{...base().xAxis,data:points.map(p=>p.date)},yAxis:{...base().yAxis,scale:true},legend:{...base().legend,data:[t.net,t.gross],selected:{[t.gross]:gross.checked}},dataZoom,series:[{name:t.net,type:"line",showSymbol:false,data:points.map(p=>p.net_nav)},{name:t.gross,type:"line",showSymbol:false,lineStyle:{type:"dashed"},data:points.map(p=>p.gross_nav)}]});
    set("drawdown",{tooltip:{...base().tooltip,valueFormatter:percent},xAxis:{...base().xAxis,data:points.map(p=>p.date)},yAxis:{...base().yAxis,axisLabel:{formatter:percent}},dataZoom,series:[{name:t.charts.drawdown,type:"line",showSymbol:false,areaStyle:{opacity:.18},data:points.map(p=>p.drawdown)}]});
    set("folds",{tooltip:{...base().tooltip,valueFormatter:percent},xAxis:{...base().xAxis,data:model.foldReturns.map(r=>r.start)},yAxis:{...base().yAxis,axisLabel:{formatter:percent}},legend:{...base().legend,data:[t.net,t.excess]},series:[{name:t.net,type:"bar",data:model.foldReturns.map(r=>r.net_return)},{name:t.excess,type:"bar",data:model.foldReturns.map(r=>r.excess_return)}]});
    set("fees",{tooltip:{...base().tooltip,valueFormatter:percent},xAxis:{...base().xAxis,data:model.feeSensitivity.map(r=>`${r.cost_bps} bps`)},yAxis:{...base().yAxis,axisLabel:{formatter:percent}},series:[{name:t.net,type:"bar",data:model.feeSensitivity.map(r=>r.net_return)}]});
    set("scatter",{tooltip:{...base().tooltip,trigger:"item",formatter:params=>`${seriesLabel(params.data.strategy)}\n${params.data.start}\n${t.net}: ${percent(params.value[1])}\n${t.metrics.max_drawdown}: ${percent(params.value[0])}`},xAxis:{...base().xAxis,type:"value",name:t.metrics.max_drawdown,nameLocation:"middle",nameGap:35,axisLabel:{formatter:percent}},yAxis:{...base().yAxis,axisLabel:{formatter:percent}},series:[...new Set(model.scatter.map(r=>r.strategy))].map(strategy=>({name:seriesLabel(strategy),type:"scatter",symbolSize:8,data:model.scatter.filter(r=>r.strategy===strategy).map(r=>({value:[r.max_drawdown,r.net_return],strategy,start:r.start,jobId:r.job_id}))}))});
    set("turnover",{tooltip:{...base().tooltip,valueFormatter:percent},xAxis:{...base().xAxis,data:model.foldReturns.map(r=>r.start)},yAxis:{...base().yAxis,axisLabel:{formatter:percent}},series:[{name:t.charts.turnover,type:"bar",data:model.foldReturns.map(r=>r.mean_daily_oneway_turnover_proxy)}]});
    set("exposure",{tooltip:{...base().tooltip,valueFormatter:percent},xAxis:{...base().xAxis,data:model.foldReturns.map(r=>r.start)},yAxis:{...base().yAxis,min:0,max:1,axisLabel:{formatter:percent}},series:[{name:t.charts.exposure,type:"bar",data:model.foldReturns.map(r=>r.mean_exposure)}]});
    set("histogram",{xAxis:{...base().xAxis,data:model.histogram.map(bin=>`${percent(bin.low)} – ${percent(bin.high)}`)},yAxis:{...base().yAxis,minInterval:1},series:[{name:t.windows,type:"bar",data:model.histogram.map(bin=>bin.count)}]});
    root.querySelector("[data-chart-status]").textContent=t.ready;
    root.dataset.ready="true";
  }
  charts.nav.group=charts.drawdown.group="portfolio-window";
  echarts.connect("portfolio-window");
  for(const chart of [charts.nav,charts.drawdown])chart.on("datazoom",event=>{
    const range=event.batch?.[0]??event;
    if(Number.isFinite(range.start)&&Number.isFinite(range.end)){
      zoomStart=range.start;zoomEnd=range.end;nodes.nav.dataset.range=JSON.stringify({start:zoomStart,end:zoomEnd});zoomPercent=Math.round(range.end-range.start);zoom.value=String(zoomPercent);root.dataset.zoom=String(zoomPercent);
    }
  });
  for(const control of Object.values(controls))control.addEventListener("change",()=>{syncControls();zoomPercent=100;zoomStart=0;zoomEnd=100;zoom.value="100";root.dataset.zoom="100";render();});
  charts.nav.on("legendselectchanged",event=>{gross.checked=event.selected[t.gross]!==false;root.dataset.grossVisible=String(gross.checked);});
  gross.addEventListener("change",()=>{root.dataset.grossVisible=String(gross.checked);charts.nav.dispatchAction({type:gross.checked?"legendSelect":"legendUnSelect",name:t.gross});});
  zoom.addEventListener("input",()=>{zoomPercent=Number(zoom.value);zoomStart=100-zoomPercent;zoomEnd=100;root.dataset.zoom=String(zoomPercent);charts.nav.dispatchAction({type:"dataZoom",start:100-zoomPercent,end:100});});
  root.querySelector("[data-reset]").addEventListener("click",()=>{syncControls(true);gross.checked=true;zoomPercent=100;zoomStart=0;zoomEnd=100;zoom.value="100";root.dataset.zoom="100";render();});
  new MutationObserver(render).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change",render);
  new ResizeObserver(()=>Object.values(charts).forEach(chart=>chart.resize())).observe(root);
  root.querySelector("fieldset").disabled=false;
  syncControls();render();
}
