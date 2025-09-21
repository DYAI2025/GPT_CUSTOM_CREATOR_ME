(function(g){
  function row([k,v]){return `<tr><td>${k}</td><td>${(+v).toFixed ? (+v).toFixed(2) : v}</td></tr>`;}
  g.renderDashboard = function(data){
    const out=document.getElementById('out'); if(!data||!data.result){out.innerHTML="keine Daten";return;}
    const sum=data.result.summary||{};
    const det=data.result.details||{};
    const html = `
      <h2>Top Cluster</h2>
      <table><tr><th>Familie</th><th>Score</th></tr>${(sum.top_clusters||[]).map(row).join('')}</table>
      <h2>Drift</h2><pre>${esc(JSON.stringify(sum.drift||{},null,2))}</pre>
      <h2>Highlights</h2><div id="hl"></div>
      <h2>SEM</h2><pre>${esc(JSON.stringify(det.sem||[],null,2))}</pre>
      <h2>CLU</h2><pre>${esc(JSON.stringify(det.clu||[],null,2))}</pre>`;
    out.innerHTML = html;
    if(data.raw_text){document.getElementById('hl').innerHTML = highlightText(data.raw_text, det.clu||[]);}
  };
  function esc(s){return s.replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));}
})(window);