"""
Repairs texts/en/**/*.csv `target` cells that were contaminated by stray
###FILE: / ###ID: / ### marker lines the model echoed from the prompt and that
parse_response glued onto the end of translations.

Removes any line within a target cell that begins (after optional whitespace)
with '###'. Legitimate translations never start a line with '###', so this is
lossless for real text. Reports per-file counts.

DO NOT run while translate_files.py is actively writing EN CSVs — wait until the
run finishes to avoid a read/write race.

Usage:
  python scripts/strip_markers.py --dry-run
  python scripts/strip_markers.py
  python scripts/strip_markers.py --file scrpt.cpk/ST_USI_057.csv
"""
import argparse
import csv
import glob
import os
import sys

EN_DIR = "texts/en"


def clean(text: str) -> str:
    lines = [l for l in text.split("\n") if not l.lstrip().startswith("###")]
    return "\n".join(lines)


def rel_paths() -> list[str]:
    return sorted(
        os.path.relpath(p, EN_DIR).replace(os.sep, "/")
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
        new = clean(old)
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
    parser.add_argument("--file",    help="Only this file (relative path)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = [args.file.replace("\\", "/")] if args.file else rel_paths()
    total_rows = total_files = 0
    for rel in files:
        if not os.path.exists(os.path.join(EN_DIR, rel)):
            print(f"  missing: {rel}")
            continue
        n = process(rel, apply=not args.dry_run)
        if n:
            total_rows += n
            total_files += 1
            print(f"  {rel}: {n} row(s)")

    verb = "would clean" if args.dry_run else "cleaned"
    print(f"\n{verb} {total_rows} row(s) across {total_files} file(s).")
    if args.dry_run and total_rows:
        print("Re-run without --dry-run to apply (only when no translation is running).")


if __name__ == "__main__":
    main()
