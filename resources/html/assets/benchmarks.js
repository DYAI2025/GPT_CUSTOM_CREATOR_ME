window.runBenchmarks = function(bench){
  if(!bench || !bench.runs){ alert("Keine Benchmarks"); return; }
  const out = bench.runs.map(r=>`
    <li><span class="badge">${r.name}</span>
    ${r.top_clusters.map(([f,s])=>`<span class="badge">${f}: ${Number(s).toFixed(2)}</span>`).join(" ")}</li>`).join("");
  const el = document.getElementById("changePoints");
  el.innerHTML = `<h3>Benchmarks</h3><ul class="list">${out}</ul>`;
};