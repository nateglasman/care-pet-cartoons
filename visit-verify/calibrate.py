"""Measure how lenient/strict the verifier is, using the shelter's own photos.

For each pet with >= 2 photos:
  positive: hold one non-cover photo out of the reference set and submit it as the candidate
            (should be MATCH, since it IS the same animal)
  negative: submit a photo of the most similar OTHER pet of the same species
            (should be NO_MATCH / UNCERTAIN, never MATCH)

Run:  python calibrate.py --dogs 6 --cats 6
Each check is one model call with ~8 images (roughly 5 cents). Results go to calibration.json.
"""
from __future__ import annotations

import argparse
import json
import sys

from verify import load_pets, pick_decoys, reference_image, verify_visit


def run(species: str, n: int, pets: list[dict]) -> list[dict]:
    rows = []
    cands = [p for p in pets if p["species"] == species and len(p["photo_urls"]) >= 2][:n]
    for pet in cands:
        held_out = pet["photo_urls"][-1]  # a non-cover photo, excluded from references
        decoy = pick_decoys(pets, pet, 1)[0]
        for kind, url, note in (("positive", held_out, pet["name"]), ("negative", decoy["cover_photo_url"], decoy["name"])):
            try:
                r = verify_visit(pet["id"], reference_image(url), pets=pets, expect_new_photo=False,
                                 exclude_reference_urls={held_out})
                ok = (r.decision == "match") if kind == "positive" else (r.decision != "match")
                rows.append({"pet": pet["name"], "species": species, "kind": kind, "candidate": note,
                             "decision": r.decision, "confidence": r.confidence, "lookalike_risk": r.model_output["lookalike_risk"],
                             "ok": ok, "reason": r.reason, "seconds": r.seconds})
                print(f"{'OK ' if ok else 'BAD'} {species} {kind:8} {pet['name']:<18} cand={note:<18} -> {r.decision:9} {r.confidence:.2f} ({r.model_output['lookalike_risk']} lookalike) {r.seconds}s", file=sys.stderr)
            except Exception as e:
                print(f"ERR {species} {kind} {pet['name']}: {e}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dogs", type=int, default=6)
    ap.add_argument("--cats", type=int, default=6)
    args = ap.parse_args()
    pets = load_pets()
    rows = run("Dog", args.dogs, pets) + run("Cat", args.cats, pets)
    json.dump(rows, open("calibration.json", "w"), indent=1)
    print("\n| Species | Case | Correct | Confidence range |\n|---|---|---|---|")
    for sp in ("Dog", "Cat"):
        for kind in ("positive", "negative"):
            sub = [r for r in rows if r["species"] == sp and r["kind"] == kind]
            if sub:
                lo, hi = min(r["confidence"] for r in sub), max(r["confidence"] for r in sub)
                print(f"| {sp} | {kind} ({'same animal, new photo' if kind == 'positive' else 'closest lookalike'}) | {sum(r['ok'] for r in sub)}/{len(sub)} | {lo:.2f} to {hi:.2f} |")
    print("\n| Pet | Case | Candidate | Decision | Confidence | Lookalike risk |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['pet']} | {r['kind']} | {r['candidate']} | {r['decision']} | {r['confidence']:.2f} | {r['lookalike_risk']} |")
