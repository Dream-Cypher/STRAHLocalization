"""
Parses the LLM's translated replies (saved as plain-text files) and writes
the translations into texts/en/**/*.csv `target` columns, matched by the
###FILE / ###ID markers that consolidate_chunks.py embedded.

Usage (from the project root):
  Save each LLM reply as texts/en/_chunks/response_001.txt,
  response_002.txt, etc. (matching chunk numbers is helpful but not required
  -- matching is done purely by the ###FILE/###ID markers in the text).

  python scripts/apply_translations.py
  (or pass specific files: python scripts/apply_translations.py path1.txt path2.txt)

Re-running is safe: later files win on (file, id) collisions, so you can
paste a corrected re-translation into a new response_*.txt and re-run.
"""
import csv
import glob
import os
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

EN_DIR = "texts/en"
RESPONSES_DIR = "texts/en/_chunks"

FILE_RE = re.compile(r"^###FILE:\s*(.+?)\s*$")
ID_RE = re.compile(r"^###ID:\s*([^\s|]+)")


def parse_response(path: str) -> dict[tuple[str, str], str]:
  """Returns {(relative_csv_path, id): translated_text}."""
  with open(path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

  found: dict[tuple[str, str], str] = {}
  current_file = None
  current_id = None
  buffer: list[str] = []

  def flush():
    if current_file and current_id:
      found[(current_file, current_id)] = "\n".join(buffer).strip("\n").rstrip()

  for line in lines:
    m_file = FILE_RE.match(line)
    m_id = ID_RE.match(line)
    if m_file:
      flush()
      current_file, current_id, buffer = m_file.group(1).strip(), None, []
    elif m_id:
      flush()
      current_id, buffer = m_id.group(1).strip(), []
    else:
      buffer.append(line)
  flush()
  return found


def apply_to_csv(rel_path: str, id_to_text: dict[str, str]) -> tuple[int, set[str]]:
  """Writes id_to_text into the `target` column of texts/en/<rel_path>.
  Returns (rows_updated, ids_not_found_in_csv)."""
  csv_path = os.path.join(EN_DIR, rel_path)
  if not os.path.exists(csv_path):
    print(f"  WARNING: {csv_path} does not exist -- skipping {len(id_to_text)} entries")
    return 0, set(id_to_text)

  with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

  updated = 0
  seen: set[str] = set()
  for row in rows:
    text = id_to_text.get(row["id"])
    if text is not None:
      row["target"] = text
      seen.add(row["id"])
      updated += 1

  with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

  return updated, set(id_to_text) - seen


def main() -> None:
  response_files = sys.argv[1:] or sorted(glob.glob(os.path.join(RESPONSES_DIR, "response_*.txt")))
  if not response_files:
    print(f"No response files found in {RESPONSES_DIR}/ (expected response_*.txt). "
          f"Save the LLM's replies there first, or pass file paths as arguments.")
    return

  # Later files win on (file, id) collisions -- lets you paste corrections.
  all_translations: dict[tuple[str, str], str] = {}
  for path in response_files:
    parsed = parse_response(path)
    print(f"Parsed {len(parsed)} entries from {path}")
    all_translations.update(parsed)

  by_file: dict[str, dict[str, str]] = {}
  for (rel_path, id_), text in all_translations.items():
    by_file.setdefault(rel_path, {})[id_] = text

  total_updated = 0
  total_missing = 0
  for rel_path, id_to_text in sorted(by_file.items()):
    updated, missing = apply_to_csv(rel_path, id_to_text)
    total_updated += updated
    total_missing += len(missing)
    note = f" -- {len(missing)} ID(s) not found: {sorted(missing)[:5]}" if missing else ""
    print(f"  {rel_path}: updated {updated}/{len(id_to_text)}{note}")

  print(f"\nTotal: {total_updated} rows updated across {len(by_file)} files"
        + (f", {total_missing} unmatched IDs (see warnings above)" if total_missing else ""))


if __name__ == "__main__":
  main()
