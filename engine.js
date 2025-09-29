// CARL MarkerEngine – deterministische Pipeline
// Anforderungen: Unicode-NFC, RFC8259 JSON, JSON Schema 2020-12, SHA-256
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createHash } from "crypto";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Hilfen
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const toNFC = (s) => (typeof s === "string" ? s.normalize("NFC") : s);
const sha256Hex = (buf) => createHash("sha256").update(buf).digest("hex");

// Lade Single Source of Truth
const CARL_DIR = __dirname;
const CANON_PATH = process.env.CANON_PATH
  ? path.resolve(process.env.CANON_PATH)
  : path.join(CARL_DIR, "markers_canonical.json");
const WEIGHTS_PATH = path.join(CARL_DIR, "weights.json");
const INPUT_SCHEMA_PATH = path.join(CARL_DIR, "schema.input.json");
const OUTPUT_SCHEMA_PATH = path.join(CARL_DIR, "schema.output.json");

// Ajv Setup (2020-12)
const ajv = new Ajv2020({
  strict: true,
  allErrors: true,
  validateFormats: true,
});
addFormats(ajv);

// Register Schemas
const weightsSchema = readJson(WEIGHTS_PATH);
ajv.addSchema(weightsSchema, "https://carl/schema/weights");
const inputSchema = readJson(INPUT_SCHEMA_PATH);
const outputSchema = readJson(OUTPUT_SCHEMA_PATH);
const validateInput = ajv.compile(inputSchema);
const validateOutput = ajv.compile(outputSchema);

// Engine Version Hash (deterministisch aus engine.js + schemas)
function computeEngineHash() {
  const parts = [
    fs.readFileSync(__filename),
    fs.readFileSync(OUTPUT_SCHEMA_PATH),
    fs.readFileSync(INPUT_SCHEMA_PATH),
  ];
  return sha256Hex(Buffer.concat(parts));
}

function hashStringNFC(s) {
  return sha256Hex(Buffer.from(toNFC(s || ""), "utf8"));
}

function hashObjectCanonical(o) {
  const json = JSON.stringify(o);
  return sha256Hex(Buffer.from(json, "utf8"));
}

function computeInputHash(payload) {
  // Input kann text oder segments enthalten
  const text = toNFC(payload.text || "");
  const segments = Array.isArray(payload.segments)
    ? payload.segments.map((s) => ({ who: s.who, text: toNFC(s.text) }))
    : null;
  const combined = JSON.stringify({ text, segments });
  return sha256Hex(Buffer.from(combined, "utf8"));
}

function stableSegmentFromText(text) {
  // Parse "Name: Inhalt" pro Zeile
  const lines = toNFC(text).split(/\r?\n/);
  const res = [];
  for (const line of lines) {
    const m = line.match(/^\s*([^:]{1,40})\s*:\s*(.+)$/);
    if (m) {
      const whoRaw = m[1].trim().toLowerCase();
      const who = whoRaw.startsWith("a")
        ? "A"
        : whoRaw.startsWith("b")
        ? "B"
        : "other";
      res.push({ who, text: m[2] });
    } else if (line.trim().length) {
      res.push({ who: "other", text: line.trim() });
    }
  }
  return res;
}

function buildGlobalText(segments) {
  const sep = "\n";
  const text = segments.map((s) => s.text).join(sep);
  const indexOffsets = [];
  let off = 0;
  for (const s of segments) {
    indexOffsets.push(off);
    off += s.text.length + sep.length;
  }
  return { text, indexOffsets, sep };
}

function detect_all(segments, canon) {
  // pure function: nutzt ausschließlich canon.markers
  const { text, indexOffsets, sep } = buildGlobalText(segments);
  const out = [];
  let segIdx = 0;
  for (const seg of segments) {
    const base = indexOffsets[segIdx];
    const segText = seg.text;
    for (const mk of canon.markers) {
      if (mk.type === "DETECT" || mk.type === "ATO" || mk.type === "SEM") {
        if (mk.regex) {
          const baseFlags = mk.flags || canon.globals?.regex_flags || "iu";
          const flags = baseFlags.includes("g") ? baseFlags : baseFlags + "g";
          const reAll = new RegExp(mk.regex, flags);
          let m;
          const str = segText;
          while ((m = reAll.exec(str)) !== null) {
            const start = base + m.index;
            const end = start + (m[0]?.length || 0);
            out.push({
              id: mk.id,
              type: mk.type,
              span: { start, end },
              segment_idx: segIdx,
              who: seg.who,
              evidence: m[0] || "",
            });
            if (!reAll.global) break;
          }
        }
      }
    }
    segIdx++;
  }
  // Sortierung nach span.start
  out.sort((a, b) => a.span.start - b.span.start || a.span.end - b.span.end);
  return out;
}

function applyPromotion(segments, detected, canon, promoMap) {
  const promotions = [];
  const bySeg = new Map();
  detected.forEach((ev) => {
    if (!bySeg.has(ev.segment_idx)) bySeg.set(ev.segment_idx, []);
    bySeg.get(ev.segment_idx).push(ev);
  });

  const rules = [...(canon.promotion_rules || [])];
  if (promoMap?.map?.length) {
    for (const r of promoMap.map) {
      if (r.promote && Array.isArray(r.from_ATO_ids)) {
        rules.push({
          target: r.promote,
          when: {
            segment_co_occurs: {
              ids: r.from_ATO_ids,
              min: r.when?.segment_co_occurs?.min_ATO || 2,
            },
          },
          produce: { id: r.promote, type: "SEM", link_from: r.from_ATO_ids },
        });
      }
    }
  }

  for (const [segIdx, events] of bySeg.entries()) {
    for (const rule of rules) {
      const ids = rule.when?.segment_co_occurs?.ids || [];
      const min = rule.when?.segment_co_occurs?.min || 2;
      const have = events.filter((e) => ids.includes(e.id));
      if (have.length >= min) {
        const baseEv = have[0];
        promotions.push({
          sem_id: rule.produce.id,
          from_atos: have.map((h) => h.id),
          segment_idx: segIdx,
          who: baseEv.who,
        });
      }
    }
  }
  return promotions;
}

function annotateClustersAndMemory(detected, promotions, canon) {
  const ann = [];
  const semInSeg = new Map();
  promotions.forEach((p) => {
    const k = p.segment_idx;
    if (!semInSeg.has(k)) semInSeg.set(k, new Set());
    semInSeg.get(k).add(p.sem_id);
  });
  const rules = canon.annotation_rules || [];
  for (const [segIdx, semSet] of semInSeg.entries()) {
    for (const r of rules) {
      if (r.target_type === "SEM") {
        for (const semId of semSet) {
          // Tags werden aus dem Kanon geholt
          const semDef = canon.markers.find((m) => m.id === semId);
          const tags = new Set(semDef?.tags || []);
          const any = (r.when_tags_any_of || []).some((t) => tags.has(t));
          if (any) {
            for (const add of r.annotate || []) {
              ann.push({
                type: add.type,
                id: add.id,
                segment_idx: segIdx,
                who: "other",
              });
            }
          }
        }
      }
    }
  }
  return ann;
}

function computeCounts(segments, markersAll) {
  const total = { ATO: 0, SEM: 0, CLU: 0, MEMA: 0 };
  const bySpeaker = { A: {}, B: {} };
  const bySegment = [];
  for (let i = 0; i < segments.length; i++) bySegment.push({});
  for (const m of markersAll) {
    if (total[m.type] != null) total[m.type]++;
    if (m.who === "A" || m.who === "B") {
      bySpeaker[m.who][m.type] = (bySpeaker[m.who][m.type] || 0) + 1;
    }
    const bag = bySegment[m.segment_idx];
    bag[m.type] = (bag[m.type] || 0) + 1;
  }
  return { total, by_speaker: bySpeaker, by_segment: bySegment };
}

function computeDensity(globalText, counts) {
  const textLen = globalText.length;
  const per1k = (n) => (textLen > 0 ? (n * 1000) / textLen : 0);
  return {
    text_len: textLen,
    per_1k_chars: {
      ATO: per1k(counts.total.ATO),
      SEM: per1k(counts.total.SEM),
      CLU: per1k(counts.total.CLU),
      MEMA: per1k(counts.total.MEMA),
    },
  };
}

function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

function computeFeatures(canon, counts, density) {
  // Features: Dichte pro 1k Zeichen, dann auf [0,1] skaliert anhand caps
  const caps = canon.globals?.text_caps || {
    ATO: 100,
    SEM: 100,
    CLU: 100,
    MEMA: 100,
  };
  function scale(n, cap) {
    return clamp01(n / cap);
  }
  const d = density?.per_1k_chars || { ATO: 0, SEM: 0, CLU: 0, MEMA: 0 };
  return {
    ATO: scale(d.ATO, caps.ATO),
    SEM: scale(d.SEM, caps.SEM),
    CLU: scale(d.CLU, caps.CLU),
    MEMA: scale(d.MEMA, caps.MEMA),
  };
}

function dot(w, f) {
  return w.ATO * f.ATO + w.SEM * f.SEM + w.CLU * f.CLU + w.MEMA * f.MEMA;
}

function normalCdf(x) {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}
function erf(x) {
  // Abramowitz-Stegun 7.1.26
  const sign = Math.sign(x);
  const a1 = 0.254829592,
    a2 = -0.284496736,
    a3 = 1.421413741,
    a4 = -1.453152027,
    a5 = 1.061405429,
    p = 0.3275911;
  const t = 1 / (1 + p * Math.abs(x));
  const y =
    1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}

function computeIndices(weights, features, options = {}) {
  const res = {};
  for (const key of ["trust", "deesc", "conflict", "sync"]) {
    const def = weights.indices[key];
    const raw = dot(def.w, features) + def.bias;
    const mu = weights.calib.mu[key];
    const sigma = weights.calib.sigma[key] || 1e-9;
    const z = (raw - mu) / sigma;
    const p = clamp01(normalCdf(z));
    res[key] = options.omitP ? { raw, z } : { raw, z, p };
  }
  return res;
}

function gateOutput(markersAll, segments) {
  const enoughMarkers =
    markersAll.filter((m) => ["ATO", "SEM", "CLU", "MEMA"].includes(m.type))
      .length >= 5;
  const enoughSegs = (segments?.length || 0) >= 2;
  return !(enoughMarkers && enoughSegs);
}

function uniqId(prefix, n) {
  return prefix + "_" + n.toString(36);
}

function arrangeMarkersForOutput(detected, promotions, annotations) {
  const outputMarkers = [];
  let n = 0;
  for (const d of detected) {
    outputMarkers.push({ ...d, promotion_of: [] });
  }
  for (const p of promotions) {
    outputMarkers.push({
      id: p.sem_id,
      type: "SEM",
      span: { start: 0, end: 0 },
      segment_idx: p.segment_idx,
      who: p.who,
      promotion_of: p.from_atos,
      evidence: "",
    });
  }
  for (const a of annotations) {
    outputMarkers.push({
      id: a.id,
      type: a.type,
      span: { start: 0, end: 0 },
      segment_idx: a.segment_idx,
      who: a.who,
      promotion_of: [],
      evidence: "",
    });
  }
  return outputMarkers;
}

function toSegments(input) {
  if (Array.isArray(input.segments) && input.segments?.length) {
    return input.segments.map((s) => ({ who: s.who, text: toNFC(s.text) }));
  }
  if (typeof input.text === "string" && input.text.trim().length) {
    return stableSegmentFromText(input.text);
  }
  return [];
}

function modeAdjustments(mode, weights) {
  // Modusabhängige Gewichtungen (deterministisch):
  // dialog (Standard), single/coach, learn, free
  const clone = JSON.parse(JSON.stringify(weights));
  // Versuche Konfiguration aus modes.json zu lesen
  let modes = null;
  try {
    const cfg = readJson(path.join(CARL_DIR, "modes.json"));
    modes = cfg?.modes || null;
  } catch (_) {}
  function scaleAll(mult) {
    for (const k of ["trust", "deesc", "conflict", "sync"]) {
      const w = clone.indices[k].w;
      w.ATO *= mult.ATO;
      w.SEM *= mult.SEM;
      w.CLU *= mult.CLU;
      w.MEMA *= mult.MEMA;
    }
  }
  const key = (mode || "dialog").toLowerCase();
  if (modes && modes[key]) {
    const conf = modes[key];
    scaleAll(conf.weights_scaling || { ATO: 1, SEM: 1, CLU: 1, MEMA: 1 });
    if (conf.calib_adjust) {
      const mu = conf.calib_adjust.mu;
      const sigma = conf.calib_adjust.sigma;
      if (typeof mu === "number" || typeof sigma === "number") {
        for (const k of ["trust", "deesc", "conflict", "sync"]) {
          if (typeof mu === "number") clone.calib.mu[k] = mu;
          if (typeof sigma === "number") clone.calib.sigma[k] = sigma;
        }
      }
    }
  } else {
    switch (key) {
      case "dialog":
        break;
      case "single":
      case "coach":
        scaleAll({ ATO: 1.0, SEM: 1.2, CLU: 1.0, MEMA: 1.2 });
        break;
      case "learn":
        scaleAll({ ATO: 1.0, SEM: 1.0, CLU: 1.0, MEMA: 1.0 });
        for (const k of ["trust", "deesc", "conflict", "sync"]) {
          clone.calib.mu[k] = 0.5;
          clone.calib.sigma[k] = 0.25;
        }
        break;
      case "free":
        scaleAll({ ATO: 0.8, SEM: 0.8, CLU: 0.8, MEMA: 0.8 });
        break;
      default:
        break;
    }
  }
  return clone;
}

export function run(input, options = {}) {
  const t0 = Date.now();
  // Normalisieren und validieren Input
  const normalized = { ...input };
  if (typeof normalized.text === "string")
    normalized.text = toNFC(normalized.text);
  if (Array.isArray(normalized.segments))
    normalized.segments = normalized.segments.map((s) => ({
      who: s.who,
      text: toNFC(s.text),
    }));

  if (!validateInput(normalized)) {
    const err = ajv.errorsText(validateInput.errors, { separator: "\n" });
    throw new Error("Input-Validierung fehlgeschlagen:\n" + err);
  }

  const canon = readJson(CANON_PATH);
  const canon_hash = hashObjectCanonical(canon);
  const weightsFile = readJson(WEIGHTS_PATH);
  // Gewichte: aus Input, sonst aus weights.json (examples[0] oder Root)
  const defaultWeights =
    weightsFile && weightsFile.indices && weightsFile.calib
      ? weightsFile
      : Array.isArray(weightsFile?.examples) && weightsFile.examples[0]
      ? weightsFile.examples[0]
      : null;
  if (!defaultWeights)
    throw new Error(
      "Gewichte nicht gefunden: weights.json enthält weder Root noch examples[0]"
    );

  const mode = options.mode || "dialog";
  const baseWeights = normalized.weights || defaultWeights;
  const weights = modeAdjustments(mode, baseWeights);
  const promoMap = readJson(path.join(CARL_DIR, "promotion_mapping.json"));

  const segments = toSegments(normalized);
  const input_hash = computeInputHash({ text: normalized.text, segments });
  const engine_hash = computeEngineHash();

  // Detection
  const detected = detect_all(segments, canon);
  // Promotion
  const promotions = applyPromotion(segments, detected, canon, promoMap);
  // Annotation (CLU/MEMA)
  const annotations = annotateClustersAndMemory(detected, promotions, canon);

  // Output Marker konsolidieren
  const markers = arrangeMarkersForOutput(detected, promotions, annotations);

  // Counts/Density/Features/Indices
  const globalText = segments.map((s) => s.text).join("\n");
  const counts = computeCounts(segments, markers);
  const density = computeDensity(globalText, counts);
  const features = computeFeatures(canon, counts, density);
  const gated = gateOutput(markers, segments);
  const indices = computeIndices(weights, features, { omitP: gated });

  const out = {
    meta: {
      input_hash,
      canon_hash,
      engine_hash,
      elapsed_ms: Date.now() - t0,
      gated,
    },
    segments,
    markers,
    promotion: promotions,
    counts,
    density,
    features,
    indices,
  };

  if (!validateOutput(out)) {
    const err = ajv.errorsText(validateOutput.errors, { separator: "\n" });
    throw new Error("Output-Validierung fehlgeschlagen:\n" + err);
  }
  return out;
}

// Exporte für Tests
export const __internals = {
  detect_all,
  applyPromotion,
  annotateClustersAndMemory,
  computeCounts,
  computeDensity,
  computeFeatures,
  computeIndices,
  gateOutput,
  modeAdjustments,
};
