"""
Condenses the handful of dialogue lines whose English is too long to fit the
dialogue box even after wrapping at DIALOGUE_WIDTH (they spill to 5+ lines).

For each over-long entry it asks the local model to shorten the wording WITHOUT
changing the meaning (preserving names, honorifics, <color> tags and parentheses),
verifies the result now wraps to <= MAX_LINES, and writes it back to the EN CSV.
Entries that already fit, or that the model can't shrink in 2 rounds, are left.

  python scripts/condense_long.py --dry-run
  python scripts/condense_long.py
  python scripts/condense_long.py --file scrpt.cpk/ST_USI_074.csv
"""
import argparse, csv, glob, os, re, sys
import translate_files as tf

WIDTH, MAX_LINES, ROUNDS = 40, 4, 2
TAG = re.compile(r"<[^>]+>")
vis = lambda s: len(TAG.sub("", s))

SYSTEM = (
  "You shorten one line of an English video-game translation so it fits a narrow "
  "on-screen text box, WITHOUT changing its meaning or tone.\n"
  "Rules:\n"
  "- Keep natural, fluent English in the same register.\n"
  "- Preserve character names and Japanese honorifics (-san, -kun, -chan, -sensei, etc.) exactly.\n"
  "- Preserve any <color=...>...</color> tags exactly as written.\n"
  "- If the line is wrapped in parentheses (an internal thought), keep the parentheses.\n"
  "- Keep the ellipsis character … and the final punctuation.\n"
  "- Reply with ONLY the shortened line — no quotes, labels, or notes."
)


def wrap(text):   # re-flow to <= WIDTH visible chars, break only at spaces (matches converter)
    out, cur = [], ""
    for w in text.replace("\n", " ").split(" "):
        if not w: continue
        cand = w if not cur else cur + " " + w
        if not cur or vis(cand) <= WIDTH: cur = cand
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out or [""]


def clean(s):
    s = s.strip().strip('"').strip("”“").strip()
    return re.sub(r"\s*\n\s*", " ", s).strip()       # collapse to running text; converter re-wraps


def tags(s):
    return sorted(TAG.findall(s))


def condense(model, text):
    """Return a shortened version that fits, or None if it can't be made to fit."""
    src = text.replace("\n", " ").strip()
    best = None
    for rnd in range(ROUNDS):
        budget = 135 if rnd == 0 else 110
        user = f"Rewrite this shorter (about {budget} characters max), keeping all meaning:\n\n{src}"
        # qwen3 thinks first (~800 tok) then answers — give it room, else content is empty
        out, _ = tf.ollama_chat(model, SYSTEM, user, num_predict=2048, temperature=0.4)
        cand = clean(out)
        if not cand or tf.KANA_KANJI.search(cand):     # empty or leaked Japanese
            continue
        if tags(cand) != tags(text):                   # color tags must survive verbatim
            continue
        if len(wrap(cand)) <= MAX_LINES:
            return cand
        best = cand if (best is None or vis(cand) < vis(best)) else best
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--model", default=tf.DEFAULT_MODEL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    files = ([os.path.join("texts/en", args.file.replace("\\", "/"))]
             if args.file else sorted(glob.glob("texts/en/scrpt.cpk/*.csv")))

    targets = []
    for p in files:
        for r in csv.DictReader(open(p, encoding="utf-8-sig", newline="")):
            t = (r.get("target", "") or "").strip()
            if t and len(wrap(t)) > MAX_LINES:
                targets.append((p, r["id"], t))
    print(f"over-long entries: {len(targets)} in {len({t[0] for t in targets})} files")
    if args.dry_run:
        for p, i, t in targets[:10]:
            print(f"  {os.path.basename(p)}/{i}  ({len(wrap(t))} lines)  {t.replace(chr(10),' ')[:70]}")
        return

    tf.check_server(args.model); system = tf.load_system_prompt()  # warms/validates server
    fixed = {}; failed = []
    for idx, (p, i, t) in enumerate(targets, 1):
        new = condense(args.model, t)
        if new:
            fixed.setdefault(p, {})[i] = new
            print(f"[{idx}/{len(targets)}] {os.path.basename(p)}/{i}: {len(wrap(t))} -> {len(wrap(new))} lines")
        else:
            failed.append((os.path.basename(p), i))
            print(f"[{idx}/{len(targets)}] {os.path.basename(p)}/{i}: COULD NOT FIT (left as-is)")
        tf.log(f"CONDENSE {os.path.basename(p)}/{i}: {'ok' if new else 'FAILED'}")

    for p, edits in fixed.items():
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f); fields = list(rd.fieldnames); rows = list(rd)
        for r in rows:
            if r["id"] in edits: r["target"] = edits[r["id"]]
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

    print(f"\ncondensed {sum(len(e) for e in fixed.values())}/{len(targets)};  still too long: {len(failed)}")
    for nm, i in failed: print(f"   {nm}/{i}")


if __name__ == "__main__":
    main()
