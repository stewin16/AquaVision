"""
fish_name_mapper.py
===================
Queries the FishBase API to map scientific fish names → Indian common names.

Run this ONCE to generate:
  1. fish_names_india.json  → Ship in Android app assets/ for offline lookup
  2. labels_indian.txt      → Use as labels.txt when retraining YOLO

Usage:
  1. Put your scientific names in 'species_scientific.txt' (one per line)
  2. pip install requests
  3. python fish_name_mapper.py
"""

import requests
import json
import time
import os
import sys

FISHBASE_API = "https://fishbase.ropensci.org"
CACHE_FILE = "fishbase_cache.json"

# Load cache to avoid re-querying
cache = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    print(f"Loaded {len(cache)} cached entries from {CACHE_FILE}")


def save_cache():
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_spec_code(genus, species):
    """Get the FishBase SpecCode for a scientific name."""
    cache_key = f"speccode:{genus}:{species}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        resp = requests.get(
            f"{FISHBASE_API}/species",
            params={"Genus": genus, "Species": species},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                code = data[0].get("SpecCode")
                cache[cache_key] = code
                save_cache()
                return code
    except Exception as e:
        print(f"    ⚠ API error for {genus} {species}: {e}")
    
    cache[cache_key] = None
    save_cache()
    return None


def get_indian_common_names(spec_code):
    """Get common names for India from FishBase."""
    cache_key = f"names:{spec_code}"
    if cache_key in cache:
        return cache[cache_key]

    names = {
        "english": None, "hindi": None, "bengali": None,
        "tamil": None, "telugu": None, "marathi": None,
        "malayalam": None, "kannada": None, "gujarati": None,
        "konkani": None, "oriya": None
    }

    try:
        offset = 0
        while True:
            resp = requests.get(
                f"{FISHBASE_API}/comnames",
                params={"SpecCode": spec_code, "limit": 200, "offset": offset},
                timeout=15
            )
            if resp.status_code != 200:
                break

            data = resp.json().get("data", [])
            if not data:
                break

            for entry in data:
                language = (entry.get("Language") or "").lower().strip()
                name = (entry.get("ComName") or "").strip()
                if not name:
                    continue

                # Map language field to our keys
                lang_map = {
                    "hindi": "hindi", "bengali": "bengali", "bangla": "bengali",
                    "tamil": "tamil", "telugu": "telugu", "marathi": "marathi",
                    "malayalam": "malayalam", "kannada": "kannada",
                    "gujarati": "gujarati", "konkani": "konkani",
                    "oriya": "oriya", "odia": "oriya"
                }

                for key, field in lang_map.items():
                    if key in language and not names[field]:
                        names[field] = name

                if "english" in language and not names["english"]:
                    names["english"] = name

            if len(data) < 200:
                break
            offset += 200
            time.sleep(0.3)

    except Exception as e:
        print(f"    ⚠ Error fetching names for SpecCode {spec_code}: {e}")

    # Clean out None values for caching
    result = {k: v for k, v in names.items() if v}
    cache[cache_key] = result
    save_cache()
    return result


def pick_display_name(names, sci_name):
    """Pick the best display name for Indian fishermen."""
    # Priority: Hindi → English → Bengali → Tamil → Telugu → Marathi → original
    priority = ["hindi", "english", "bengali", "tamil", "telugu", "marathi",
                "malayalam", "kannada", "gujarati"]
    for lang in priority:
        if names.get(lang):
            return names[lang]
    return sci_name


def process_species_list(input_file, output_json, output_labels):
    """
    Read scientific names, query FishBase, output:
      1. JSON mapping file (for the Android app)
      2. New labels.txt (for retraining)
    """
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        print(f"   Create '{input_file}' with one scientific name per line.")
        print(f"   Example:")
        print(f"     Labeo rohita")
        print(f"     Catla catla")
        print(f"     Oreochromis niloticus")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        species_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    print(f"\n{'='*60}")
    print(f"  FishBase Indian Name Mapper")
    print(f"  Processing {len(species_list)} species...")
    print(f"{'='*60}\n")

    mapping = {}
    new_labels = []
    stats = {"found": 0, "not_found": 0, "has_hindi": 0}

    for i, sci_name in enumerate(species_list):
        parts = sci_name.split()

        # If it's already a common name (1 word or known), keep it
        if len(parts) < 2:
            print(f"  [{i+1:3d}/{len(species_list)}] '{sci_name}' — kept as-is (not a binomial name)")
            mapping[sci_name] = {"display_name": sci_name, "names": {}}
            new_labels.append(sci_name)
            continue

        genus, species = parts[0], parts[1]
        print(f"  [{i+1:3d}/{len(species_list)}] {genus} {species}", end="")

        spec_code = get_spec_code(genus, species)
        if not spec_code:
            print(f" — ⚠ Not found in FishBase")
            mapping[sci_name] = {"display_name": sci_name, "names": {}}
            new_labels.append(sci_name)
            stats["not_found"] += 1
            time.sleep(0.3)
            continue

        names = get_indian_common_names(spec_code)
        display_name = pick_display_name(names, sci_name)

        mapping[sci_name] = {
            "display_name": display_name,
            "names": names
        }
        new_labels.append(display_name)
        stats["found"] += 1
        if names.get("hindi"):
            stats["has_hindi"] += 1

        langs_found = ", ".join(f"{k}={v}" for k, v in names.items() if v)
        print(f" → {display_name}  [{langs_found}]")
        time.sleep(0.5)  # Rate limiting

    # Save JSON mapping
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    # Save new labels.txt
    with open(output_labels, 'w', encoding='utf-8') as f:
        for label in new_labels:
            f.write(label + '\n')

    # Print summary
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total species:       {len(species_list)}")
    print(f"  Found in FishBase:   {stats['found']}")
    print(f"  Not found:           {stats['not_found']}")
    print(f"  With Hindi name:     {stats['has_hindi']}")
    print(f"")
    print(f"  ✅ Saved: {output_json}")
    print(f"  ✅ Saved: {output_labels}")
    print(f"{'='*60}")


if __name__ == "__main__":
    process_species_list(
        input_file="species_scientific.txt",
        output_json="fish_names_india.json",
        output_labels="labels_indian.txt"
    )
