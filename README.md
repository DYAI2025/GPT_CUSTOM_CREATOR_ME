# CARL MarkerEngine

A comprehensive linguistic and emotional marker analysis engine for dialogue and text processing with therapeutic framework integration. CARL identifies patterns in German conversations and provides professional-grade psychological analysis tools.

## 🎯 Overview

CARL MarkerEngine analyzes text and dialogue to identify four levels of linguistic markers:

- **ATO (Atomic)** - Basic pattern detection (acknowledgments, questions, apologies)
- **SEM (Semantic)** - Higher-level patterns derived from ATO combinations
- **CLU (Cluster)** - Complex interaction patterns indicating alignment
- **MEMA (Memory/Meta)** - Empathy and memory-related markers

### 🔬 Advanced Analysis Features

**Psychological Indices:**
- **Trust** - Trustworthiness and reliability indicators
- **De-escalation** - Conflict reduction and calming patterns  
- **Conflict** - Tension, disagreement, and stress markers
- **Sync** - Dialogue synchronization and rapport level

**Drift Axes Analysis:**
- **Tension ↔ Calm** - Emotional state progression
- **Approach ↔ Avoid** - Engagement vs withdrawal patterns
- **Agency ↔ Communion** - Individual vs collective focus
- **Certainty ↔ Ambiguity** - Confidence vs uncertainty dynamics

**Therapeutic Framework Integration:**
- **CBCT (Cognitively-Based Compassion Training)** - Support and ambivalence detection
- **EFT (Emotionally Focused Therapy)** - Attunement and disorganization patterns
- **SFT (Solution-Focused Therapy)** - Protest and resistance identification
- **Gottman Method** - Four Horsemen relationship patterns

**Professional Features:**
- **Email Context Analysis** - Subject line, participants, power dynamics
- **Heatmap Visualization** - Marker density across conversation segments
- **Balance Analysis** - Speaker initiative and talk-time ratios
- **Change Point Detection** - Conversation shift identification
- **Validity Assessment** - Analysis confidence and gate validation
- **Blindspot Protocol** - Expert-level CAND_* marker filtering

## 🚀 Quick Start

### Prerequisites

- Node.js 14+ 
- Python 3.7+ (for marker building and Python orchestrator)
- Modern web browser (for dashboard viewing)
- PyYAML, Jinja2, jsonschema (for Python features)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd carl
```

2. Install Python dependencies:
```bash
pip install pyyaml jinja2 jsonschema
```

3. Build the marker database (one-time setup):
```bash
python3 build_markers_canonical.py
```

This loads 597 German linguistic markers from the `ALL_Marker_5.1/` directory.

4. Validate installation:
```bash
python3 validate.py
```

### Marker Management Toolkit (Drop-in)

The `marker_manager/` package replaces the previous ad-hoc scripts with a
drop-in toolchain that mirrors the production layout described in the project
specification.  It reads marker YAML from the LeanDeep source folder and keeps a
single canonical JSON artefact up-to-date while persisting backups and
supporting focus/model profiles.

#### Configuration

All commands share the same YAML configuration file.  The repository already
includes a ready-to-use example at `marker_manager/marker_manager_config.yaml`
with the canonical paths:

```yaml
source_dir: "/Users/benjaminpoersch/Projekte/.../Marker_LeanDeep3.4/"
canonical_json: "/Users/benjaminpoersch/Projekte/.../Marker_LeanDeep3.4/_canonical/markers_canonical.json"
backup_dir: "/Users/benjaminpoersch/Projekte/.../Marker_LeanDeep3.4/_canonical/backups/"
schema_file: "schemas/schema.markers.json"
focus_schemata_file: "schemas/focus_schemata.json"
models_dir: "resources/models"
```

Update the ellipses to match your local path only if the directory structure is
different.

#### CLI commands

Install the toolkit in editable mode and run one of the dedicated commands:

```bash
pip install -r requirements.txt

# 1) einmalig alles bauen
python -m marker_manager.cli sync -c marker_manager/marker_manager_config.yaml

# 2) Watch-Modus (Auto-Update bei YAML-Änderungen)
python -m marker_manager.cli watch -c marker_manager/marker_manager_config.yaml

# 3) Validieren ohne Schreiben
python -m marker_manager.cli validate -c marker_manager/marker_manager_config.yaml

# 4) GUI starten
python -m marker_manager.cli gui -c marker_manager/marker_manager_config.yaml  # http://localhost:5173
```

Every build is atomic: the CLI writes to a temporary file, performs an `fsync`
and replaces `markers_canonical.json` in one step while copying the previous
version into `_canonical/backups/`.

#### Browser GUI

Running `python -m marker_manager.cli gui ...` launches a lightweight Flask app
that exposes the REST endpoints required by the specification and serves a
single-page dashboard.  From the GUI you can:

- Drag & drop or paste YAML snippets which are saved into the configured
  `source_dir` and trigger an immediate rebuild.
- Toggle manual rebuilds, inspect the active focus schema/model profile and
  review the diff between the latest canonical artefact and its most recent
  backup (JSON Patch).
- Inspect recent events such as sync runs, uploads, watcher activity or errors.

### Basic Usage

#### Option 1: Command Line Analysis

```bash
# Create input file
echo '{"text": "A: Danke für deine Hilfe!\\nB: Gern geschehen!"}' > input.json

# Run analysis
node cli.js input.json > output.json

# View results
cat output.json | jq '.'
```

#### Option 2: Interactive Dashboard

```bash
# Generate HTML dashboard with analysis
node scripts/generate_dashboard.js input.json dashboard.html

# Open in browser
open dashboard.html  # macOS
xdg-open dashboard.html  # Linux
start dashboard.html  # Windows
```

#### Option 3: Python Orchestrator (Advanced Features)

```bash
# Run comprehensive analysis with Python orchestrator
PYTHONPATH=. python3 -c "
from orchestrator import ProjectGPT
from pathlib import Path
pg = ProjectGPT(Path('.'))
code, result = pg.start_routine('{\"text\": \"A: Ich brauche Unterstützung.\\\nB: Ich bin für dich da.\"}', 'default', 'SCH_TEXT')
print('Analysis complete:', code)
print('Indices:', result['analysis_data']['engine_result']['indices'])
print('Drift Axes:', result['analysis_data']['engine_result']['drift_axes'])
"
```

## 📖 Detailed Usage

### Input Format

CARL accepts JSON input with either single text or dialogue segments:

#### Single Text Format
```json
{
  "text": "A: Das ist eine gute Idee.\nB: Danke, das freut mich."
}
```

#### Segmented Dialogue Format  
```json
{
  "segments": [
    { "who": "A", "text": "Das ist eine gute Idee." },
    { "who": "B", "text": "Danke, das freut mich." }
  ]
}
```

### Analysis Modes

Different modes adjust weighting and calibration:

```bash
node cli.js --mode dialog input.json   # Default dialogue mode
node cli.js --mode single input.json   # Single speaker mode
node cli.js --mode coach input.json    # Coaching conversation
node cli.js --mode learn input.json    # Learning context
node cli.js --mode free input.json     # Free-form analysis
```

**Python Orchestrator Modes:**
- **easy** - Minimal analysis with core markers
- **advanced** - Standard professional analysis
- **expert** - Full analysis including CAND_* markers and blindspot detection

### Output Structure

The engine outputs detailed JSON with marker detection results:

```json
{
  "meta": {
    "input_hash": "...",      // Content hash for reproducibility
    "canon_hash": "...",      // Marker database version
    "engine_hash": "...",     // Engine version
    "elapsed_ms": 6,          // Processing time
    "gated": false            // Gate validation status
  },
  "segments": [...],          // Processed segments
  "markers": [               // Detected markers
    {
      "id": "ATO_ACK",
      "type": "ATO", 
      "span": {"start": 0, "end": 5},
      "segment_idx": 0,
      "who": "A",
      "evidence": "Danke"
    }
  ],
  "promotion": [...],         // Promoted markers (SEM, CLU)
  "counts": {                // Statistics
    "total": {"ATO": 5, "SEM": 2, "CLU": 1, "MEMA": 0},
    "by_speaker": {...},
    "by_segment": [...]
  },
  "density": {...},           // Marker density metrics
  "features": {...},          // Numerical features
  "indices": {...}            // Calculated indices
}
```

## 🎨 HTML Dashboard

The interactive dashboard provides visual analysis:

### Features
- **Top Clusters** - Most prominent communication patterns
- **Drift Analysis** - Conversation dynamics over time
- **Highlighted Text** - Visual marker identification
- **Detailed Breakdowns** - SEM, CLU, MEMA marker lists

### Dashboard Generation

```bash
# Generate with custom output path
node scripts/generate_dashboard.js input.json reports/analysis.html

# Assets are automatically copied
ls reports/
# analysis.html
# analysis_data.json
# assets/
```

### Dashboard Controls
- **Render** - Refresh visualization
- **Benchmarks** - View performance metrics
- **JSON Input** - Paste custom JSON for live analysis

## 🏗️ Architecture

### Core Components

```
carl/
├── JavaScript Engine
│   ├── cli.js                        # CLI entry point
│   ├── engine.js                     # Core analysis engine
│   ├── engine_intuition.js           # Extended pattern detection
│   └── markers_canonical.json        # 597 marker definitions
│
├── Python Orchestrator
│   ├── orchestrator.py               # Main orchestration system
│   ├── enginelib/runtime.py          # Advanced analysis runtime
│   └── validate.py                   # System validation
│
├── Configuration
│   ├── resources/config/
│   │   ├── weights.yaml              # Family weights
│   │   ├── axes_map.yaml             # Drift axes mapping
│   │   ├── promotion_mapping.yaml    # CLU name mappings
│   │   ├── Model-registry.json       # Model definitions
│   │   └── PROF_marker_axes.json     # Axis definitions
│   │
│   ├── resources/mappings/
│   │   ├── lenses_map.yaml           # Therapeutic frameworks
│   │   └── frame_mapping.yaml        # Framework mapping
│   │
│   └── resources/scorings/
│       └── scorings.yaml             # Index calculations
│
├── Scripts & Tools
│   ├── build_markers_canonical.py    # Marker compilation
│   └── generate_dashboard.js         # Dashboard generation
│
├── Web Interface
│   └── resources/html/
│       ├── analyse.HTML              # Dashboard template
│       └── assets/                   # CSS/JS visualization
│
├── Marker Database
│   └── ALL_Marker_5.1/              # Source marker definitions
│       ├── ATO_atomic/              # 281 atomic markers
│       ├── SEM_semantic/            # 203 semantic markers
│       ├── CLU_cluster/             # 75 cluster markers
│       └── MEMA_meta/               # 38 meta markers
│
└── Testing & Validation
    ├── tests/                       # Test suite
    ├── schemas/                     # JSON schemas
    └── resources/profiles/          # Analysis profiles
```

### Processing Pipeline

**JavaScript Engine:**
1. **Input Normalization** - Unicode NFC normalization
2. **Segmentation** - Split dialogue by speakers
3. **ATO Detection** - Regex-based atomic markers
4. **SEM Promotion** - Combine ATOs into semantic patterns
5. **CLU Formation** - Identify cluster patterns
6. **MEMA Analysis** - Meta-level patterns
7. **Output Generation** - JSON results

**Python Orchestrator (Advanced):**
1. **Engine Execution** - Run marker detection pipeline
2. **Index Calculation** - Compute trust, conflict, sync, de-escalation
3. **Drift Analysis** - Calculate 4-axis psychological dimensions
4. **Therapeutic Mapping** - Apply CBCT, EFT, SFT, Gottman lenses
5. **Heatmap Generation** - Bucket marker density visualization
6. **Balance Assessment** - Speaker dynamics and ratios
7. **Validity Check** - Gate validation and confidence metrics
8. **Email Context** - Extract metadata for email conversations
9. **Change Point Detection** - Identify conversation shifts
10. **HTML Integration** - Generate interactive dashboards

## 🔧 Advanced Configuration

### Custom Marker Sets

Add custom markers to `ALL_Marker_5.1/` directories:

```yaml
# ALL_Marker_5.1/ATO_atomic/CUSTOM_MARKER.yaml
id: ATO_CUSTOM
type: ATO
regex: "\\b(pattern1|pattern2)\\b"
tags: ["custom", "category"]
examples: ["pattern1 example", "pattern2 case"]
```

Rebuild after adding markers:
```bash
python3 build_markers_canonical.py
```

### Configuration Files

**Family Weights** (`resources/config/weights.yaml`):
```yaml
families:
  SUPPORT: 1.0
  CONFLICT: 1.0
  UNCERTAINTY: 0.8
```

**Drift Axes** (`resources/config/axes_map.yaml`):
```yaml
tension_calm:
  CONFLICT: 1.0
  SUPPORT: -0.6
  UNCERTAINTY: 0.2
approach_avoid:
  SUPPORT: 0.7
  CONFLICT: -0.4
  UNCERTAINTY: -0.3
```

**Therapeutic Lenses** (`resources/mappings/lenses_map.yaml`):
```yaml
SUPPORT: [CBCT.support, EFT.attunement]
CONFLICT: [SFT.protest, Gottman.four_horsemen]
UNCERTAINTY: [CBCT.ambivalence, EFT.disorganization]
```

**Index Calculations** (`resources/scorings/scorings.yaml`):
```yaml
trust:
  families: { SUPPORT: 0.7, UNCERTAINTY: -0.3, CONFLICT: -0.4 }
deesc:
  families: { SUPPORT: 0.6, CONFLICT: -0.6 }
conflict:
  families: { CONFLICT: 1.0 }
sync:
  families: { SUPPORT: 0.5, UNCERTAINTY: -0.2 }
```

### Schema Validation

The engine validates input/output against JSON schemas:
- `schema.input.json` - Input format validation
- `schema.output.json` - Output format validation
- `schema.markers.json` - Marker structure validation

## 📊 Marker Categories

### ATO (Atomic) Markers - Examples
- `ATO_ACK` - Acknowledgments ("danke", "okay", "verstanden")
- `ATO_APOLOGY` - Apologies ("entschuldigung", "tut mir leid")
- `ATO_QUESTION` - Questions ("warum", "wie", "was")

### SEM (Semantic) Markers - Examples
- `SEM_VALIDATION` - Validation patterns (multiple ACKs)
- `SEM_CONFLICT_EVIDENCE` - Conflict indicators
- `SEM_REPAIR` - Repair attempts

### CLU (Cluster) Markers - Examples
- `CLU_SUPPORT` - Support clusters
- `CLU_ALIGNMENT` - Alignment patterns
- `CLU_TENSION` - Tension clusters

### MEMA (Meta) Markers - Examples
- `MEMA_EMPATHY` - Empathy patterns
- `MEMA_MEMORY` - Memory references
- `MEMA_META_COMMUNICATION` - Meta-level communication

## 🧪 Testing

### Run Test Analysis

```bash
# Test with sample German dialogue
node cli.js test_german.json

# Test with minimal input
echo '{"text": "Hallo"}' | node cli.js

# Test HTML generation
node scripts/generate_dashboard.js test_german.json test.html
```

### Python Tests

```bash
# Run Python test suite with proper path
PYTHONPATH=. python3 tests/test_errors.py
PYTHONPATH=. python3 tests/test_chunking_gates.py
PYTHONPATH=. python3 tests/test_html_payload.py

# Validate complete system
python3 validate.py
```

## 🔍 Troubleshooting

### Common Issues

1. **No markers detected**
   - Run `python3 build_markers_canonical.py` to populate markers
   - Check input is in German (current marker set)
   - Verify JSON input format

2. **Dashboard not rendering**
   - Ensure assets folder is in same directory as HTML
   - Check browser console for errors
   - Verify data injection in HTML source

3. **JSON parsing errors**
   - Properly escape newlines: `\\n` not `\n`
   - Use valid JSON format
   - Test with `jq` tool: `cat input.json | jq '.'`

4. **Python orchestrator errors**
   - Use `PYTHONPATH=.` for imports
   - Install dependencies: `pip install pyyaml jinja2 jsonschema`
   - Check required files with `python3 validate.py`

5. **Gate blocking (E_GATE_BLOCKED)**
   - Text too short: minimum 2 segments required
   - Not enough markers: minimum 5 markers required
   - Add more substantial dialogue content

### Debug Mode

Enable verbose output:
```bash
# Show detailed processing
node cli.js --verbose input.json

# Check marker loading
cat markers_canonical.json | jq '.markers | length'
# Should output: 597
```

## 📈 Performance

**JavaScript Engine:**
- **Marker Loading:** ~600 patterns in <10ms
- **Analysis Speed:** 4-6ms for typical dialogue
- **Dashboard Generation:** <1 second
- **Memory Usage:** ~50MB Node.js process
- **Deterministic:** Same input → same output (content-hash verified)

**Python Orchestrator:**
- **Index Calculation:** <1ms for typical dialogue
- **Drift Analysis:** <1ms for 4-axis computation  
- **Therapeutic Mapping:** <1ms for lens aggregation
- **Heatmap Generation:** <5ms for 500-char buckets
- **Complete Pipeline:** <50ms total processing time
- **Memory Usage:** ~100MB Python process

## 🌐 Language Support

Currently supports **German** with 597 markers. The architecture supports adding other languages:

1. Create marker definitions in `ALL_Marker_5.1/`
2. Use appropriate Unicode regex patterns
3. Rebuild with `build_markers_canonical.py`

## 🤝 Contributing

### Adding New Markers
1. Add new markers to appropriate `ALL_Marker_5.1/` subdirectory
2. Follow YAML format of existing markers
3. Include examples and tags
4. Test with sample dialogues
5. Rebuild with `python3 build_markers_canonical.py`

### Adding New Features
1. Update configuration files in `resources/config/`
2. Extend `enginelib/runtime.py` for new analysis functions
3. Add corresponding tests in `tests/`
4. Update `validate.py` for new requirements
5. Document in README.md

### Adding Therapeutic Frameworks
1. Add mappings to `resources/mappings/lenses_map.yaml`
2. Update scoring formulas in `resources/scorings/scorings.yaml`
3. Test with clinical dialogue samples
4. Validate with domain experts

## 📝 License

MIT License - See LICENSE file for details

## 🔗 Links

- [Documentation](docs/)
  - [Status Report](docs/STATUS.md)
  - [Implementation Details](docs/IMPLEMENTATION_COMPLETE.md)
  - [Architecture Notes](docs/IMPLEMENTATION_STATUS.md)
- [Example Dashboards](dashboard.html) (generated test dashboard)
- [Marker Documentation](ALL_Marker_5.1/EXPLAINABILITY_TEMPLATE.yaml)
- [Configuration Reference](resources/config/)
- [Therapeutic Frameworks](resources/mappings/)

## 👥 Authors

- CARL MarkerEngine Development Team
- Contributors from #WORDthread_lab

## 🙏 Acknowledgments

- Based on linguistic research in German dialogue analysis
- Therapeutic frameworks: CBCT, EFT, SFT, Gottman Method
- Inspired by conversation analysis and psychological assessment
- Built with Node.js, Python, and modern web technologies

## 🔄 Recent Updates

**Version 1.1.0 - Advanced Features:**
- ✅ Python orchestrator with professional analysis tools
- ✅ Therapeutic framework integration (CBCT, EFT, SFT, Gottman)
- ✅ 4-axis drift analysis (tension_calm, approach_avoid, agency_communion, certainty_ambiguity)
- ✅ Advanced indices (trust, de-escalation, conflict, sync)
- ✅ Email context extraction and metadata analysis
- ✅ Heatmap visualization for marker density
- ✅ Balance analysis for speaker dynamics
- ✅ Change point detection for conversation shifts
- ✅ Expert mode with CAND_* marker filtering
- ✅ Comprehensive validation and testing suite

---

*For technical details, see [IMPLEMENTATION_COMPLETE.md](docs/IMPLEMENTATION_COMPLETE.md)*