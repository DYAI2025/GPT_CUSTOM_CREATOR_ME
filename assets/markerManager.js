(function(){
  const VALID_TYPES = ["ATO", "SEM", "CLU", "MEMA", "DETECT"];
  const state = {
    markers: new Map(),
    focusProfiles: [],
    modelProfiles: [],
    markersJson: null,
    focusJson: null,
    modelsJson: null,
  };

  const markerPreview = document.getElementById('markerPreview');
  const focusPreview = document.getElementById('focusPreview');
  const modelPreview = document.getElementById('modelPreview');
  const catalogPreview = document.getElementById('catalogPreview');
  const downloadMarkersBtn = document.getElementById('btnDownloadMarkers');
  const downloadFocusBtn = document.getElementById('btnDownloadFocus');
  const downloadModelsBtn = document.getElementById('btnDownloadModels');
  const exportCanonicalBtn = document.getElementById('btnExportCanonical');

  // ------------------------------------------------------------------ helpers
  function parseText(text, filename){
    if(!text){
      return null;
    }
    const trimmed = text.trim();
    if(!trimmed){
      return null;
    }
    const isYaml = filename?.endsWith('.yaml') || filename?.endsWith('.yml');
    const forceYaml = !filename && /:\s/.test(trimmed) && !trimmed.trim().startsWith('{');
    try{
      if(isYaml || forceYaml){
        return jsyaml.load(trimmed);
      }
      return JSON.parse(trimmed);
    }catch(err){
      alert(`Error parsing ${filename || 'text'}: ${err}`);
      return null;
    }
  }

  function normaliseMarker(raw, sourceName){
    if(!raw || typeof raw !== 'object') return null;
    const id = raw.id || raw.name;
    let type = raw.type || inferTypeFromName(sourceName || id || '');
    if(!id || !type) return null;
    type = String(type).toUpperCase();
    if(!VALID_TYPES.includes(type)) return null;
    const marker = { id: String(id), type };
    const fields = ['regex','pattern','patterns','tags','examples','composed_of','span_strategy','activation','notes','weight'];
    for(const key of fields){
      if(key in raw && raw[key] !== undefined && raw[key] !== null && raw[key] !== ''){
        const value = raw[key];
        if(Array.isArray(value)){
          marker[key] = value.filter(v => v !== null && v !== undefined && v !== '');
        }else if(typeof value === 'string' && ['pattern','patterns','tags','examples','composed_of'].includes(key)){
          marker[key] = [value];
        }else{
          marker[key] = value;
        }
      }
    }
    return marker;
  }

  function inferTypeFromName(name){
    const parts = String(name).split(/[\\/]/);
    for(let i = parts.length - 1; i >= 0; i--){
      const part = parts[i].toUpperCase();
      const head = part.split('_', 1)[0];
      if(VALID_TYPES.includes(head)) return head;
    }
    return null;
  }

  function snapshotMarkers(){
    const list = Array.from(state.markers.values()).sort((a,b)=>{
      if(a.type === b.type){ return a.id.localeCompare(b.id); }
      return a.type.localeCompare(b.type);
    });
    state.markersJson = list;
    markerPreview.textContent = JSON.stringify(list, null, 2);
    downloadMarkersBtn.disabled = list.length === 0;
    updateCatalogPreview();
  }

  function snapshotFocus(profiles){
    state.focusProfiles = profiles;
    state.focusJson = profiles;
    focusPreview.textContent = JSON.stringify(profiles, null, 2);
    downloadFocusBtn.disabled = !profiles.length;
    updateCatalogPreview();
  }

  function snapshotModels(models){
    state.modelProfiles = models;
    state.modelsJson = models;
    modelPreview.textContent = JSON.stringify(models, null, 2);
    downloadModelsBtn.disabled = !models.length;
    updateCatalogPreview();
  }

  function updateCatalogPreview(){
    const version = document.getElementById('catalogVersion').value || '1.0';
    const spec = document.getElementById('catalogSpec').value || 'Marker Canonical';
    const payload = {
      version,
      ld_spec: spec,
      updated_at: new Date().toISOString(),
      markers: state.markersJson || [],
    };
    if(state.focusProfiles.length) payload.focus_profiles = state.focusProfiles;
    if(state.modelProfiles.length) payload.model_profiles = state.modelProfiles;
    exportCanonicalBtn.disabled = (payload.markers.length === 0);
    catalogPreview.textContent = JSON.stringify(payload, null, 2);
  }

  function downloadJSON(filename, data){
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function parseFocus(text){
    const data = parseText(text);
    if(!data) return [];
    const profiles = data.profiles || data;
    const out = [];
    if(typeof profiles !== 'object') return out;
    for(const [name, spec] of Object.entries(profiles)){
      if(!spec || typeof spec !== 'object') continue;
      const profile = { name };
      if(spec.description) profile.description = String(spec.description);
      if(spec.marker_weights && typeof spec.marker_weights === 'object'){
        profile.marker_weights = normaliseNumberMap(spec.marker_weights);
      }
      if(spec.tag_weights && typeof spec.tag_weights === 'object'){
        profile.tag_weights = normaliseNumberMap(spec.tag_weights);
      }
      if(spec.type_weights && typeof spec.type_weights === 'object'){
        profile.type_weights = normaliseNumberMap(spec.type_weights, true);
      }
      out.push(profile);
    }
    return out;
  }

  function parseModels(text){
    const data = parseText(text);
    if(!data) return [];
    const models = data.models || data;
    const out = [];
    if(typeof models !== 'object') return out;
    for(const [name, spec] of Object.entries(models)){
      if(!spec || typeof spec !== 'object') continue;
      const model = { name };
      if(spec.description) model.description = String(spec.description);
      if(spec.system_prompt) model.system_prompt = String(spec.system_prompt);
      if(spec.focus_profile) model.focus_profile = String(spec.focus_profile);
      if(spec.default_mode) model.default_mode = String(spec.default_mode);
      const extra = {};
      for(const [key, value] of Object.entries(spec)){
        if(['description','system_prompt','focus_profile','default_mode'].includes(key)) continue;
        extra[key] = value;
      }
      if(Object.keys(extra).length) model.extra = extra;
      out.push(model);
    }
    return out;
  }

  function normaliseNumberMap(map, upperKeys=false){
    const out = {};
    for(const [key, value] of Object.entries(map)){
      const num = Number(value);
      if(Number.isFinite(num)){
        out[upperKeys ? key.toUpperCase() : key] = num;
      }
    }
    return out;
  }

  function loadMarkersFromText(text, sourceName){
    const parsed = parseText(text, sourceName);
    if(!parsed) return;
    const items = Array.isArray(parsed) ? parsed : [parsed];
    let added = 0;
    for(const item of items){
      const marker = normaliseMarker(item, sourceName);
      if(marker){
        state.markers.set(marker.id, marker);
        added++;
      }
    }
    if(added){
      snapshotMarkers();
    }
  }

  function resetMarkers(){
    state.markers.clear();
    state.markersJson = [];
    markerPreview.textContent = '';
    downloadMarkersBtn.disabled = true;
    updateCatalogPreview();
  }

  // ------------------------------------------------------------------ events
  document.getElementById('markerFiles').addEventListener('change', (evt)=>{
    const files = Array.from(evt.target.files || []);
    if(!files.length) return;
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = () => loadMarkersFromText(reader.result, file.name);
      reader.readAsText(file);
    });
    evt.target.value = '';
  });

  document.getElementById('btnParseMarkers').addEventListener('click', ()=>{
    const text = document.getElementById('markerText').value;
    loadMarkersFromText(text, 'manual');
  });

  document.getElementById('btnClearMarkers').addEventListener('click', resetMarkers);

  downloadMarkersBtn.addEventListener('click', ()=>{
    if(state.markersJson){
      downloadJSON('markers.json', state.markersJson);
    }
  });

  document.getElementById('btnParseFocus').addEventListener('click', ()=>{
    const profiles = parseFocus(document.getElementById('focusText').value);
    snapshotFocus(profiles);
  });

  downloadFocusBtn.addEventListener('click', ()=>{
    if(state.focusJson){
      downloadJSON('focus_profiles.json', state.focusJson);
    }
  });

  document.getElementById('btnParseModels').addEventListener('click', ()=>{
    const models = parseModels(document.getElementById('modelText').value);
    snapshotModels(models);
  });

  downloadModelsBtn.addEventListener('click', ()=>{
    if(state.modelsJson){
      downloadJSON('model_profiles.json', state.modelsJson);
    }
  });

  exportCanonicalBtn.addEventListener('click', ()=>{
    const version = document.getElementById('catalogVersion').value || '1.0';
    const spec = document.getElementById('catalogSpec').value || 'Marker Canonical';
    const payload = {
      version,
      ld_spec: spec,
      updated_at: new Date().toISOString(),
      markers: state.markersJson || [],
    };
    if(state.focusProfiles.length) payload.focus_profiles = state.focusProfiles;
    if(state.modelProfiles.length) payload.model_profiles = state.modelProfiles;
    downloadJSON('markers_canonical.json', payload);
  });

  document.getElementById('btnLoadCanonical').addEventListener('click', ()=>{
    document.getElementById('canonicalFile').click();
  });

  document.getElementById('canonicalFile').addEventListener('change', (evt)=>{
    const file = evt.target.files?.[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = ()=>{
      try{
        const data = JSON.parse(reader.result);
        if(Array.isArray(data.markers)){
          state.markers.clear();
          data.markers.forEach(item => {
            const marker = normaliseMarker(item, item.id);
            if(marker) state.markers.set(marker.id, marker);
          });
          snapshotMarkers();
        }
        if(Array.isArray(data.focus_profiles)){
          snapshotFocus(data.focus_profiles);
          document.getElementById('focusText').value = JSON.stringify({profiles: data.focus_profiles}, null, 2);
        }
        if(Array.isArray(data.model_profiles)){
          snapshotModels(data.model_profiles);
          document.getElementById('modelText').value = JSON.stringify({models: data.model_profiles}, null, 2);
        }
        if(data.ld_spec) document.getElementById('catalogSpec').value = data.ld_spec;
        if(data.version) document.getElementById('catalogVersion').value = data.version;
      }catch(err){
        alert('Konnte Datei nicht laden: ' + err);
      }
    };
    reader.readAsText(file);
    evt.target.value = '';
  });

  document.getElementById('catalogVersion').addEventListener('input', updateCatalogPreview);
  document.getElementById('catalogSpec').addEventListener('input', updateCatalogPreview);

  // initial render
  updateCatalogPreview();
})();
