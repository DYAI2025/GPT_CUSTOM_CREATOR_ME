# CARL MarkerEngine

## Project Overview

The CARL MarkerEngine is a command-line tool for analyzing text to identify linguistic and emotional markers. It operates on a deterministic pipeline, taking a JSON object with text or dialogue segments as input and producing a detailed JSON analysis as output.

The engine identifies several types of markers:
*   **ATO (Atomic):** Basic, regex-detected markers like acknowledgements, questions, or apologies.
*   **SEM (Semantic):** Higher-level markers derived from combinations of ATOs, representing concepts like validation or repair.
*   **CLU (Cluster):** Markers indicating alignment or other complex interactions.
*   **MEMA (Memory/Meta):** Markers related to empathy and memory.
*   **DETECT:** General-purpose detectors for signals like excessive capitalization.

Based on the detected and promoted markers, the engine calculates four key indices:
*   **Trust**
*   **De-escalation**
*   **Conflict**
*   **Sync**

The entire process is designed to be deterministic and reproducible, with content-based hashing for the engine, its configuration, and the input text.

### Technologies

*   **Language:** JavaScript (ES Modules)
*   **Environment:** Node.js
*   **Validation:** AJV (for JSON Schema validation)

## Building and Running

The project is self-contained and does not have external npm dependencies listed in a `package.json`. It can be run directly using Node.js.

### Running the Engine

The engine is executed via the `cli.js` script. It expects a JSON input from either a file or standard input.

**Command:**

```bash
node cli.js [--mode <mode>] [input_file.json]
```

*   `--mode <mode>`: Specifies the analysis mode. The default is `dialog`. Other modes might include `single`, `coach`, `learn`, or `free`, which adjust the weighting and calibration.
*   `[input_file.json]`: The path to a JSON file containing the input text. If omitted, the script reads from `stdin`.

### Input Format

The input must be a JSON object conforming to `schema.input.json`. It can contain either a single `text` field or an array of `segments`.

**Example (from stdin):**

```bash
echo '{ "text": "A: Das ist eine gute Idee.\\nB: Danke, das freut mich." }' | node cli.js
```

**Example (from file):**

```bash
node cli.js my_input.json
```

Where `my_input.json` contains:
```json
{
  "segments": [
    { "who": "A", "text": "Das ist eine gute Idee." },
    { "who": "B", "text": "Danke, das freut mich." }
  ]
}
```

## Development Conventions

*   **Determinism:** The core principle of the engine is to be deterministic. Any changes to the engine logic (`engine.js`), schemas, or canonical marker data (`markers_canonical.json`) will result in a different `engine_hash`.
*   **Single Source of Truth:** The analysis logic is driven by a set of configuration files in the root directory:
    *   `markers_canonical.json`: The master list of all markers, their regexes, and promotion/annotation rules.
    *   `weights.json`: The weighting and calibration parameters for calculating the final indices.
    *   `modes.json`: Defines adjustments to weights and calibration for different analysis modes.
    *   `promotion_mapping.json`: Additional rules for promoting markers.
*   **Schema Validation:** All inputs and outputs are validated against JSON Schemas (`schema.input.json`, `schema.output.json`, etc.).
*   **Unicode Normalization:** All text is normalized to NFC (Normalization Form C).
