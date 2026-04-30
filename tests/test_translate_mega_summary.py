import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_engine.translate_en_to_de import translate_en_to_de

INPUT_MEGA = ROOT / "data" / "output" / "mega_summary.json"
OUTPUT_MEGA_DE = ROOT / "data" / "output" / "mega_summary_de.json"


def test_translate_mega_summary_simple():
    with open(INPUT_MEGA, "r", encoding="utf-8") as f:
        data = json.load(f)

    en_summary = data.get("mega_summary", "").strip()
    if not en_summary:
        raise ValueError("Mega summary is empty")

    de_summary = translate_en_to_de(en_summary)

    out = {
        "request_id": data.get("request_id"),
        "mega_summary_en": en_summary,
        "mega_summary_de": de_summary,
    }

    OUTPUT_MEGA_DE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MEGA_DE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("Mega summary translated (simple validation)")
    print(f"Output written to: {OUTPUT_MEGA_DE}")


if __name__ == "__main__":
    test_translate_mega_summary_simple()
