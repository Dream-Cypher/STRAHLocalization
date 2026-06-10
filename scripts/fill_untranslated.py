"""
Targeted fill for rows that are still untranslated in texts/en/**/*.csv —
either empty, or the Japanese source echoed back verbatim — WITHOUT
re-translating whole files.

For each EN CSV:
  1. Compare to texts/ja/**/*.csv; find rows where translate_files.is_untranslated().
  2. Re-request ONLY those rows (small batches, temp 0.4 to avoid re-echoing),
     up to 2 rounds, accepting only real (non-echo) translations.
  3. Write accepted translations back into the EN CSV's `target`; every other
     cell is left exactly as-is.

Reuses the translate_files machinery (model call, parsing, echo detection) so
behaviour stays in sync with the main pipeline. Run from the project root.

Usage:
  python scripts/fill_untranslated.py --dry-run                       # report only
  python scripts/fill_untranslated.py                                 # fill all
  python scripts/fill_untranslated.py --file scrpt.cpk/ST_USI_096.csv
  python scripts/fill_untranslated.py --temp 0.5
"""
import argparse
import csv
import glob
import os
import re
import sys

import translate_files as tf   # scripts/ is on sys.path when run as a script

ROUNDS, BATCH = 2, 30


def find_untranslated(rel: str):
    """Return (ids_to_fill, {id: prompt_entry}, {id: ja_source})."""
    ja_rows = tf.read_ja_csv(os.path.join(tf.JA_DIR, rel))
    en_path = os.path.join(tf.EN_DIR, rel)
    en = {}
    if os.path.exists(en_path):
        with open(en_path, encoding="utf-8-sig", newline="") as f:
            en = {r["id"].strip(): (r.get("target", "") or "")
                  for r in csv.DictReader(f) if r.get("id", "").strip()}

    entry_by_id: dict[str, str] = {}
    for e in tf.build_entries(ja_rows):
        m = re.match(r"^###ID:\s*([^\s|]+)", e)
        if m:
            entry_by_id[m.group(1)] = e
    src_by_id = {r.get("id", "").strip(): (r.get("target", "") or "").strip() for r in ja_rows}

    todo = [i for i in entry_by_id
            if tf.is_untranslated(en.get(i, "").strip(), src_by_id.get(i, ""))]
    return todo, entry_by_id, src_by_id


def write_back(rel: str, filled: dict[str, str]) -> None:
    en_path = os.path.join(tf.EN_DIR, rel)
    with open(en_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows   = list(reader)
    for row in rows:
        i = row.get("id", "").strip()
        if i in filled:
            row["target"] = filled[i]
    with open(en_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def fill_file(rel: str, model: str, system: str, temperature: float,
              idx: int, total: int) -> tuple[int, int]:
    todo, entry_by_id, src_by_id = find_untranslated(rel)
    if not todo:
        return 0, 0
    print(f"\n[{idx}/{total}] {rel}  —  {len(todo)} untranslated row(s)")

    filled: dict[str, str] = {}
    remaining = list(todo)
    for rnd in range(ROUNDS):
        if not remaining:
            break
        if rnd:
            print(f"  round {rnd + 1}/{ROUNDS}: {len(remaining)} still untranslated")
        next_remaining: list[str] = []
        for s in range(0, len(remaining), BATCH):
            chunk     = remaining[s:s + BATCH]
            batch_txt = "".join(tf.annotate_lines(entry_by_id[i]) for i in chunk)
            disp      = tf.BatchDisplay("f", "?", len(chunk))
            user_msg  = (f"Translating: {rel}\n\n"
                         "IMPORTANT: All translations must be in English only.\n\n"
                         + batch_txt)
            txt, st = tf.ollama_chat(
                model, system, user_msg, display=disp,
                num_predict=len(chunk) * 160 + 800,
                runaway_limit=len(chunk) + max(20, len(chunk) // 2),
                temperature=temperature)
            txt = tf.fix_response(txt)
            disp.finish(st.get("eval_count", 0), st.get("prompt_eval_count", 0),
                        st.get("prompt_eval_duration", 0) / 1e9)
            got = tf.parse_response(txt)
            for k in chunk:
                v = got.get(k)
                if v and not tf.is_untranslated(v, src_by_id.get(k, "")):
                    filled[k] = v
                else:
                    next_remaining.append(k)
        remaining = next_remaining

    if filled:
        write_back(rel, filled)
    still = len(todo) - len(filled)
    note  = f"  ({still} still echoed/empty — re-run to retry)" if still else ""
    print(f"  → filled {len(filled)}/{len(todo)}{note}")
    tf.log(f"FILL {rel}: filled {len(filled)}/{len(todo)}{note}")
    return len(todo), len(filled)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model",   default=tf.DEFAULT_MODEL)
    ap.add_argument("--file",    help="Only this file (relative path)")
    ap.add_argument("--temp",    type=float, default=0.4,
                    help="Sampling temperature (default 0.4 — higher than the main "
                         "pipeline to avoid re-echoing the source)")
    ap.add_argument("--dry-run", action="store_true", help="Report scope, don't call the model")
    args = ap.parse_args()

    files = ([args.file.replace("\\", "/")] if args.file else
             sorted(os.path.relpath(p, tf.JA_DIR).replace(os.sep, "/")
                    for p in glob.glob(os.path.join(tf.JA_DIR, "**", "*.csv"), recursive=True)))

    # Survey what's untranslated up front.
    affected = []
    for rel in files:
        if not os.path.exists(os.path.join(tf.EN_DIR, rel)):
            continue
        todo, _, _ = find_untranslated(rel)
        if todo:
            affected.append((rel, len(todo)))

    if not affected:
        print("Nothing to fill — every translatable row has a real translation.")
        return

    total_rows = sum(n for _, n in affected)
    print(f"Untranslated: {total_rows} row(s) across {len(affected)} file(s)")
    for rel, n in sorted(affected, key=lambda x: -x[1]):
        print(f"  {n:4d}  {rel}")

    if args.dry_run:
        print("\nDry run — re-run without --dry-run to fill.")
        return

    tf.check_server(args.model)
    system = tf.load_system_prompt()
    tf.warmup(args.model, system)
    tf.log("=" * 60)
    tf.log(f"FILL START  model={args.model}  files={len(affected)}  rows={total_rows}  temp={args.temp}")

    tot_found = tot_filled = 0
    for i, (rel, _) in enumerate(sorted(affected, key=lambda x: -x[1]), 1):
        found, filled = fill_file(rel, args.model, system, args.temp, i, len(affected))
        tot_found += found
        tot_filled += filled

    print(f"\nFilled {tot_filled}/{tot_found} row(s) across {len(affected)} file(s).")
    if tot_filled < tot_found:
        print(f"{tot_found - tot_filled} still untranslated (model re-echoed) — re-run to retry.")
    tf.log(f"FILL END  filled {tot_filled}/{tot_found}")


if __name__ == "__main__":
    main()
