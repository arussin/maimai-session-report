/* Prepared cards only: no engine, catalog loading or account access. */
(() => {
  'use strict';
  const view=JSON.parse(document.getElementById('report-data').textContent).preparedRecommendations;
  const host=document.getElementById('targets-view'),legacy=host?.querySelector('.practice-layout');
  if(!view?.cards?.length || !legacy) return;
  const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const section=make('section',undefined,'prepared-targets');section.setAttribute('aria-label','Prepared recommendations');
  section.append(make('h2','Next targets'),make('p',`Prepared ${new Date(view.cutoff_ms).toISOString().slice(0,10)} · Conditional gains compete for the same rating slots. Reachability is unverified.`,'section-subtitle'));
  const grid=make('div',undefined,'prepared-card-grid');section.append(grid);
  for(const card of view.cards){
    const article=make('article',undefined,'prepared-card');
    article.append(make('span',{rating:'Rating up',practice:'Pattern practice',discovery:'Discover'}[card.category],'prepared-kind'),make('h3',card.title),make('p',`${card.difficulty} · ${card.format} · Lv ${card.level}`));
    if(card.target!=null)article.append(make('strong',`${card.target.toFixed(4)}%`,'prepared-goal'));
    else article.append(make('p',card.category==='practice'?'Practice the prepared pattern goal':'Explore a structural neighbor'));
    if(card.gain!=null)article.append(make('p',`+${card.gain} rating if achieved`));
    if(card.previous!=null)article.append(make('p',`PB ${card.previous.toFixed(4)}%`,'section-subtitle'));
    if(view.browser){
      const query=new URLSearchParams({catalog:view.catalog.id,version:view.catalog.version,chart:card.chart_id});
      const link=make('a','Explore chart');link.href=`${view.browser.scheme}://${view.browser.host}${view.browser.path}?${query}`;
      link.rel='noopener noreferrer';link.target='_blank';article.append(link);
    }
    grid.append(article);
  }
  legacy.before(section);
  const details=make('details',undefined,'prepared-session-details');details.append(make('summary','Session snapshot suggestions and difficulty profile'));
  legacy.before(details);details.append(legacy);
})();
