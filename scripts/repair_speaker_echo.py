"""
Repairs rows where the model echoed the SPEAKER name and the Japanese source
ahead of the English translation, e.g. (seen in ST_TOK_009):

    target = "Shinpei Ajiro\nやった！\nもう一匹もやっつけたぞ！\nI did it!\nI took out another one too!"
             └ speaker ──┘ └────── Japanese source ──────┘ └────── English ──────┘

The English is already present and correct — only the speaker line and the
Japanese lines need stripping. Recovery: drop line 0 (the speaker) and every
line containing kana/kanji, keep the rest.

A strict guard ensures we only touch real speaker-echo rows: line 0 must be a
short romanized name (not a sentence), the body must contain Japanese lines, and
the recovered remainder must be non-empty clean English. Fully-untranslated rows
(no English present) and ordinary partials don't match, so they're left for the
model fill.

  python scripts/repair_speaker_echo.py --dry-run
  python scripts/repair_speaker_echo.py
  python scripts/repair_speaker_echo.py --file scrpt.cpk/ST_TOK_009.csv
"""
import argparse
import csv
import glob
import os
import re
import sys

EN_DIR = "texts/en"
KK = re.compile(r"[぀-ゟ゠-ヿ一-鿿㐀-䶿]")        # kana / kanji


def recover(target: str) -> str | None:
    """Return the recovered English if `target` is a speaker+JA+English echo,
    else None (leave the row untouched)."""
    lines = target.split("\n")
    if len(lines) < 2:
        return None
    line0 = lines[0]
    if KK.search(line0):                                  # line 0 must be romanized speaker
        return None
    if len(line0.split()) > 4 or line0.rstrip().endswith((".", "!", "?", "…", ",")):
        return None                                       # looks like a sentence, not a name
    body = lines[1:]
    if not any(KK.search(l) for l in body):               # must have Japanese to strip
        return None
    english = [l for l in body if not KK.search(l)]
    rec = "\n".join(english).strip()
    if not rec or KK.search(rec):                         # must recover real English
        return None
    return rec


def process(rel: str, apply: bool, samples: list) -> int:
    path = os.path.join(EN_DIR, rel)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows   = list(reader)
    if "target" not in fields:
        return 0

    changed = 0
    for row in rows:
        old = row.get("target", "") or ""
        rec = recover(old)
        if rec is not None and rec != old:
            if len(samples) < 8:
                samples.append((rel.split("/")[-1], row.get("id", ""), old, rec))
            row["target"] = rec
            changed += 1

    if changed and apply:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = ([args.file.replace("\\", "/")] if args.file else
             sorted(os.path.relpath(p, EN_DIR).replace(os.sep, "/")
                    for p in glob.glob(os.path.join(EN_DIR, "**", "*.csv"), recursive=True)))

    samples: list = []
    total_rows = total_files = 0
    for rel in files:
        if not os.path.exists(os.path.join(EN_DIR, rel)):
            continue
        n = process(rel, apply=not args.dry_run, samples=samples)
        if n:
            total_rows += n
            total_files += 1
            print(f"  {rel}: {n} row(s)")

    print("\nsample recoveries:")
    for f, i, old, rec in samples:
        print(f"  {f}/{i}")
        print(f"    OLD: {old.replace(chr(10), ' / ')[:80]}")
        print(f"    NEW: {rec.replace(chr(10), ' / ')[:80]}")

    verb = "would repair" if args.dry_run else "repaired"
    print(f"\n{verb} {total_rows} row(s) across {total_files} file(s).")


if __name__ == "__main__":
    main()
