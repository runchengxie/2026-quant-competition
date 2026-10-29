export async function mountCnnChart(root) {
 const plot=root.querySelector('[data-cnn-chart]');
 const fallback=root.querySelector('[data-cnn-fallback]');
 const controls=root.querySelector('[data-cnn-controls]');
 const select=root.querySelector('[data-cnn-select]');
 try {
  const config=JSON.parse(root.querySelector('[data-cnn-config]').textContent);
  const echarts=await import('echarts');
  plot.hidden=false;
  const chart=echarts.init(plot);
  const styles=['solid','dashed','dotted'];
  const ymax=Math.ceil(Math.max(...config.series.flatMap(item=>item.values))/50)*50;
  const update=()=>{
   const choice=select.value;
   root.dataset.selection=choice;
   const dark=getComputedStyle(document.body).backgroundColor==='rgb(23, 27, 32)';
   const ink=dark?'#e9ebec':'#334155';
   const colors=dark?['#c4a5ff','#62d5c4','#f9bd72']:['#6d28d9','#087f73','#b45309'];
   chart.setOption({
    color:colors,
    animation:false,
    tooltip:{trigger:'axis',valueFormatter:value=>Number(value).toFixed(2)},
    legend:{data:config.names,selectedMode:false,selected:Object.fromEntries(config.series.map((item,index)=>[config.names[index],choice==='all'||choice===item.strategy])),textStyle:{color:ink},top:4},
    grid:{left:48,right:24,top:55,bottom:70,containLabel:true},
    xAxis:{type:'category',data:config.dates,axisLabel:{color:ink,hideOverlap:true}},
    yAxis:{type:'value',min:0,max:ymax,axisLabel:{color:ink},splitLine:{lineStyle:{color:dark?'#475569':'#d8dee9'}}},
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:14,textStyle:{color:ink}}],
    series:config.series.map((item,index)=>({name:config.names[index],type:'line',data:item.values,showSymbol:false,
     lineStyle:{width:2.5,type:styles[index]},
     emphasis:{focus:'series'}}))
   });
  };
  update();
  select.addEventListener('change',update);
  window.addEventListener('resize',()=>chart.resize());
  new MutationObserver(update).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',update);
  controls.hidden=false;fallback.hidden=true;root.dataset.ready='true';
 } catch(error) {
  plot.hidden=true;controls.hidden=true;fallback.hidden=false;
  console.error('CNN chart unavailable; static chart and table remain available',error);
 }
}
