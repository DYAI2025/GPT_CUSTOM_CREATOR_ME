/* helpers */
export function fmt(n){ try{ return Number(n).toFixed(2);}catch(_){return n} }
export function text(s){ return (s||"").toString() }
export function pickQuotes(segments, hits, k=2){
  const out=[]; const unique=new Set();
  (hits||[]).slice(0,10).forEach(h=>{
    const segIdx = h.meta?.segment ?? 0;
    const seg = segments?.[segIdx] || "";
    if(seg && out.length<k && !unique.has(seg)){ out.push(seg.slice(0,180)); unique.add(seg); }
  });
  return out;
}
export function colorByFamily(f){
  return {SUPPORT:"#54d2a5",CONFLICT:"#ff6b6b",UNCERTAINTY:"#ffd166"}[f] || "#6ea8fe";
}
export function buildHeatCells(heatmap){
  const max = Math.max(1,...(heatmap||[]).map(b=> (b.dens?.SEM||0)+(b.dens?.CLU||0)+(b.dens?.MEMA||0)));
  return (heatmap||[]).map(b=>{
    const v=(b.dens?.SEM||0)+(b.dens?.CLU||0)+(b.dens?.MEMA||0);
    const lvl = v===0?0 : v/max>0.8?4 : v/max>0.55?3 : v/max>0.3?2 : 1;
    return `<div class="cell" data-lvl="${lvl}"><span title="SEM:${b.dens?.SEM||0} CLU:${b.dens?.CLU||0} MEMA:${b.dens?.MEMA||0}"></span></div>`;
  }).join("");
}
export function highlightWithMarkers(text, clu){
  let html = (text||"").replace(/[&<>"]/g, m=>({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;" }[m]));
  (clu||[]).forEach(h=>{
    const tag = h.family?.toLowerCase();
    if(!tag) return;
    const re = new RegExp(`(${tag})`,"gi");
    html = html.replace(re, `<mark>$1</mark>`);
  });
  return html;
}