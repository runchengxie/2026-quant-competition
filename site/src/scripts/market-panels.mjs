const names={hk:'HK',us:'US',crypto:'crypto'};

export function marketForHash(hash){
 try{const key=decodeURIComponent(hash).replace(/^#market-/,'');return Object.hasOwn(names,key)?names[key]:null;}catch{return null;}
}

export function mountMarketPanels(root){
 const links=[...root.querySelectorAll('[data-market-link]')],panels=[...root.querySelectorAll('[data-market-panel]')];
 if(links.length!==3||panels.length!==3)throw new Error('Incomplete market navigation');
 const nav=root.querySelector('[data-market-navigation]');nav.setAttribute('role','tablist');
 function show(market,focus=false){
  if(!Object.values(names).includes(market))throw new RangeError('Unknown market');
  root.dataset.currentMarket=market;
  for(const panel of panels){panel.hidden=panel.dataset.marketPanel!==market;panel.setAttribute('role','tabpanel');}
  for(const link of links){const active=link.dataset.marketLink===market;link.setAttribute('role','tab');link.setAttribute('aria-selected',String(active));link.tabIndex=active?0:-1;if(active&&focus)link.focus();}
  requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
 }
 function fromHash(){
  let target;try{target=document.getElementById(decodeURIComponent(location.hash.slice(1)));}catch{return;}
  const market=marketForHash(location.hash)||target?.closest('[data-market-panel]')?.dataset.marketPanel;
  if(market){show(market);requestAnimationFrame(()=>target?.scrollIntoView({block:'start'}));}
 }
 for(const [index,link] of links.entries()){
  link.addEventListener('click',event=>{event.preventDefault();history.pushState(null,'',link.getAttribute('href'));show(link.dataset.marketLink);});
  link.addEventListener('keydown',event=>{
   const next=event.key==='ArrowRight'?(index+1)%3:event.key==='ArrowLeft'?(index+2)%3:event.key==='Home'?0:event.key==='End'?2:null;
   if(next===null)return;event.preventDefault();history.pushState(null,'',links[next].getAttribute('href'));show(links[next].dataset.marketLink,true);
  });
 }
 show('US');fromHash();window.addEventListener('hashchange',fromHash);window.addEventListener('popstate',fromHash);
 root.dataset.marketReady='true';
}
