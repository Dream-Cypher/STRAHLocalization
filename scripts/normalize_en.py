"""
One-off text normalization pass over texts/en/**/*.csv `target` columns.

Brings the chunk-workflow files (applied via apply_translations.py, which
never ran fix_response) in line with the same style conventions translate_files
already enforces:

  ……  (or any run of …)  → …      single ellipsis
  ...  (3+ ASCII dots)    → …      ASCII dot run → ellipsis
  〜 / ～ (wave dash/fullwidth tilde) → ~
  【 】                   → [ ]    lenticular → square brackets

Idempotent: re-running changes nothing. Only the `target` column is touched;
`source`, `id`, and `developer_comments` are copied through unchanged.

Usage:
  python scripts/normalize_en.py --dry-run        # report what would change
  python scripts/normalize_en.py                  # apply in place
  python scripts/normalize_en.py --file scrpt.cpk/ST_HDR_001.csv
"""
import argparse
import csv
import glob
import os
import re
import sys

EN_DIR = "texts/en"

_ELLIPSIS_RUN = re.compile(r"…{2,}")
_ASCII_DOTS   = re.compile(r"\.{3,}")
_PERIOD_AFTER_ELLIPSIS = re.compile(r"…\.")
# Skip still-untranslated targets (real kana/kanji) so we don't corrupt pending
# Japanese. Punctuation alone (。！？ etc.) is NOT a skip signal — those are
# exactly what we want to normalize on otherwise-English lines.
_KANA_KANJI = re.compile(r"[぀-ゟ゠-ヿ一-鿿㐀-䶿]")

# Fullwidth / Japanese punctuation -> ASCII. Japanese quotes 「」『』 are left
# alone (no clean English equivalent without guessing quote style).
_PUNCT = str.maketrans({
    "。": ".", "、": ",", "，": ",", "！": "!", "？": "?",
    "：": ":", "；": ";", "（": "(", "）": ")", "　": " ",
})


def normalize(text: str) -> str:
    text = text.translate(_PUNCT)
    text = _ELLIPSIS_RUN.sub("…", text)             # …… -> …
    text = _ASCII_DOTS.sub("…", text)               # ... -> …
    text = _PERIOD_AFTER_ELLIPSIS.sub("…", text)    # ….  -> …  (e.g. from 。 after …)
    text = text.replace("〜", "~").replace("～", "~")
    text = text.replace("【", "[").replace("】", "]")
    return text


def rel_paths() -> list[str]:
    return sorted(
        os.path.relpath(p, EN_DIR).replace("\\", "/")
        for p in glob.glob(os.path.join(EN_DIR, "**", "*.csv"), recursive=True)
    )


def process(rel: str, apply: bool) -> int:
    path = os.path.join(EN_DIR, rel)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader     = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows       = list(reader)

    if "target" not in fieldnames:
        return 0

    changed = 0
    for row in rows:
        old = row.get("target", "")
        if _KANA_KANJI.search(old):   # still Japanese (real text) — leave for translation
            continue
        new = normalize(old)
        if new != old:
            row["target"] = new
            changed += 1

    if changed and apply:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return changed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--file",    help="Normalize only this file (relative path)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report changes without writing")
    args = parser.parse_args()

    files = [args.file.replace("\\", "/")] if args.file else rel_paths()

    total_rows  = 0
    total_files = 0
    for rel in files:
        if not os.path.exists(os.path.join(EN_DIR, rel)):
            print(f"  missing: {rel}")
            continue
        n = process(rel, apply=not args.dry_run)
        if n:
            total_rows  += n
            total_files += 1
            print(f"  {rel}: {n} row(s)")

    verb = "would change" if args.dry_run else "changed"
    print(f"\n{verb} {total_rows} row(s) across {total_files} file(s).")
    if args.dry_run and total_rows:
        print("Re-run without --dry-run to apply.")


if __name__ == "__main__":
    main()
