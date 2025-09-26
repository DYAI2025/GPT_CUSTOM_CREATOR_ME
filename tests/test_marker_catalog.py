import json
import tempfile
import unittest
from pathlib import Path

from enginelib.marker_catalog import MarkerCatalog

SAMPLE_YAML = """
- id: ATO_ACK
  type: ato
  regex: "\\bdanke\\b"
  tags: [thanks]
- name: SEM_VALIDATION
  type: sem
  pattern: ["ich verstehe"]
  composed_of: [ATO_ACK]
"""

FOCUS_YAML = """
profiles:
  empathy:
    description: Mehr Empathie
    marker_weights:
      SEM_VALIDATION: 1.5
    tag_weights:
      empathy: 1.2
    type_weights:
      sem: 1.1
"""

MODELS_YAML = """
models:
  default:
    description: Standardprofil
    system_prompt: Sei freundlich
    focus_profile: empathy
    default_mode: dialog
    temperature: 0.3
"""


class MarkerCatalogTest(unittest.TestCase):
    def test_catalog_builds_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "markers.yaml"
            path.write_text(SAMPLE_YAML, encoding="utf-8")

            catalog = MarkerCatalog()
            catalog.load_markers(path)
            payload = catalog.to_json(version="test", spec="spec")

            self.assertEqual(payload["version"], "test")
            self.assertEqual(payload["ld_spec"], "spec")
            self.assertEqual(len(payload["markers"]), 2)
            ids = {m["id"] for m in payload["markers"]}
            self.assertIn("ATO_ACK", ids)
            self.assertIn("SEM_VALIDATION", ids)
            for marker in payload["markers"]:
                self.assertIn(marker["type"], {"ATO", "SEM"})

    def test_focus_and_model_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker_path = Path(tmp) / "markers.yaml"
            marker_path.write_text(SAMPLE_YAML, encoding="utf-8")
            focus_path = Path(tmp) / "focus.yaml"
            focus_path.write_text(FOCUS_YAML, encoding="utf-8")
            model_path = Path(tmp) / "models.yaml"
            model_path.write_text(MODELS_YAML, encoding="utf-8")

            catalog = MarkerCatalog()
            catalog.load_markers(marker_path)
            catalog.load_focus_schema(focus_path)
            catalog.load_model_schema(model_path)
            payload = catalog.to_json()

            self.assertEqual(len(payload["focus_profiles"]), 1)
            focus = payload["focus_profiles"][0]
            self.assertEqual(focus["name"], "empathy")
            self.assertAlmostEqual(focus["marker_weights"]["SEM_VALIDATION"], 1.5)
            self.assertAlmostEqual(focus["type_weights"]["SEM"], 1.1)

            self.assertEqual(len(payload["model_profiles"]), 1)
            model = payload["model_profiles"][0]
            self.assertEqual(model["name"], "default")
            self.assertEqual(model["focus_profile"], "empathy")
            self.assertEqual(model["extra"], {"temperature": 0.3})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
