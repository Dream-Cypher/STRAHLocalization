"""
Audits texts/en/**/*.csv against texts/ja/**/*.csv.

Checks:
  1. Missing entries     — ID exists in JA but not in EN
  2. Untranslated        — EN target contains Japanese/Chinese characters
  3. Same as source      — EN target is byte-identical to JA target
  4. Line count mismatch — non-empty line count differs between JA and EN
  5. Name/term issues    — honorific substitutions, known bad terms, stray CJK

Three-way comparison mode shows JA / ZH / EN side by side.

Usage:
  python scripts/audit_translations.py                     # full audit, all files
  python scripts/audit_translations.py --file scrpt.cpk/ST_HDR_005.csv
  python scripts/audit_translations.py --compare scrpt.cpk/ST_HDR_005.csv
  python scripts/audit_translations.py --sample 20
  python scripts/audit_translations.py --sample 20 --file scrpt.cpk/ST_HDR_005.csv
  python scripts/audit_translations.py --issues-only       # summary, problem files only
"""

import argparse
import csv
import glob
import os
import random
import re
import sys

JA_DIR = "texts/ja"
EN_DIR = "texts/en"
ZH_DIR = "texts/zh_Hans"

# ── character detection ───────────────────────────────────────────────────────

# Unicode ranges that should not appear in English translations
_CJK_RE = re.compile(
    r"[぀-ゟ"   # hiragana
    r"゠-ヿ"   # katakana
    r"一-鿿"   # CJK unified ideographs (main block)
    r"㐀-䶿"   # CJK extension A
    r"＀-￯"   # fullwidth / halfwidth forms
    r"　-〿]"  # CJK symbols & punctuation (e.g. 「」、。)
)

# ── name / term checks ────────────────────────────────────────────────────────

# (pattern, message, is_regex)
TERM_CHECKS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b[Ss]hadow [Ii]llness\b"),
     "use 'Shadow Sickness' not 'Shadow Illness'"),
    (re.compile(r"\bYagiburi\b", re.IGNORECASE),
     "wrong name — should be 'Karikiri'"),
    (re.compile(r"\bMr\.\s+[A-Z]|Ms\.\s+[A-Z]|Mrs\.\s+[A-Z]|Miss\s+[A-Z]"),
     "honorific substitution — use Japanese suffix (-san, -kun, etc.)"),
    (re.compile(r"……"),
     "double ellipsis '……' not normalised to '…'"),
    (re.compile(r"\.{3,}"),
     "ASCII dot run not normalised to '…'"),
    (re.compile(r"\bthe teacher\b", re.IGNORECASE),
     "soft: 'the teacher' may be 先生 → should be 'Sensei' (check context)"),
    (re.compile(r"\btide\b", re.IGNORECASE),
     "soft: 'tide' may be 潮/ウシオ used as a name — check context"),
    (re.compile(r"【|】"),
     "Japanese lenticular brackets 【】 not converted to []"),
]

# ── helpers ───────────────────────────────────────────────────────────────────

def read_csv(path: str) -> dict[str, dict]:
    """Return {id: row_dict} for a CSV file, or {} if missing."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["id"].strip(): row for row in csv.DictReader(f) if row.get("id", "").strip()}


def content_lines(text: str) -> list[str]:
    return [l for l in text.split("\n") if l.strip()]


def line_count(text: str) -> int:
    """On-screen line count, matching the engine's target.split('\\n').
    Counts every newline-separated segment (blank lines included), since the
    game renders each as its own line. Text is assumed already .strip()'d."""
    return text.count("\n") + 1 if text else 0


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def truncate(text: str, width: int = 70) -> str:
    text = text.replace("\n", " ↵ ")
    return text if len(text) <= width else text[:width - 1] + "…"


def rel_paths() -> list[str]:
    return sorted(
        os.path.relpath(p, JA_DIR).replace("\\", "/")
        for p in glob.glob(os.path.join(JA_DIR, "**", "*.csv"), recursive=True)
    )


# ── issue types ───────────────────────────────────────────────────────────────

class Issue:
    def __init__(self, kind: str, id_: str, detail: str,
                 ja: str = "", en: str = "", zh: str = ""):
        self.kind   = kind    # MISSING | UNTRANSLATED | SAME | LINES | TERM | CJK
        self.id_    = id_
        self.detail = detail
        self.ja     = ja
        self.en     = en
        self.zh     = zh

    def is_soft(self) -> bool:
        return self.kind == "TERM" and self.detail.startswith("soft:")


def audit_file(rel: str) -> list[Issue]:
    ja_rows = read_csv(os.path.join(JA_DIR, rel))
    en_rows = read_csv(os.path.join(EN_DIR, rel))
    issues: list[Issue] = []

    for id_, ja_row in ja_rows.items():
        ja_text = ja_row.get("target", "").strip()
        if not ja_text:
            continue

        if id_ not in en_rows:
            issues.append(Issue("MISSING", id_, "not in EN CSV", ja=ja_text))
            continue

        en_text = en_rows[id_].get("target", "").strip()

        if not en_text or en_text == ja_text:
            issues.append(Issue("SAME", id_, "EN == JA (untranslated)", ja=ja_text, en=en_text))
            continue

        if has_cjk(en_text):
            issues.append(Issue("CJK", id_, "CJK characters in EN text", ja=ja_text, en=en_text))

        ja_lc = line_count(ja_text)
        en_lc = line_count(en_text)
        if ja_lc != en_lc:
            issues.append(Issue(
                "LINES", id_,
                f"JA={ja_lc} lines  EN={en_lc} lines",
                ja=ja_text, en=en_text,
            ))

        for pattern, msg in TERM_CHECKS:
            if pattern.search(en_text):
                issues.append(Issue("TERM", id_, msg, ja=ja_text, en=en_text))

    return issues


# ── display helpers ───────────────────────────────────────────────────────────

def print_issue(issue: Issue, show_text: bool = True) -> None:
    tag = f"[{issue.kind}]"
    print(f"  {tag:<14} {issue.id_:<20}  {issue.detail}")
    if show_text and issue.ja:
        print(f"    JA: {truncate(issue.ja)}")
    if show_text and issue.en:
        print(f"    EN: {truncate(issue.en)}")


def print_three_way(id_: str, speaker: str,
                    ja: str, zh: str, en: str,
                    flag: str = "") -> None:
    header = f"  {id_}"
    if speaker:
        header += f"  [{speaker}]"
    if flag:
        header += f"  *** {flag} ***"
    print(header)
    for label, text in [("JA", ja), ("ZH", zh), ("EN", en)]:
        if text:
            lines = text.split("\n")
            print(f"    {label}: {lines[0]}")
            for l in lines[1:]:
                print(f"        {l}")
    print()


# ── modes ─────────────────────────────────────────────────────────────────────

def run_audit(files: list[str], issues_only: bool, show_detail: bool) -> None:
    total_entries = total_issues = 0
    counts = {"MISSING": 0, "SAME": 0, "CJK": 0, "LINES": 0, "TERM": 0}
    file_summaries: list[tuple[str, int, dict[str, int]]] = []

    for rel in files:
        ja_rows = read_csv(os.path.join(JA_DIR, rel))
        n_entries = sum(1 for r in ja_rows.values() if r.get("target", "").strip())
        issues = audit_file(rel)

        fc: dict[str, int] = {k: 0 for k in counts}
        for iss in issues:
            fc[iss.kind] = fc.get(iss.kind, 0) + 1
            counts[iss.kind] = counts.get(iss.kind, 0) + 1
        total_entries += n_entries
        total_issues  += len(issues)
        file_summaries.append((rel, n_entries, fc))

    print(f"\n{'=' * 72}")
    print(f"  TRANSLATION AUDIT")
    print(f"  Files: {len(files)}   Entries: {total_entries}   Issues: {total_issues}")
    print(f"  Missing:{counts['MISSING']}  Untranslated:{counts['SAME']}"
          f"  CJK-in-EN:{counts['CJK']}  LineMismatch:{counts['LINES']}"
          f"  Terms:{counts['TERM']}")
    print(f"{'=' * 72}\n")

    # Per-file summary table
    col = 46
    hdr = f"  {'FILE':<{col}}  {'entries':>7}  {'miss':>4}  {'same':>4}  {'cjk':>4}  {'lines':>5}  {'terms':>5}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for rel, n, fc in file_summaries:
        has_issues = any(v for v in fc.values())
        if issues_only and not has_issues:
            continue
        flag = " !" if has_issues else ""
        print(f"  {rel:<{col}}  {n:>7}  {fc['MISSING']:>4}  {fc['SAME']:>4}"
              f"  {fc['CJK']:>4}  {fc['LINES']:>5}  {fc['TERM']:>5}{flag}")

    if not show_detail:
        print("\nRun with --file <path> for per-entry detail.")
        return

    # Detailed issues
    print()
    for rel in files:
        issues = audit_file(rel)
        if not issues:
            continue
        # Separate hard issues from soft term hits
        hard   = [i for i in issues if not i.is_soft()]
        soft   = [i for i in issues if i.is_soft()]
        print(f"\n── {rel} ──")
        for iss in hard:
            print_issue(iss, show_text=True)
        if soft:
            print(f"  (soft term hits: {len(soft)} — run --compare to inspect)")


def run_file_detail(rel: str) -> None:
    issues = audit_file(rel)
    if not issues:
        print(f"\n{rel}: no issues found.")
        return
    hard = [i for i in issues if not i.is_soft()]
    soft = [i for i in issues if i.is_soft()]
    print(f"\n── {rel} — {len(issues)} issue(s) ──\n")
    for iss in hard:
        print_issue(iss, show_text=True)
    if soft:
        print(f"\n  Soft term hits ({len(soft)}):")
        for iss in soft:
            print_issue(iss, show_text=True)


def run_compare(rel: str) -> None:
    ja_rows = read_csv(os.path.join(JA_DIR, rel))
    en_rows = read_csv(os.path.join(EN_DIR, rel))
    zh_rows = read_csv(os.path.join(ZH_DIR, rel))

    print(f"\n{'=' * 72}")
    print(f"  THREE-WAY COMPARISON: {rel}")
    print(f"{'=' * 72}\n")

    for id_, ja_row in ja_rows.items():
        ja_text  = ja_row.get("target", "").strip()
        en_text  = en_rows.get(id_, {}).get("target", "").strip() if en_rows else ""
        zh_text  = zh_rows.get(id_, {}).get("target", "").strip() if zh_rows else ""
        speaker  = ja_row.get("developer_comments", "").strip()
        if not ja_text:
            continue
        ja_lc = line_count(ja_text)
        en_lc = line_count(en_text)
        flag = ""
        if not en_text or en_text == ja_text:
            flag = "UNTRANSLATED"
        elif ja_lc != en_lc:
            flag = f"LINE MISMATCH JA={ja_lc} EN={en_lc}"
        elif has_cjk(en_text):
            flag = "CJK IN EN"
        print_three_way(id_, speaker, ja_text, zh_text, en_text, flag)


def run_sample(n: int, rel: str | None) -> None:
    if rel:
        files = [rel]
    else:
        files = rel_paths()

    pool: list[tuple[str, str]] = []
    for f in files:
        ja_rows = read_csv(os.path.join(JA_DIR, f))
        for id_, row in ja_rows.items():
            if row.get("target", "").strip():
                pool.append((f, id_))

    sample = random.sample(pool, min(n, len(pool)))
    sample.sort()

    print(f"\n{'=' * 72}")
    print(f"  SAMPLE ({len(sample)} entries)")
    print(f"{'=' * 72}\n")

    for f, id_ in sample:
        ja_row = read_csv(os.path.join(JA_DIR, f)).get(id_, {})
        en_row = read_csv(os.path.join(EN_DIR, f)).get(id_, {})
        zh_row = read_csv(os.path.join(ZH_DIR, f)).get(id_, {})
        ja = ja_row.get("target", "").strip()
        en = en_row.get("target", "").strip()
        zh = zh_row.get("target", "").strip()
        spkr = ja_row.get("developer_comments", "").strip()
        ja_lc = line_count(ja)
        en_lc = line_count(en)
        flag = ""
        if not en or en == ja:
            flag = "UNTRANSLATED"
        elif ja_lc != en_lc:
            flag = f"LINE MISMATCH JA={ja_lc} EN={en_lc}"
        elif has_cjk(en):
            flag = "CJK IN EN"
        print(f"  [{f}]")
        print_three_way(id_, spkr, ja, zh, en, flag)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--file",        help="Audit or compare a single file (relative path)")
    parser.add_argument("--compare",     help="Three-way JA/ZH/EN comparison for a file")
    parser.add_argument("--sample",      type=int, metavar="N",
                        help="Show N random entries in three-way view")
    parser.add_argument("--issues-only", action="store_true",
                        help="Summary table: only show files that have issues")
    parser.add_argument("--detail",      action="store_true",
                        help="Print per-entry detail after the summary table")
    args = parser.parse_args()

    if args.compare:
        run_compare(args.compare.replace("\\", "/"))
    elif args.sample is not None:
        run_sample(args.sample, args.file.replace("\\", "/") if args.file else None)
    elif args.file:
        run_file_detail(args.file.replace("\\", "/"))
    else:
        files = rel_paths()
        run_audit(files, issues_only=args.issues_only, show_detail=args.detail)


if __name__ == "__main__":
    main()
