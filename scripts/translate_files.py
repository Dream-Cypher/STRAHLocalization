"""
Translates Japanese CSV files one-by-one using a local Ollama model.

For each texts/ja/**/*.csv that doesn't yet have texts/en/**/*.csv output:
  1. Reads all rows, builds ###ID:-only batches (no ###FILE: in the prompt —
     single-file context means no cross-file ID collisions)
  2. Sends to Ollama with adaptive batching
  3. Writes intermediate to texts/en/_translations/<path>.txt  (for inspection)
  4. Applies translations directly to texts/en/<path>.csv

Resume-safe: skips any file whose English CSV already exists.

Usage:
  python scripts/translate_files.py
  python scripts/translate_files.py --file scrpt.cpk/ST_HDR_005.csv
  python scripts/translate_files.py --from-file scrpt.cpk/ST_HDR_010.csv
  python scripts/translate_files.py --force
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

OLLAMA_IP           = os.getenv("OLLAMA_IP", "10.219.72.133")  # LAN Ollama server; override via OLLAMA_IP env var
OLLAMA_HOST         = f"http://{OLLAMA_IP}:11434"
DEFAULT_MODEL       = "qwen3:30b-a3b-q4_K_M"
JA_DIR              = "texts/ja"
EN_DIR              = "texts/en"
TRANSLATIONS_DIR    = "texts/en/_translations"
INSTRUCTIONS_PATH   = "texts/en/_chunks/chunk_000_INSTRUCTIONS.txt"
REQUEST_TIMEOUT     = 900
MAX_IDS_PER_REQUEST = 120
WARMUP_PROMPT       = "Reply with only the word: Ready"

ID_RE     = re.compile(r"^###ID:\s*([^\s|]+)", re.MULTILINE)
ID_MARKER = "###ID:"
BAR_WIDTH = 28

# Hiragana / katakana / CJK ideographs — real Japanese text (NOT punctuation).
KANA_KANJI = re.compile(r"[぀-ゟ゠-ヿ一-鿿㐀-䶿]")


def is_untranslated(text: str | None, source: str = "") -> bool:
    """A row is untranslated if it has no text, or its 'translation' still contains
    Japanese kana/kanji — covering a verbatim echo, a near-echo whose punctuation
    got normalized (so it no longer byte-matches the source), or a partial
    translation with Japanese left in. Pure punctuation like '！！' contains no
    kana/kanji, so it is correctly treated as translated. (`source` is unused now
    but kept for call-site compatibility.)"""
    if not text:
        return True
    return bool(KANA_KANJI.search(text))

FIX_5DIGIT   = re.compile(r"(###ID: [A-Z]+_)0(\d{4})(?!\d)")
FIX_BARE_NUM = re.compile(r"(###ID: )(\d{4})(?!\d)(\s|$|\|)")

LOG_PATH = os.path.join(TRANSLATIONS_DIR, "translate.log")


# ── logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """Append a timestamped line to the run log. Best-effort; never raises."""
    try:
        os.makedirs(TRANSLATIONS_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg.strip(chr(10))}\n")
    except Exception:
        pass


def emit(msg: str) -> None:
    """print() to the console and also record the line in the log."""
    print(msg)
    log(msg)


# ── progress display ──────────────────────────────────────────────────────────

def _bar(got: int, expected: int, width: int = BAR_WIDTH) -> str:
    filled = min(width, int(width * got / expected)) if expected else 0
    return "█" * filled + "░" * (width - filled)


class BatchDisplay:
    def __init__(self, b_idx: int, n_batches: int | str, expected: int) -> None:
        self.b_idx     = b_idx
        self.n_batches = n_batches
        self.expected  = expected
        self.got       = 0
        self.t0        = time.time()
        self._prefix   = f"  {b_idx}/{n_batches}"
        self._render(end="\r")

    def update(self, got: int) -> None:
        self.got = got
        self._render(end="\r")

    def _tok_rate(self, tok: int) -> str:
        elapsed = time.time() - self.t0
        if elapsed < 0.5 or tok == 0:
            return "  —  tok/s"
        return f"{tok / elapsed:5.1f} tok/s"

    def _render(self, tok: int = 0, end: str = "\r") -> None:
        bar  = _bar(self.got, self.expected)
        rate = self._tok_rate(tok)
        line = f"{self._prefix}  {bar}  {self.got:4d}/{self.expected:<4d}  {rate}"
        print(f"\r{line:<78}", end=end, flush=True)

    def finish(self, tok: int, prompt_tok: int, prompt_s: float) -> None:
        elapsed = time.time() - self.t0
        rate    = f"{tok / elapsed:.1f}" if elapsed > 0 else "—"
        bar     = _bar(self.got, self.expected)
        trunc   = "  ~~ split" if 0 < self.got < self.expected * 0.9 else ""
        prompt  = f"  prompt {prompt_tok}t/{prompt_s:.1f}s" if prompt_tok else ""
        line    = (f"{self._prefix}  {bar}  {self.got:4d}/{self.expected:<4d}"
                   f"  {rate} tok/s{prompt}{trunc}")
        print(f"\r{line:<78}")


# ── Ollama API ────────────────────────────────────────────────────────────────

def ollama_chat(model: str, system: str, user: str,
                display: BatchDisplay | None = None,
                num_predict: int | None = None,
                runaway_limit: int | None = None,
                temperature: float = 0.1) -> tuple[str, dict]:
    options = {
        "temperature":    temperature,
        "num_ctx":        32768,
        "thinking":       False,
        "repeat_penalty": 1.3,   # suppress degenerate repetition loops
    }
    if num_predict:
        options["num_predict"] = num_predict   # token ceiling, secondary guard
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     True,
        "keep_alive": -1,
        "options":    options,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    parts: list[str] = []
    stats: dict = {}
    _mlen    = len(ID_MARKER)
    tail     = ""
    id_count = 0
    runaway  = False

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        for raw_line in resp:
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = obj.get("message", {}).get("content", "")
            if content:
                parts.append(content)
                window = tail + content
                count  = window.count(ID_MARKER)
                if count:
                    id_count += count
                    if display is not None:
                        display.update(id_count)
                tail = window[-(_mlen - 1):]
                if runaway_limit and id_count > runaway_limit:
                    runaway = True          # model overshot — stop reading, close conn
                    break

            if obj.get("done"):
                stats = {
                    "eval_count":           obj.get("eval_count", 0),
                    "eval_duration":        obj.get("eval_duration", 0),
                    "prompt_eval_count":    obj.get("prompt_eval_count", 0),
                    "prompt_eval_duration": obj.get("prompt_eval_duration", 0),
                }
                break

    stats["runaway"] = runaway
    return "".join(parts), stats


# ── entry helpers ─────────────────────────────────────────────────────────────

def annotate_lines(entry: str) -> str:
    """Append [N lines] to the ###ID: line when entry has multiple content lines."""
    lines = entry.split("\n")
    content = [l for l in lines[1:] if l.strip()]
    if len(content) > 1:
        lines[0] = f"{lines[0].rstrip()} [{len(content)} lines]"
        return "\n".join(lines)
    return entry


def fix_response(text: str) -> str:
    """Post-process model response: fix ID formatting, ellipsis, deduplicate."""
    text = FIX_5DIGIT.sub(r"\1\2", text)
    text = FIX_BARE_NUM.sub(r"\1XMESS_\2\3", text)
    text = re.sub(r"…{2,}", "…", text)
    text = re.sub(r"\.{3,}", "…", text)
    # Normalise any indented ###ID: lines the model may have added
    text = re.sub(r"^[ \t]+(###ID:)", r"\1", text, flags=re.MULTILINE)
    # Drop stray ###FILE: lines the model echoes from the prompt (the real header
    # is written separately) — otherwise they get glued into translations.
    text = re.sub(r"^[ \t]*###FILE:.*(?:\r?\n)?", "", text, flags=re.MULTILINE)
    text = _dedup_ids(text)
    return text


def _dedup_ids(text: str) -> str:
    """Keep only the FIRST translation for each ###ID:, removing later duplicates.
    Batches never share IDs in this file-by-file flow, so duplicates only arise
    from in-batch model repetition loops — where the first pass is the clean one
    and later repeats tend to degrade."""
    segments = re.split(r"(?=^###ID:)", text, flags=re.MULTILINE)
    first_idx: dict[str, int] = {}
    for i, seg in enumerate(segments):
        if seg.startswith("###ID:"):
            m = re.match(r"^###ID:\s*([^\s|]+)", seg)
            if m and m.group(1) not in first_idx:
                first_idx[m.group(1)] = i
    return "".join(
        seg for i, seg in enumerate(segments)
        if not (
            seg.startswith("###ID:")
            and (m := re.match(r"^###ID:\s*([^\s|]+)", seg))
            and first_idx.get(m.group(1)) != i
        )
    )


# ── CSV I/O ───────────────────────────────────────────────────────────────────

def read_ja_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_entries(rows: list[dict]) -> list[str]:
    """Convert CSV rows into ###ID: entry strings for the prompt."""
    entries = []
    for row in rows:
        id_  = row.get("id", "").strip()
        text = row.get("target", "").strip()
        spkr = row.get("developer_comments", "").strip()
        if not id_ or not text:
            continue
        header = f"###ID: {id_}"
        if spkr:
            header += f" | SPEAKER(JA): {spkr}"
        entries.append(f"{header}\n{text}\n")
    return entries


def parse_response(text: str) -> dict[str, str]:
    """Parse ###ID:-only response into {id: translated_text}."""
    result: dict[str, str] = {}
    cur_id: str | None = None
    buf: list[str] = []

    def flush():
        if cur_id:
            result[cur_id] = "\n".join(buf).strip("\n").rstrip()

    for line in text.splitlines():
        m = re.match(r"^###ID:\s*([^\s|]+)", line)
        if m:
            flush()
            cur_id = m.group(1)
            buf = []
        elif line.lstrip().startswith("###"):
            continue          # stray ###FILE:/### marker echoed by the model — never content
        else:
            buf.append(line)
    flush()
    return result


def apply_to_csv(ja_path: str, en_path: str, translations: dict[str, str]) -> tuple[int, int]:
    """Write English CSV: copy source structure, replace target with translations.
    Returns (rows_translated, rows_untranslated)."""
    with open(ja_path, encoding="utf-8-sig", newline="") as f:
        reader     = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows       = list(reader)

    translated = untranslated = 0
    for row in rows:
        id_  = row.get("id", "").strip()
        src  = row.get("target", "").strip()
        text = translations.get(id_)
        if text and not is_untranslated(text, src):   # real translation, not an echo
            row["target"] = text
            translated += 1
        elif src:
            untranslated += 1

    os.makedirs(os.path.dirname(en_path), exist_ok=True)
    with open(en_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return translated, untranslated


# ── server helpers ────────────────────────────────────────────────────────────

def check_server(model: str) -> None:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        names = [m["name"] for m in data.get("models", [])]
        if not any(model in n for n in names):
            print(f"WARNING: model '{model}' not found. Available: {names}")
            sys.exit(1)
        print(f"Server OK — model '{model}' ready.")
    except (urllib.error.URLError, OSError) as e:
        print(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")
        sys.exit(1)


def warmup(model: str, system: str) -> None:
    print("Warming up model… ", end="", flush=True)
    t0 = time.time()
    ollama_chat(model, system, WARMUP_PROMPT)
    print(f"done ({time.time() - t0:.1f}s)")


def load_system_prompt() -> str:
    # INSTRUCTIONS_PATH is generated by consolidate_chunks.py; fall back to the
    # committed glossary so a fresh checkout can still run without that step.
    path = INSTRUCTIONS_PATH if os.path.exists(INSTRUCTIONS_PATH) else "texts/en/GLOSSARY.md"
    if not os.path.exists(path):
        sys.exit(f"No translation instructions found. Run scripts/consolidate_chunks.py to "
                 f"generate {INSTRUCTIONS_PATH}, or add texts/en/GLOSSARY.md.")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return re.sub(r"=== END OF INSTRUCTIONS.*$", "", text, flags=re.DOTALL).strip()


# ── per-file translation ──────────────────────────────────────────────────────

def translate_file(rel_path: str, model: str, system: str,
                   file_idx: int, total: int,
                   start_batch: int = MAX_IDS_PER_REQUEST,
                   temperature: float = 0.1) -> bool:
    """Translate one CSV file. Returns True on success."""
    ja_path    = os.path.join(JA_DIR, rel_path)
    en_path    = os.path.join(EN_DIR, rel_path)
    inter_path = os.path.join(TRANSLATIONS_DIR, os.path.splitext(rel_path)[0] + ".txt")

    rows    = read_ja_csv(ja_path)
    entries = build_entries(rows)
    if not entries:
        print(f"[{file_idx}/{total}] {rel_path}  — no translatable rows, skipping")
        return True

    expected     = len(entries)
    est_batches  = max(1, (expected + start_batch - 1) // start_batch)
    emit(f"\n[{file_idx}/{total}] {rel_path}  —  {expected} entries"
         + (f"  (~{est_batches} batches)" if est_batches > 1 else ""))

    response_parts: list[str] = []
    pos        = 0
    batch_size = start_batch
    b_idx      = 0
    t0         = time.time()
    file_toks  = 0
    MAX_RETRIES = 2
    MIN_BATCH   = 20

    try:
        while pos < len(entries):
            b_idx += 1
            end   = min(pos + batch_size, len(entries))
            batch = entries[pos:end]

            batch_txt      = "".join(annotate_lines(e) for e in batch)
            batch_expected = len(batch)

            text = ""
            stats: dict = {}
            retry_smaller = False
            for attempt in range(1, MAX_RETRIES + 2):
                disp     = BatchDisplay(b_idx, "?", batch_expected)
                user_msg = (
                    f"Translating: {rel_path}\n\n"
                    "IMPORTANT: All translations must be in English only.\n\n"
                    + batch_txt
                )
                cap    = batch_expected * 160 + 800
                rlimit = batch_expected + max(20, batch_expected // 2)   # ~1.5x
                text, stats = ollama_chat(model, system, user_msg, display=disp,
                                          num_predict=cap, runaway_limit=rlimit,
                                          temperature=temperature)
                text = fix_response(text)
                batch_got = len(ID_RE.findall(text))
                eval_tok  = stats.get("eval_count", 0)
                p_tok     = stats.get("prompt_eval_count", 0)
                p_s       = stats.get("prompt_eval_duration", 0) / 1e9
                file_toks += eval_tok
                disp.finish(eval_tok, p_tok, p_s)

                # Repetition runaway: if dedup didn't recover a usable batch, shrink
                # the batch and retry the same position (smaller spans loop less).
                if stats.get("runaway") and batch_got < batch_expected * 0.9:
                    if batch_expected > MIN_BATCH:
                        batch_size = max(MIN_BATCH, batch_expected // 2)
                        emit(f"  Batch {b_idx} runaway ({batch_got} usable) — "
                             f"shrinking to {batch_size} and retrying")
                        retry_smaller = True
                        break
                    # already minimal — fall through to normal handling below

                if batch_got > 0 or attempt > MAX_RETRIES:
                    break
                emit(f"  Batch {b_idx} got 0 IDs — retry {attempt}/{MAX_RETRIES}")

            if retry_smaller:
                continue   # re-translate same position with a smaller batch_size

            if batch_got >= batch_expected * 0.9:
                response_parts.append(text)
                pos        = end
                batch_size = start_batch
            elif batch_got >= min(3, batch_expected):
                last_id_match  = list(re.finditer(r"^###ID:", text, re.MULTILINE))[-1]
                after          = text[last_id_match.start():].split("\n", 1)
                content_lines  = [l for l in (after[1].split("\n") if len(after) > 1 else [])
                                   if l.strip() and not l.startswith("###")]
                if not content_lines:
                    effective = batch_got - 1
                    text = text[:last_id_match.start()].rstrip("\n") + "\n"
                else:
                    effective = batch_got
                response_parts.append(text)
                pos       += effective
                batch_size = effective or start_batch
            else:
                emit(f"  Batch {b_idx} unrecoverable ({batch_got}/{batch_expected}) — aborting file")
                return False

    except Exception as e:
        emit(f"\n  FAILED ({e})")
        return False

    raw_response = "\n".join(response_parts)
    response     = fix_response(raw_response)
    translations = parse_response(response)

    # ── gap-fill: re-request only the source IDs the model dropped or mis-keyed ──
    # (corrupted IDs like XMESS_0134→XESS, or dropped runs). Cheaper and more
    # convergent than re-translating the whole file for 1-4 missing entries.
    entry_by_id: dict[str, str] = {}
    for e in entries:
        m = re.match(r"^###ID:\s*([^\s|]+)", e)
        if m:
            entry_by_id[m.group(1)] = e
    source_order = list(entry_by_id.keys())
    src_by_id = {r.get("id", "").strip(): (r.get("target", "") or "").strip() for r in rows}
    GAP_ROUNDS, GAP_BATCH = 2, 30
    try:
        for _round in range(GAP_ROUNDS):
            missing = [i for i in source_order
                       if is_untranslated(translations.get(i), src_by_id.get(i, ""))]
            if not missing:
                break
            shown = ", ".join(missing[:8]) + ("…" if len(missing) > 8 else "")
            emit(f"  Gap-fill {_round + 1}/{GAP_ROUNDS}: {len(missing)} missing — {shown}")
            for s in range(0, len(missing), GAP_BATCH):
                chunk     = missing[s:s + GAP_BATCH]
                batch_txt = "".join(annotate_lines(entry_by_id[i]) for i in chunk)
                disp      = BatchDisplay("g", "?", len(chunk))
                user_msg  = (f"Translating: {rel_path}\n\n"
                             "IMPORTANT: All translations must be in English only.\n\n"
                             + batch_txt)
                txt, st = ollama_chat(
                    model, system, user_msg, display=disp,
                    num_predict=len(chunk) * 160 + 800,
                    runaway_limit=len(chunk) + max(20, len(chunk) // 2),
                    temperature=max(temperature, 0.3))   # nudge off the deterministic miss
                txt = fix_response(txt)
                disp.finish(st.get("eval_count", 0), st.get("prompt_eval_count", 0),
                            st.get("prompt_eval_duration", 0) / 1e9)
                for k, v in parse_response(txt).items():
                    if (k in entry_by_id
                            and is_untranslated(translations.get(k), src_by_id.get(k, ""))
                            and not is_untranslated(v, src_by_id.get(k, ""))):
                        translations[k] = v
                response += "\n" + txt
    except Exception as e:
        emit(f"\n  Gap-fill aborted ({e}) — proceeding with what we have")
    # ── end gap-fill ──

    # Apply to English CSV (also tells us how many source rows actually matched)
    translated, untranslated = apply_to_csv(ja_path, en_path, translations)
    complete = translated >= expected

    # On a complete run, write the real intermediate (also the resume skip-marker).
    # On a partial run, write a .partial sidecar for inspection but DO NOT create the
    # real intermediate — so a re-run re-translates the whole file instead of skipping it.
    out_path = inter_path if complete else inter_path + ".partial"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"###FILE: {rel_path}\n")
        f.write(response)
    if complete and os.path.exists(inter_path + ".partial"):
        os.remove(inter_path + ".partial")   # clear stale sidecar from an earlier partial run

    elapsed = time.time() - t0
    note    = f"  ({untranslated} untranslated rows)" if untranslated else ""
    if not complete:
        emit(f"  → {translated}/{expected} rows written  {elapsed:.0f}s"
             f"  *** INCOMPLETE — saved {os.path.basename(out_path)}, will retry on re-run{note}")
        return False
    emit(f"  → {translated}/{expected} rows written  {elapsed:.0f}s{note}")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--model",     default=DEFAULT_MODEL)
    parser.add_argument("--file",      help="Translate only this file, e.g. scrpt.cpk/ST_HDR_005.csv")
    parser.add_argument("--from-file", help="Skip all files alphabetically before this one")
    parser.add_argument("--force",     action="store_true",
                        help="Re-translate even if English CSV already exists")
    parser.add_argument("--batch",     type=int, default=MAX_IDS_PER_REQUEST,
                        help=f"Starting IDs per request (default {MAX_IDS_PER_REQUEST}); "
                             "use a smaller value for repetition-prone files")
    parser.add_argument("--temp",      type=float, default=0.1,
                        help="Sampling temperature (default 0.1); raise (~0.4) to break "
                             "repetition loops on low-entropy files")
    args = parser.parse_args()

    check_server(args.model)
    system = load_system_prompt()
    warmup(args.model, system)

    # Enumerate source files
    all_ja = sorted(
        os.path.relpath(p, JA_DIR).replace("\\", "/")
        for p in glob.glob(os.path.join(JA_DIR, "**", "*.csv"), recursive=True)
    )

    if args.file:
        target = args.file.replace("\\", "/")
        all_ja = [f for f in all_ja if f == target]
        if not all_ja:
            print(f"File '{target}' not found under {JA_DIR}/")
            sys.exit(1)

    if args.from_file:
        threshold = args.from_file.replace("\\", "/")
        all_ja = [f for f in all_ja if f >= threshold]

    todo: list[str] = []
    skipped = 0
    for rel in all_ja:
        inter_path = os.path.join(TRANSLATIONS_DIR, os.path.splitext(rel)[0] + ".txt")
        if not args.force and os.path.exists(inter_path):
            skipped += 1
            continue
        todo.append(rel)

    if not todo:
        print(f"Nothing to do — all {skipped} file(s) already have English CSVs.")
        print("Use --force to re-translate.")
        return

    print(f"\nModel:   {args.model}")
    print(f"Server:  {OLLAMA_HOST}")
    print(f"To do:   {len(todo)} file(s)  (skipping {skipped} already done)")

    ovr = (f"  overrides batch={args.batch} temp={args.temp}"
           if args.batch != MAX_IDS_PER_REQUEST or args.temp != 0.1 else "")
    if ovr:
        print(f"Overrides:{ovr}")
    log("=" * 60)
    log(f"RUN START  model={args.model}  todo={len(todo)}  skipped={skipped}{ovr}")

    failed: list[str] = []
    for i, rel in enumerate(todo, 1):
        ok = translate_file(rel, args.model, system, i, len(todo),
                            start_batch=args.batch, temperature=args.temp)
        if not ok:
            failed.append(rel)

    print()
    if failed:
        emit(f"RUN END  failed ({len(failed)})/{len(todo)} — re-run to retry:")
        for f in failed:
            emit(f"  {f}")
    else:
        emit("RUN END  all files translated successfully.")


if __name__ == "__main__":
    main()
