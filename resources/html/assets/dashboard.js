import {fmt,text,pickQuotes,colorByFamily,buildHeatCells,highlightWithMarkers} from './utils.js';

function asPairs(arr){ return Array.isArray(arr)? arr : []; }

function drawClusters(ctx, top){
  const labels = top.map(x=>x[0]); const values = top.map(x=>x[1]);
  const colors = labels.map(l=>colorByFamily(l));
  return new Chart(ctx, {type:"bar",
    data:{labels,datasets:[{data:values, backgroundColor:colors}]},
    options:{plugins:{legend:{display:false}},scales:{y:{min:0, max:1}}}
  });
}
function drawIndices(ctx, idx){
  const labels = ["trust","deesc","conflict","sync"];
  const data = labels.map(k=> idx?.[k] ?? 0);
  return new Chart(ctx,{type:"radar",
    data:{labels,datasets:[{data, borderColor:"#6ea8fe", backgroundColor:"rgba(110,168,254,.2)"}]},
    options:{plugins:{legend:{display:false}}, scales:{r:{min:-1,max:1}}}
  });
}
function drawAxes(ctx, axes){
  const labels = Object.keys(axes?.values||{});
  const data = labels.map(k=> axes.values[k]);
  return new Chart(ctx,{type:"bar",
    data:{labels,datasets:[{data, backgroundColor:"#a6b4ff"}]},
    options:{plugins:{legend:{display:false}},scales:{y:{min:-1,max:1}}}
  });
}
function drawBalance(ctx, bal){
  const kv=Object.entries(bal?.initiative_vs_support||{}); if(!kv.length) return;
  return new Chart(ctx,{type:"doughnut",
    data:{labels:kv.map(x=>x[0]),datasets:[{data:kv.map(x=>x[1]), backgroundColor:["#6ea8fe","#54d2a5","#ffd166","#ff6b6b"]}]},
    options:{plugins:{legend:{position:"bottom"}}}
  });
}
function drawLenses(ctx, lenses){
  const arr = (lenses||[]).slice(0,8);
  return new Chart(ctx,{type:"bar",
    data:{labels:arr.map(x=>x.lens),datasets:[{data:arr.map(x=>x.score), backgroundColor:"#54d2a5"}]},
    options:{indexAxis:"y", plugins:{legend:{display:false}}}
  });
}
function drawQuestionBadges(node, packs){
  if(!node) return;
  if(!packs || !packs.length){ node.innerHTML = '<span class="small">Keine Nachfragen geplant.</span>'; return; }
  node.innerHTML = packs.map(p=>{
    const asked = p.asked ?? 0;
    const answered = p.answered ?? 0;
    const promoted = p.promoted ?? 0;
    const pending = p.pending ?? Math.max(asked - answered, 0);
    return `<div class="badge-pack"><strong>${text(p.pack||'?')}</strong>`+
      `<span>${answered}/${asked} beantwortet</span>`+
      `<span>${pending} offen</span>`+
      `<span>${promoted} promoted</span></div>`;
  }).join("");
}
function drawQuestionAnswered(canvas, metrics){
  if(!canvas) return;
  const asked = metrics?.asked ?? 0;
  const answered = metrics?.answered ?? 0;
  if(asked <= 0 && answered <= 0){ canvas.classList.add('hidden'); return; }
  const remaining = Math.max(asked - answered, 0);
  new Chart(canvas, {type:"doughnut",
    data:{labels:["beantwortet","offen"], datasets:[{data:[answered, remaining], backgroundColor:["#54d2a5","#2f3760"]}]},
    options:{plugins:{legend:{position:"bottom"}}, cutout:"55%"}
  });
}
function drawQuestionPromoted(canvas, metrics){
  if(!canvas) return;
  const promoted = metrics?.promoted ?? 0;
  const cand = metrics?.cand ?? 0;
  if(promoted <= 0 && cand <= 0){ canvas.classList.add('hidden'); return; }
  const pending = Math.max(cand - promoted, 0);
  new Chart(canvas, {type:"doughnut",
    data:{labels:["promoted","cand"], datasets:[{data:[promoted, pending], backgroundColor:["#ffd166","#2f3760"]}]},
    options:{plugins:{legend:{position:"bottom"}}, cutout:"55%"}
  });
}
function renderFollowUp(node, followUp, questions){
  if(!node) return;
  const promos = {};
  (questions?.promotions || []).forEach(p=>{
    (p.questions||[]).forEach(q=>{
      if(!promos[q]) promos[q]=[];
      promos[q].push(p.to);
    });
  });
  const answered = (followUp?.items && followUp.items.length ? followUp.items : (questions?.qa_trace || [])).map(item=>({
    pack: item.pack,
    question: item.question,
    answer: item.answer,
    cand: item.cand || [],
    promoted: item.promoted || promos[item.id] || [],
    sequence: item.sequence
  }));
  const pending = questions?.to_ask || [];
  let html = '';
  if(answered.length){
    html += answered.map(item=>{
      const cand = (item.cand||[]).join(', ');
      const promoted = (item.promoted||[]).join(', ');
      return `<div class="qa-item"><span class="qa-pack">${text(item.pack||'?')}</span> ${text(item.question||'')}`+
        `<span class="qa-answer">${text(item.answer||'–')}</span>`+
        `<span class="qa-markers">CAND: ${cand||'—'}${promoted? ' · Promotion: '+promoted:''}</span></div>`;
    }).join("");
  }
  if(pending.length){
    const list = pending.map(item=> `<li><strong>${text(item.pack||'?')}</strong> ${text(item.prompt||'')}</li>`).join("");
    html += `<div class="qa-pending"><div class="qa-pending-title">Offene Nachfragen</div><ul>${list}</ul></div>`;
  }
  if(!html){
    html = '<span class="small">Keine Nachfragen erfasst.</span>';
  }
  node.innerHTML = html;
}
function renderTimeline(node, trace, pending){
  if(!node) return;
  const rows = [];
  (trace||[]).forEach(entry=>{
    rows.push(`<li><strong>#${entry.sequence ?? '?'} ${text(entry.pack||'')}</strong> — ${text(entry.question||'')}`+
              `<br><span class="small">Antwort: ${text(entry.answer||'–')}</span></li>`);
  });
  (pending||[]).forEach((entry, idx)=>{
    rows.push(`<li class="pending"><strong>→ ${text(entry.pack||'')}</strong> — ${text(entry.prompt||'')}`+
              `<br><span class="small">Status: offen</span></li>`);
  });
  node.innerHTML = rows.length ? rows.join("") : '<li>Keine Q&A erfasst</li>';
}

window.renderDashboard = function(data){
  const model = data.model || "unbekannt";
  const res = data.result || {};
  const sum = res.summary || {};
  const det = res.details || {};
  const eng = data.engine_result || {};
  const metaDiv = document.getElementById("meta");
  metaDiv.innerHTML = `<span class="badge">Modell: ${model}</span> <span class="badge">Top: ${asPairs(sum.top_clusters).map(p=>`${p[0]} ${fmt(p[1])}`).join(" · ")}</span>`;

  drawClusters(document.getElementById("chartClusters"), asPairs(sum.top_clusters));
  drawIndices(document.getElementById("chartIndices"), eng.indices || {});
  drawAxes(document.getElementById("chartAxes"), eng.drift_axes || {values:{}});
  document.getElementById("axesTrends").textContent = Object.entries((eng.drift_axes||{}).trend||{}).map(([k,v])=>`${k}: ${v}`).join(" · ") || "—";
  drawBalance(document.getElementById("chartBalance"), eng.balance || {});
  drawLenses(document.getElementById("chartLenses"), sum.lenses || []);

  const hm = eng.heatmap || [];
  document.getElementById("heatmap").innerHTML = buildHeatCells(hm);

  const cps = eng.change_points || [];
  document.getElementById("changePoints").innerHTML = cps.length
    ? cps.map(c=>`<li><strong>T${c.timestamp_or_seq ?? "?"}</strong> — ${text(c.micro_narrative_1liner)||"Wendepunkt"} <span class="badge">${(c.involved_markers||[]).join(", ")}</span></li>`).join("")
    : `<li>keine markanten Wendepunkte erkannt</li>`;

  const raw = data.raw_text || "";
  const hl = highlightWithMarkers(raw, det.clu || []);
  document.getElementById("highlights").innerHTML = hl || "—";

  const questions = eng.questions || {};
  drawQuestionBadges(document.getElementById("questionBadges"), (questions.metrics?.packs) || []);
  drawQuestionAnswered(document.getElementById("chartQuestionAnswered"), questions.metrics);
  drawQuestionPromoted(document.getElementById("chartQuestionPromoted"), questions.metrics);
  renderFollowUp(document.getElementById("questionFollowUp"), data.follow_up, questions);
  renderTimeline(document.getElementById("questionTimeline"), questions.qa_trace || [], questions.to_ask || []);
};
