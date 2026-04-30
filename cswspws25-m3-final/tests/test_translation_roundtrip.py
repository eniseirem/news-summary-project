import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from llm_engine.multilingual import translate_text_to_en
from llm_engine.translate_en_to_de import translate_en_to_de


INPUT_FILE = ROOT / "data" / "input" / "test_articles_translation.json"
OUTPUT_FILE = ROOT / "data" / "output" / "translation_roundtrip_results.json"


def test_translation_roundtrip_with_real_articles():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        articles = json.load(f)

    results = []

    for article in articles[:5]:  # bewusst klein halten
        original_de = {
            "title": article.get("title", ""),
            "body": article.get("body", "")
        }

        translated_en = {
            "title": translate_text_to_en(original_de["title"], src_lang="de"),
            "body": translate_text_to_en(original_de["body"], src_lang="de")
        }

        back_translated_de = {
            "title": translate_en_to_de(translated_en["title"]),
            "body": translate_en_to_de(translated_en["body"])
        }

        results.append(
            {
                "id": article.get("id"),
                "original_language": "de",
                "original_de": original_de,
                "translated_en": translated_en,
                "back_translated_de": back_translated_de
            }
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(results)} translated articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    test_translation_roundtrip_with_real_articles()
