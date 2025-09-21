// Intuition-CLU Erweiterung (LEAN.DEEP 3.4)
// Pure functions, deterministisch. Keine Seiteneffekte.

/**
 * Prozessiert Intuition-Cluster-Zustände aus Events (insb. SEM/CLU-kontext) und annotiert sie.
 * opts: {
 *   confirm_window: number,   // Anzahl aufeinanderfolgender Segmente bis "confirmed"
 *   decay_window: number,     // TTL in Segmenten bis "decayed"
 *   family_map: Record<string,string>, // Marker-ID -> Familienkey
 *   multiplier: number        // Faktor für applyFamilyMultiplier
 * }
 * @param {Array} events - Engine-Marker (id,type,segment_idx,who,...)
 * @param {object} opts   - Optionen
 * @returns {{events:Array, telemetry:{confirmed:number,retracted:number,ewma_precision:number}}}
 */
export function processIntuitionClu(events, opts){
  const confirmWindow = Math.max(1, opts?.confirm_window ?? 2);
  const decayWindow = Math.max(1, opts?.decay_window ?? 4);
  const multiplier = Number.isFinite(opts?.multiplier) ? opts.multiplier : 1.1;
  const familyMap = opts?.family_map || {};

  const famState = new Map(); // familyKey -> { lastSeg, streak, state: 'provisional'|'confirmed'|'decayed' }
  let confirmed = 0, retracted = 0;

  // sort by segment_idx for deterministic traversal
  const evs = [...events].sort((a,b)=> (a.segment_idx - b.segment_idx) || (a.span?.start||0)-(b.span?.start||0));
  const augmented = [];

  for (const ev of evs){
    const fam = familyMap[ev.id] || null;
    if (!fam) { augmented.push(ev); continue; }

    const st = famState.get(fam) || { lastSeg: ev.segment_idx, streak: 0, state: 'provisional' };
    // decay check
    if (ev.segment_idx - st.lastSeg > decayWindow) {
      if (st.state === 'confirmed') retracted++;
      st.state = 'decayed';
      st.streak = 0;
    }
    // update streak if same family seen
    st.streak = (st.state === 'decayed') ? 1 : (st.streak + 1);
    st.lastSeg = ev.segment_idx;
    if (st.state !== 'confirmed' && st.streak >= confirmWindow) {
      st.state = 'confirmed';
      confirmed++;
    } else if (st.state === 'decayed') {
      st.state = 'provisional';
    }
    famState.set(fam, st);

    augmented.push({ ...ev, meta: { ...(ev.meta||{}), intuition_state: st.state, intuition_family: fam } });
  }

  // naive EWMA precision proxy: confirmed / (confirmed + retracted + 1)
  const ewma_precision = confirmed / (confirmed + retracted + 1);
  return { events: augmented, telemetry: { confirmed, retracted, ewma_precision } };
}

/**
 * Wendet einen Multiplikator je nach Intuitionszustand an. Wirkt nur in confirmed-Phase.
 * @param {Record<string,{raw:number,z?:number,p?:number}>} indices
 * @param {'provisional'|'confirmed'|'decayed'} state
 * @param {number} multiplier
 */
export function applyFamilyMultiplier(indices, state, multiplier){
  if (state !== 'confirmed') return indices;
  const m = Number.isFinite(multiplier) ? multiplier : 1.0;
  const out = {};
  for (const k of Object.keys(indices)){
    const v = indices[k];
    out[k] = { ...v, raw: v.raw * m };
  }
  return out;
}


