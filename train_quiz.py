#!/usr/bin/env python3
"""
Train / improve the quiz answer cache  (quiz_answers.json)
=========================================================
The bot already learns automatically while it runs. This script makes the
cache stronger between runs:

* Re-asks Gemini for every entry whose confidence is low, has no answer, or
  has a black-listed wrong option.
* Uses self-consistency: asks N times with slight temperature and takes the
  majority vote (more accurate than one shot).
* Stores the answer TEXT (survives option shuffling) and re-keys every entry
  by the question text.
* Never touches the "wrong" blacklist learned from the app.

Usage
-----
    .venv2\\Scripts\\python.exe train_quiz.py                 # train weak entries
    .venv2\\Scripts\\python.exe train_quiz.py --all           # re-check everything
    .venv2\\Scripts\\python.exe train_quiz.py --samples 5 --min-conf 0.95
    .venv2\\Scripts\\python.exe train_quiz.py --review        # only show stats
    .venv2\\Scripts\\python.exe train_quiz.py --limit 20      # batch size
"""

import argparse
import collections
import json
import os
import sys
import time
import urllib.error

from king_quiz_bot import (
    CACHE_FILE, CONFIG_FILE, ask_gemini, build_prompt, gemini_call,
    load_json, model_list, norm, normalize_cache, parse_answer, qkey,
    save_json,
)


def entry_options(entry):
    opts = entry.get("options") or {}
    out = []
    for letter in sorted(opts, key=lambda x: str(x)):
        text = (opts.get(letter) or "").strip()
        if text:
            out.append({"letter": str(letter).upper()[:1], "text": text})
    return out


def needs_training(entry, min_conf, retrain_all=False):
    if retrain_all:
        return True
    if not entry.get("answer_text"):
        return True
    if float(entry.get("confidence") or 0) < min_conf:
        return True
    if entry.get("wrong"):
        # the saved answer is one of the black-listed ones -> unusable
        if str(entry.get("answer", "")).upper()[:1] in [
                str(w).upper() for w in entry["wrong"]]:
            return True
    return False


def vote_answer(entry, cfg, samples=3):
    options = entry_options(entry)
    if len(options) < 2:
        return None, 0.0, "no-options"

    prompt = build_prompt(entry["question"], options)
    votes = collections.Counter()
    confs = collections.defaultdict(list)
    models = model_list(cfg)

    for i in range(max(1, samples)):
        raw = None
        for model in models:
            try:
                raw = gemini_call(prompt, cfg, model,
                                  temperature=0.30 if samples > 1 else 0.0)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(1.2)
                    continue
                break
            except Exception:
                break
        if not raw:
            continue
        ans, conf = parse_answer(raw, options)
        if ans:
            votes[ans] += 1
            confs[ans].append(conf)
        time.sleep(0.35)

    if not votes:
        return None, 0.0, "gemini-failed"

    best, count = votes.most_common(1)[0]
    conf = (sum(confs[best]) / len(confs[best])) if confs[best] else 0.7
    # agreement boosts confidence, disagreement lowers it
    agreement = count / max(1, samples)
    final_conf = round(min(0.99, max(0.05, conf * (0.6 + 0.4 * agreement))), 3)
    return best, final_conf, f"{count}/{samples} votes"


def review(cache):
    total = len(cache)
    no_answer = sum(1 for e in cache.values() if not e.get("answer_text"))
    low = sum(1 for e in cache.values()
              if float(e.get("confidence") or 0) < 0.85)
    wrong = sum(1 for e in cache.values() if e.get("wrong"))
    correct = sum(1 for e in cache.values() if e.get("correct"))
    print(f"entries       : {total}")
    print(f"no answer     : {no_answer}")
    print(f"low confidence: {low}")
    print(f"has wrong list: {wrong}")
    print(f"confirmed ok  : {correct}")
    if total:
        langs = collections.Counter("hi" if any(
            "\u0900" <= ch <= "\u097f" for ch in e.get("question", "")) else "en"
            for e in cache.values())
        print(f"language mix  : {dict(langs)}")
    print("\nTop 10 lowest confidence:")
    for e in sorted(cache.values(),
                    key=lambda x: float(x.get("confidence") or 0))[:10]:
        print(f"  [{float(e.get('confidence') or 0):.2f}] "
              f"{e.get('answer_text') or e.get('answer') or '?'}  "
              f"<- {e.get('question', '')[:90]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="re-check every entry")
    ap.add_argument("--min-conf", type=float, default=0.85)
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--review", action="store_true", help="show stats only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--serial", default="", help="unused, kept for symmetry")
    args = ap.parse_args()

    cfg = load_json(CONFIG_FILE, {})
    raw_cache = load_json(CACHE_FILE, {})
    cache = normalize_cache(raw_cache)

    print("=" * 60)
    print("QUIZ TRAINER")
    print("=" * 60)
    review(cache)

    if args.review:
        return

    targets = [e for e in cache.values()
               if needs_training(e, args.min_conf, retrain_all=args.all)]
    targets.sort(key=lambda e: float(e.get("confidence") or 0))
    if args.limit:
        targets = targets[:args.limit]

    if not targets:
        print("\nNothing to train. Use --all to re-check every answer.")
        return

    print(f"\nTraining {len(targets)} entries "
          f"({args.samples} samples each)...\n")

    changed = 0
    failed = 0
    for i, entry in enumerate(targets, 1):
        q = entry.get("question", "")
        old = entry.get("answer_text") or entry.get("answer") or "?"
        ans, conf, note = vote_answer(entry, cfg, samples=args.samples)
        if not ans:
            failed += 1
            print(f"[{i}/{len(targets)}] SKIP ({note}): {q[:70]}")
            continue

        options = {o["letter"]: o["text"] for o in entry_options(entry)}
        answer_text = options.get(ans, "")
        print(f"[{i}/{len(targets)}] {old!r} -> {ans}. {answer_text!r} "
              f"({conf:.2f}, {note})")

        if not args.dry_run:
            entry["answer"] = ans
            entry["answer_text"] = answer_text
            entry["confidence"] = conf
            entry["trained_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            entry["trained_by"] = f"train_quiz/{args.samples}"
            # keep learned blacklist, drop a stale confirmed flag
            if entry.get("correct") and conf < 0.8:
                entry.pop("correct", None)
            cache[qkey(q)] = entry
            changed += 1

    if not args.dry_run and changed:
        save_json(CACHE_FILE, cache)
    print(f"\nDone. updated={changed} failed={failed} "
          f"total={len(cache)}")
    if not args.dry_run:
        review(cache)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
