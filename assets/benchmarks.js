(function(g){
  g.runBenchmarks = function(){
    if(!g.ANALYSIS_DATA || !g.ANALYSIS_DATA._bench){alert("keine Benchmarks");return;}
    const runs=g.ANALYSIS_DATA._bench.runs||[];
    const out=document.getElementById('out');
    out.innerHTML = `<h2>Benchmarks</h2>` + runs.map(r=>`<div><span class="badge">${r.name}</span>
      <table><tr><th>Familie</th><th>Score</th></tr>${r.top_clusters.map(([f,s])=>`<tr><td>${f}</td><td>${(+s).toFixed(2)}</td></tr>`).join('')}</table></div>`).join('');
  };
})(window);