"""Flask web application for the marker manager."""
from __future__ import annotations

from flask import Flask, jsonify, render_template_string, request

from .service import MarkerManagerService


def create_app(service: MarkerManagerService) -> Flask:
    app = Flask(__name__)
    app.config["MARKER_SERVICE"] = service

    @app.route("/")
    def index():
        return render_template_string(_DASHBOARD_HTML)

    @app.get("/api/status")
    def api_status():
        return jsonify(service.status_payload())

    @app.post("/api/upload")
    def api_upload():
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "no files provided"}), 400
        for storage in files:
            filename = storage.filename or "uploaded.yaml"
            content = storage.stream.read().decode("utf-8")
            service.write_yaml_blob(filename, content)
        result = service.rebuild_after_write()
        return jsonify(result.summary())

    @app.post("/api/paste")
    def api_paste():
        payload = request.get_json(force=True)
        filename = payload.get("filename", "pasted.yaml")
        content = payload.get("content", "")
        service.write_yaml_blob(filename, content)
        result = service.rebuild_after_write()
        return jsonify(result.summary())

    @app.post("/api/build")
    def api_build():
        result = service.sync()
        return jsonify(result.summary())

    @app.post("/api/focus")
    def api_focus():
        payload = request.get_json(force=True)
        name = payload.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        info = service.set_focus_schema(name)
        return jsonify(info)

    @app.post("/api/model")
    def api_model():
        payload = request.get_json(force=True)
        name = payload.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        info = service.set_model_profile(name)
        return jsonify(info)

    @app.get("/api/diff")
    def api_diff():
        return jsonify(service.diff_last())

    @app.get("/api/logs")
    def api_logs():
        limit = int(request.args.get("limit", 50))
        return jsonify(service.recent_logs(limit))

    return app


_DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Marker Manager</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
      h1 { margin-bottom: 1rem; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.5rem; }
      .card { background: #1e293b; padding: 1.5rem; border-radius: 1rem; box-shadow: 0 15px 30px rgba(15, 23, 42, 0.4); }
      label { display: block; margin-bottom: 0.5rem; font-weight: 600; }
      input[type="file"], textarea, select { width: 100%; padding: 0.75rem; border-radius: 0.75rem; border: 1px solid #334155; background: #0f172a; color: #f8fafc; }
      textarea { min-height: 160px; }
      button { padding: 0.75rem 1.5rem; border-radius: 999px; border: none; background: linear-gradient(135deg, #22d3ee, #6366f1); color: #0f172a; font-weight: 700; cursor: pointer; margin-top: 0.75rem; }
      button.secondary { background: transparent; border: 1px solid #334155; color: #e2e8f0; }
      #logs { max-height: 200px; overflow-y: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 0.85rem; background: #0f172a; padding: 1rem; border-radius: 0.75rem; }
      .status { display: flex; flex-direction: column; gap: 0.5rem; }
      .status-list { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.25rem; color: #94a3b8; font-size: 0.85rem; }
      .pill { background: rgba(148, 163, 184, 0.2); border-radius: 999px; padding: 0.35rem 0.75rem; display: inline-block; }
    </style>
  </head>
  <body>
    <h1>Marker Manager Dashboard</h1>
    <div class="grid">
      <div class="card">
        <h2>Status</h2>
        <div class="status" id="status"></div>
        <button id="refresh">Refresh</button>
        <button id="build" class="secondary">Build Canonical</button>
      </div>
      <div class="card">
        <h2>Upload YAML</h2>
        <label for="file-input">Drag & drop or choose files</label>
        <input type="file" id="file-input" multiple>
        <button id="upload">Upload</button>
        <h3 style="margin-top:1.5rem">Paste YAML</h3>
        <textarea id="paste"></textarea>
        <input type="text" id="paste-name" placeholder="pasted.yaml" style="margin-top:0.75rem">
        <button id="paste-btn">Save & Build</button>
      </div>
      <div class="card">
        <h2>Schemas & Models</h2>
        <label for="focus">Focus Schema</label>
        <select id="focus"></select>
        <label for="model" style="margin-top:1rem">Model Profile</label>
        <select id="model"></select>
      </div>
      <div class="card">
        <h2>History</h2>
        <pre id="diff" style="white-space:pre-wrap"></pre>
      </div>
      <div class="card" style="grid-column:1/-1">
        <h2>Logs</h2>
        <div id="logs"></div>
      </div>
    </div>
    <script>
      async function fetchStatus() {
        const response = await fetch('/api/status');
        const data = await response.json();
        const statusEl = document.getElementById('status');
        const metrics = data.metrics || {};
        const lastBuild = metrics.last_build_ts ? new Date(metrics.last_build_ts * 1000).toLocaleString() : '—';
        const resultSummary = data.result ? `${data.result.count} marker · ok=${data.result.ok}` : '—';
        const conflictDetails = metrics.conflicts || [];
        const hashDisplay = metrics.hash_canonical ? `${metrics.hash_canonical.slice(0, 12)}…` : '—';
        statusEl.innerHTML = `
          <div><span class="pill">Source</span> ${data.config.source_dir}</div>
          <div><span class="pill">Canonical</span> ${data.config.canonical_json}</div>
          <div><span class="pill">Backups</span> ${data.config.backup_dir}</div>
          <div><span class="pill">Focus</span> ${data.focus.active || '—'}</div>
          <div><span class="pill">Model</span> ${data.model.active || '—'}</div>
          <div><span class="pill">Last Build</span> ${lastBuild}</div>
          <div><span class="pill">Markers</span> ${metrics.items_total ?? '—'}</div>
          <div><span class="pill">Dedupe Hits</span> ${metrics.dedupe_hits ?? 0}</div>
          <div><span class="pill">Conflicts</span> ${conflictDetails.length}</div>
          <div><span class="pill">Hash</span> ${hashDisplay}</div>
          <div><span class="pill">Last Result</span> ${resultSummary}</div>
        `;
        const inputFiles = (metrics.input_files || []).map(entry => `<div>${entry}</div>`).join('');
        if (inputFiles) {
          statusEl.innerHTML += `<div><span class="pill">Inputs</span><div class="status-list">${inputFiles}</div></div>`;
        }
        if (conflictDetails.length) {
          const details = conflictDetails.map(entry => `<div>${entry}</div>`).join('');
          statusEl.innerHTML += `<div><span class="pill">Conflict Details</span><div class="status-list">${details}</div></div>`;
        }
        populateSelect('focus', data.focus.available, data.focus.active, '/api/focus');
        populateSelect('model', data.model.available, data.model.active, '/api/model');
        fetchDiff();
        fetchLogs();
      }

      async function populateSelect(id, options, active, endpoint) {
        const select = document.getElementById(id);
        select.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select';
        select.appendChild(placeholder);
        options.forEach(opt => {
          const option = document.createElement('option');
          option.value = opt;
          option.textContent = opt;
          if (opt === active) option.selected = true;
          select.appendChild(option);
        });
        select.onchange = async (event) => {
          if (!event.target.value) return;
          await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: event.target.value })
          });
          fetchStatus();
        };
      }

      async function uploadFiles() {
        const input = document.getElementById('file-input');
        if (!input.files.length) return alert('Select at least one file');
        const body = new FormData();
        for (const file of input.files) body.append('files', file);
        const response = await fetch('/api/upload', { method: 'POST', body });
        const data = await response.json();
        alert(JSON.stringify(data, null, 2));
        fetchStatus();
      }

      async function pasteYaml() {
        const content = document.getElementById('paste').value;
        const filename = document.getElementById('paste-name').value || 'pasted.yaml';
        if (!content.trim()) return alert('Nothing to save');
        const response = await fetch('/api/paste', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename, content })
        });
        const data = await response.json();
        alert(JSON.stringify(data, null, 2));
        fetchStatus();
      }

      async function buildCanonical() {
        const response = await fetch('/api/build', { method: 'POST' });
        const data = await response.json();
        alert(JSON.stringify(data, null, 2));
        fetchStatus();
      }

      async function fetchDiff() {
        const response = await fetch('/api/diff');
        const data = await response.json();
        const diffEl = document.getElementById('diff');
        diffEl.textContent = data.patch || 'No diff available';
      }

      async function fetchLogs() {
        const response = await fetch('/api/logs');
        const data = await response.json();
        const logsEl = document.getElementById('logs');
        logsEl.innerHTML = data.map(entry => `${new Date(entry.timestamp * 1000).toLocaleTimeString()} :: ${entry.type} :: ${JSON.stringify(entry.payload)}`).join('\n');
      }

      document.getElementById('refresh').onclick = fetchStatus;
      document.getElementById('build').onclick = buildCanonical;
      document.getElementById('upload').onclick = uploadFiles;
      document.getElementById('paste-btn').onclick = pasteYaml;
      fetchStatus();
    </script>
  </body>
</html>
"""
