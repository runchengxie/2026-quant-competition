import {matches} from './tree-study-state.mjs';
for(const section of document.querySelectorAll('[data-tree-study]')) {
  const controls=section.querySelector('[data-tree-controls]');
  const filters=[...controls.querySelectorAll('[data-tree-filter]')];
  const apply=()=>{
    const selection=Object.fromEntries(filters.map(select=>[select.dataset.treeFilter,select.value]));
    for(const row of section.querySelectorAll('[data-tree-row]')) row.hidden=!matches(row.dataset,selection);
    const summary=section.querySelector('[data-tree-context-summary]');
    summary.textContent=filters.map(select=>`${select.dataset.treeLabel}: ${select.selectedOptions[0].textContent}`).join(' · ');
    summary.hidden=false;
  };
  for(const select of filters) select.addEventListener('change',apply);
  controls.hidden=false;
  apply();
  section.dataset.treeReady='true';
}
