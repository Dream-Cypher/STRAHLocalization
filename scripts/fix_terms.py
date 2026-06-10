"""
Fixes term/honorific issues in texts/en/**/*.csv:

  * Mr./Ms./Mrs./Miss <Name>  ->  <Name>-<suffix>, where the suffix is taken from
    the Japanese source for that row:
      - if the JA line has <name><suffix> adjacent (さん/くん/ちゃん/様/先生/...), use it
      - else if the JA line contains 先生, use -sensei
      - else: LEAVE unchanged and report (we won't invent a register)
  * A few fixed glossary corrections (Shadow Illness -> Shadow Sickness, etc.)

Corrupted names (not in the glossary map — e.g. Erica, Totsuura, Hibune) are a
separate name-fidelity problem; they are reported, never auto-changed.

Run from the project root.
  python scripts/fix_terms.py --dry-run
  python scripts/fix_terms.py
  python scripts/fix_terms.py --file scrpt.cpk/ST_HDR_001.csv
"""
import argparse
import csv
import glob
import os
import re
import sys

JA_DIR, EN_DIR = "texts/ja", "texts/en"

# English name -> Japanese form(s) used in the source (from the glossary).
NAME2JA = {
    "Totsumura": ["凸村"], "Tetsu": ["哲", "凸村"], "Nagumo": ["南雲"],
    "Koyumiba": ["小弓場"], "Nezu": ["根津"], "Hishigata": ["菱形"],
    "Karikiri": ["雁切"], "Hizuru": ["ひづる", "南方"], "Shiomi": ["汐見"],
    "Ajiro": ["網代"], "Kofune": ["小舟"], "Alan": ["アラン"],
    "Kaori": ["小弓場", "カオリ", "かおり"], "Shinpei": ["慎平", "シンペイ"],
    "Mio": ["澪", "ミオ"], "Ushio": ["潮", "ウシオ"], "Ryunosuke": ["竜之介"],
    "Chitose": ["千登勢"], "Kobayakawa": ["小早川"], "Negoro": ["根来"],
    "Nakamura": ["中村"], "Akemi": ["暁見", "あけみ"], "Hitobuchi": ["人渕"],
    "Sou": ["窓", "菱形"], "Minakata": ["南方"], "Erica": ["エリカ"],
}

# Japanese honorific suffix -> romanized form (checked in this order).
SUFFIXES = [
    ("先生", "-sensei"), ("先輩", "-senpai"), ("ちゃん", "-chan"),
    ("くん", "-kun"), ("君", "-kun"), ("様", "-sama"), ("さま", "-sama"),
    ("殿", "-dono"), ("さん", "-san"),
]

# Plain glossary text corrections (case-insensitive key match via regex).
FIXED = [
    (re.compile(r"\b[Ss]hadow [Ii]llness\b"), "Shadow Sickness"),
    (re.compile(r"\bYagiburi\b", re.IGNORECASE), "Karikiri"),
]

HON_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Miss)\.?\s+([A-Z][a-zA-Z]+)")


def adjacent_suffix(name: str, ja: str) -> str | None:
    """Romanized suffix if <jaform><suffix> appears adjacently in the JA line."""
    for form in NAME2JA.get(name, []):
        i = ja.find(form)
        while i != -1:
            rest = ja[i + len(form):]
            for jsuf, rsuf in SUFFIXES:
                if rest.startswith(jsuf):
                    return rsuf
            i = ja.find(form, i + 1)
    return None


def resolve(name: str, ja: str) -> tuple[str | None, str]:
    """Return (replacement_or_None, reason)."""
    if name not in NAME2JA:
        return None, "unmapped-name"          # likely corrupted/wrong name
    suf = adjacent_suffix(name, ja)
    if suf:
        return f"{name}{suf}", "adjacent"
    if "先生" in ja:
        return f"{name}-sensei", "sensei-in-line"
    return name, "drop-title"   # JA attaches no honorific → drop the Mr./Ms.


def process(rel: str, apply: bool, stats: dict) -> int:
    en_path = os.path.join(EN_DIR, rel)
    if not os.path.exists(en_path):
        return 0
    ja = {}
    ja_path = os.path.join(JA_DIR, rel)
    if os.path.exists(ja_path):
        with open(ja_path, encoding="utf-8-sig", newline="") as f:
            ja = {r["id"].strip(): (r.get("target", "") or "") for r in csv.DictReader(f)
                  if r.get("id", "").strip()}

    with open(en_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows   = list(reader)

    changed = 0
    for row in rows:
        old = row.get("target", "") or ""
        new = old
        for pat, repl in FIXED:
            new = pat.sub(repl, new)
        jv = ja.get(row.get("id", "").strip(), "")

        def sub_hon(m):
            name = m.group(1)
            repl, reason = resolve(name, jv)
            if repl:
                stats["fixed"] = stats.get("fixed", 0) + 1
                stats.setdefault("by_suffix", {})
                suf = repl[len(name):] or "(dropped title)"
                stats["by_suffix"][suf] = stats["by_suffix"].get(suf, 0) + 1
                return repl
            stats.setdefault("unresolved", []).append((rel.split("/")[-1], name, reason))
            return m.group(0)

        new = HON_RE.sub(sub_hon, new)
        if new != old:
            row["target"] = new
            changed += 1

    if changed and apply:
        with open(en_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = ([args.file.replace("\\", "/")] if args.file else
             sorted(os.path.relpath(p, EN_DIR).replace(os.sep, "/")
                    for p in glob.glob(os.path.join(EN_DIR, "**", "*.csv"), recursive=True)))

    stats: dict = {}
    total_rows = total_files = 0
    for rel in files:
        n = process(rel, apply=not args.dry_run, stats=stats)
        if n:
            total_rows += n
            total_files += 1

    verb = "would change" if args.dry_run else "changed"
    print(f"\nHonorifics fixed: {stats.get('fixed', 0)}  {stats.get('by_suffix', {})}")
    print(f"{verb} {total_rows} row(s) across {total_files} file(s).")

    unresolved = stats.get("unresolved", [])
    if unresolved:
        from collections import Counter
        by_reason = Counter(r for _, _, r in unresolved)
        by_name   = Counter(n for _, n, _ in unresolved)
        print(f"\nUNRESOLVED (left unchanged for manual review): {len(unresolved)}")
        print(f"  reasons: {dict(by_reason)}")
        print(f"  names:   {dict(by_name.most_common())}")


if __name__ == "__main__":
    main()
