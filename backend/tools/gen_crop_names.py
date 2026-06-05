#!/usr/bin/env python
"""Generate regional crop-name translations from Wikidata (Tier-1, "trusted").

Reads the live commodity list (the same ~380 the UI shows), resolves each English
commodity to a Wikidata item, and pulls that item's labels in the app's 11
non-English languages. Writes a per-language PREVIEW under ./out and a coverage
report. With --merge it folds the new keys into the locale JSONs.

Design / honesty notes:
  - Key format mirrors the frontend helper (src/i18n/cropName.js): the locale key
    is `crop.name.` + the English commodity lowercased with non-alphanumerics
    stripped, so e.g. "Bengal Gram (Gram)(Whole)" -> crop.name.bengalgramgramwhole.
    No frontend change is needed; missing keys fall back to English.
  - --merge only ADDS keys absent from a locale file, so the 36 hand-curated
    canonical crop names are never overwritten.
  - Matching is heuristic (English-label search, with a light agri-description
    filter to avoid e.g. the drink "Absinthe"). Coverage is uneven. Treat all
    output as DRAFT pending native-speaker review; `conf` in the cache flags how
    confident the Wikidata match was ("agri" = description looked agricultural,
    "first" = took the top hit anyway).

Run from backend/ with the venv, while the backend is up on :8000:
    venv/Scripts/python.exe tools/gen_crop_names.py            # dry run + report
    venv/Scripts/python.exe tools/gen_crop_names.py --merge    # fold into locales
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Wikidata language codes line up 1:1 with our locale codes (or = Odia, as = Assamese).
LANGS = ["hi", "pa", "mr", "gu", "bn", "te", "ta", "kn", "ml", "or", "as"]

HERE = Path(__file__).resolve().parent
LOCALES_DIR = HERE.parents[1] / "frontend" / "src" / "i18n" / "locales"
CACHE = HERE / "crop_wikidata_cache.json"
OUT_DIR = HERE / "out"

API = "https://www.wikidata.org/w/api.php"
# Wikimedia policy requires a descriptive User-Agent.
UA = ("CropAnalyser-i18n/1.0 "
      "(https://github.com/Sumit-bit-0/CropAnalyser; agri crop-name i18n)")

AGRI_HINT = re.compile(
    r"\b(plant|crop|vegetable|fruit|cereal|grain|legume|pulse|spice|herb|"
    r"flower|millet|seed|bean|lentil|pea|nut|tree|species|cultivar|food|"
    r"oilseed|tuber|root)\b", re.I)

# Descriptions that mean the match is NOT the produce itself -> drop the labels
# even if it slipped past the agri filter (e.g. "Cauliflower mosaic virus",
# "Asteraceae" the family, a person named like a commodity).
REJECT = re.compile(
    r"\b(virus|viroid|disease|pathogen|bacterium|fungus|family|genus|order|"
    r"subfamily|surname|given name|given-name|businessman|politician|actor|"
    r"actress|singer|musician|band|film|movie|song|album|village|town|city|"
    r"river|district|municipality|company|brand|software|video game|"
    r"manufacturer|chemical compound)\b", re.I)

# Qualifier words that don't change the base crop identity; stripped so variant
# rows ("Banana - Green", "Onion Green") resolve to the same produce.
QUALIFIERS = {"green", "dry", "dried", "raw", "ripe", "whole", "fresh", "local",
              "hybrid", "big", "small", "medium", "large", "new", "old", "red",
              "white", "black", "yellow", "tender"}


def norm(s: str) -> str:
    """Must match cropName.js normCrop exactly."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean(name: str) -> str:
    """English search term: drop parentheticals, slash- and dash-variants, and
    leading/trailing qualifier words for a better Wikidata hit."""
    n = re.sub(r"\(.*?\)", "", name)
    n = n.split("/")[0]
    n = n.split(" - ")[0]
    n = re.sub(r"\s+", " ", n).strip()
    toks = n.split()
    while toks and toks[0].lower() in QUALIFIERS:
        toks.pop(0)
    while toks and toks[-1].lower() in QUALIFIERS:
        toks.pop()
    return " ".join(toks) if toks else n


def _get(params: dict) -> dict:
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def search_best(term: str):
    """Return {qid, desc, match, conf} for the best agri-ish hit, or None."""
    try:
        d = _get({"action": "wbsearchentities", "search": term,
                  "language": "en", "type": "item", "limit": 7})
    except Exception as e:  # network / API hiccup
        print(f"  ! search failed for {term!r}: {e}", file=sys.stderr)
        return None
    hits = d.get("search", [])
    if not hits:
        return None
    for h in hits:
        desc = h.get("description", "") or ""
        if AGRI_HINT.search(desc):
            return {"qid": h["id"], "desc": desc, "match": h.get("label", ""), "conf": "agri"}
    h = hits[0]
    return {"qid": h["id"], "desc": h.get("description", "") or "",
            "match": h.get("label", ""), "conf": "first"}


def fetch_labels(qids: list) -> dict:
    """Batch up to 50 QIDs per call -> {qid: {lang: label}}."""
    out = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        try:
            d = _get({"action": "wbgetentities", "ids": "|".join(batch),
                      "props": "labels", "languages": "|".join(LANGS)})
        except Exception as e:
            print(f"  ! getentities failed: {e}", file=sys.stderr)
            continue
        for qid, ent in d.get("entities", {}).items():
            labels = ent.get("labels", {})
            out[qid] = {l: labels[l]["value"] for l in LANGS if l in labels}
        time.sleep(0.2)
    return out


def load_commodities(api_base: str) -> list:
    url = api_base.rstrip("/") + "/api/mandi/commodities"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return [x["display_name"] for x in data]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://localhost:8000", help="backend base URL")
    ap.add_argument("--merge", action="store_true", help="fold new keys into locale JSONs")
    ap.add_argument("--refresh", action="store_true", help="ignore cache, re-query Wikidata")
    args = ap.parse_args()

    commodities = load_commodities(args.api)
    print(f"commodities: {len(commodities)}")

    cache = {}
    if CACHE.exists() and not args.refresh:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    # 1) resolve QIDs (cached across runs). Retry previous misses too — an
    # improved cleaner may now find them — but keep resolved hits cached.
    todo = [c for c in commodities
            if c not in cache or (cache[c].get("qid") is None)]
    print(f"to resolve: {len(todo)} (cached hits: {len(commodities) - len(todo)})")
    resolved_now = {}
    for i, c in enumerate(todo, 1):
        resolved_now[c] = search_best(clean(c))
        if i % 25 == 0:
            print(f"  searched {i}/{len(todo)}")
        time.sleep(0.15)

    # 2) fetch labels for the newly found QIDs
    new_qids = sorted({r["qid"] for r in resolved_now.values() if r})
    labels_by_qid = fetch_labels(new_qids) if new_qids else {}

    # 3) update cache
    for c in todo:
        r = resolved_now.get(c)
        if r:
            cache[c] = {"qid": r["qid"], "conf": r["conf"], "match": r["match"],
                        "desc": r["desc"], "labels": labels_by_qid.get(r["qid"], {})}
        else:
            cache[c] = {"qid": None, "conf": None, "match": None, "desc": None, "labels": {}}
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4) build per-language key maps, dropping matches whose description says the
    # item isn't the produce (virus / family / person / place ...).
    per_lang = {l: {} for l in LANGS}
    rejected = 0
    for c in commodities:
        entry = cache.get(c) or {}
        if entry.get("desc") and REJECT.search(entry["desc"]):
            rejected += 1
            continue
        key = "crop.name." + norm(c)
        for l, val in (entry.get("labels") or {}).items():
            per_lang[l][key] = val

    # coverage report
    resolved = sum(1 for c in commodities if (cache.get(c) or {}).get("qid"))
    agri = sum(1 for c in commodities if (cache.get(c) or {}).get("conf") == "agri")
    print("\n=== coverage ===")
    print(f"  resolved to a Wikidata item : {resolved}/{len(commodities)} "
          f"({agri} high-confidence agri, {resolved - agri} top-hit fallback)")
    print(f"  dropped by REJECT filter    : {rejected}")
    for l in LANGS:
        print(f"  {l}: {len(per_lang[l])} labels")

    # 5) previews always; merge only on request
    OUT_DIR.mkdir(exist_ok=True)
    for l in LANGS:
        (OUT_DIR / f"crop_names.{l}.json").write_text(
            json.dumps(per_lang[l], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\npreviews -> {OUT_DIR}")

    if args.merge:
        added_total = 0
        for l in LANGS:
            added_total += merge_textual(LOCALES_DIR / f"{l}.json", per_lang[l], l)
        print(f"merged {added_total} keys into locale files "
              f"(curated keys left untouched)")
    else:
        print("dry run (no locale files changed). Re-run with --merge to fold in.")


def merge_textual(path: Path, newkeys: dict, lang: str) -> int:
    """Append keys not already present, preserving the file's existing formatting
    (a plain json.dump would reflow the hand-curated catalogs). Returns count added."""
    data = json.loads(path.read_text(encoding="utf-8"))   # also validates JSON
    add = {k: v for k, v in newkeys.items() if k not in data}
    if not add:
        print(f"  {lang}: +0 keys")
        return 0
    text = path.read_text(encoding="utf-8").rstrip()
    if not text.endswith("}"):
        raise ValueError(f"{path} does not end with '}}'")
    head = text[:-1].rstrip()
    if not head.endswith(","):
        head += ","
    items = list(add.items())
    lines = []
    for i, (k, v) in enumerate(items):
        body = json.dumps({k: v}, ensure_ascii=False)[1:-1]   # "key": "value"
        lines.append("  " + body + ("," if i < len(items) - 1 else ""))
    path.write_text(head + "\n" + "\n".join(lines) + "\n}\n", encoding="utf-8")
    print(f"  {lang}: +{len(add)} keys")
    return len(add)


if __name__ == "__main__":
    main()
