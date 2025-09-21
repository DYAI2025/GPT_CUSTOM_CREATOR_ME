// Runtime: baut Dashboard-Payload und injiziert in analyse.HTML
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function build_dashboard_payload(engineOutput){
  const out = engineOutput;
  return {
    meta: out.meta,
    phases: [],
    overview: { indices: out.indices, features: out.features, counts: out.counts, density: out.density },
    individuals: { A: (out.counts?.by_speaker?.A)||{}, B: (out.counts?.by_speaker?.B)||{} },
    system: {},
    change: {},
    closing: {}
  };
}

export function derive_pair_benchmarks(engineOutput){
  return { trust: null, deesc: null, conflict: null, sync: null };
}

export function render_to_html(engineOutput, { htmlPath } = {}){
  const p = htmlPath || path.join(__dirname, 'analyse.HTML');
  const html = fs.readFileSync(p, 'utf8');
  const payload = build_dashboard_payload(engineOutput);
  const inj = `\n<script>window.ANALYSIS_DATA = ${JSON.stringify(payload)}; try{ renderDashboard(); }catch(e){ console.error(e); }</script>\n`;
  return html.replace(/<\/body>\s*<\/html>\s*$/i, inj + '</body></html>');
}


