"""
Translates remaining chunk files using a local Ollama model.

Reads  texts/en/_chunks/chunk_NNN.txt  (from consolidate_chunks.py)
Writes texts/en/_chunks/response_NNN.txt

Skips chunks that already have a response file — safe to resume after interruption.
Applies the same ID-format fixes as the chunk workflow automatically.

Usage:
  python scripts/translate_local.py
  python scripts/translate_local.py --model qwen2.5:14b-instruct-q4_K_M
  python scripts/translate_local.py --chunk 011        # single chunk
  python scripts/translate_local.py --from-chunk 020   # resume from chunk 020
  python scripts/translate_local.py --force            # re-translate even if response exists
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

OLLAMA_IP         = os.getenv("OLLAMA_IP", "10.219.72.133")  # LAN Ollama server; override via OLLAMA_IP env var
OLLAMA_HOST       = f"http://{OLLAMA_IP}:11434"
DEFAULT_MODEL     = "qwen3:30b-a3b-q4_K_M"
CHUNKS_DIR        = "texts/en/_chunks"
REQUEST_TIMEOUT   = 900   # 15 minutes per batch
MAX_IDS_PER_REQUEST = 120
WARMUP_PROMPT = "Reply with only the word: Ready"

FIX_5DIGIT   = re.compile(r"(###ID: [A-Z]+_)0(\d{4})(?!\d)")
FIX_BARE_NUM = re.compile(r"(###ID: )(\d{4})(?!\d)(\s|$|\|)")
ID_RE        = re.compile(r"^###ID:\s*([^\s|]+)", re.MULTILINE)
ID_MARKER    = "###ID:"          # used for streaming detection
BAR_WIDTH    = 28


# ── progress display ──────────────────────────────────────────────────────────

def _bar(got: int, expected: int, width: int = BAR_WIDTH) -> str:
    filled = int(width * got / expected) if expected else 0
    return "█" * filled + "░" * (width - filled)


class BatchDisplay:
    """Prints and updates a single-line progress display for one batch."""

    def __init__(self, b_idx: int, n_batches: int | str, expected: int) -> None:
        self.b_idx    = b_idx
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
                display: BatchDisplay | None = None) -> tuple[str, dict]:
    """Stream /api/chat; update display as IDs arrive.
    Returns (full_text, stats) where stats has eval_count, eval_duration,
    prompt_eval_count, prompt_eval_duration (all from the done event)."""

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     True,
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            "num_ctx":     32768,
            "thinking":    False,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    parts: list[str] = []
    stats: dict = {}
    # Tail buffer to catch ###ID: split across stream chunks.
    # We keep (MARKER_LEN-1) chars so a marker spanning two chunks isn't missed.
    _mlen = len(ID_MARKER)  # 6
    tail  = ""

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
                if display is not None:
                    window = tail + content
                    # Count markers in full window. Tail is exactly (MARKER_LEN-1)=5
                    # chars, so it can never hold a complete 6-char marker — no
                    # double-counting is possible.
                    count = window.count(ID_MARKER)
                    if count:
                        display.update(display.got + count)
                    tail = window[-(_mlen - 1):]

            if obj.get("done"):
                stats = {
                    "eval_count":          obj.get("eval_count", 0),
                    "eval_duration":       obj.get("eval_duration", 0),
                    "prompt_eval_count":   obj.get("prompt_eval_count", 0),
                    "prompt_eval_duration": obj.get("prompt_eval_duration", 0),
                }
                break

    return "".join(parts), stats


# ── entry annotation ─────────────────────────────────────────────────────────

def annotate_lines(entry: str) -> str:
    """Append [N lines] to the ID line when entry has multiple content lines."""
    lines = entry.split("\n")
    content = [l for l in lines[1:] if l.strip()]
    if len(content) > 1:
        lines[0] = f"{lines[0].rstrip()} [{len(content)} lines]"
        return "\n".join(lines)
    return entry


# ── ID repair ─────────────────────────────────────────────────────────────────

def fix_ids(text: str) -> str:
    text = FIX_5DIGIT.sub(r"\1\2", text)
    text = FIX_BARE_NUM.sub(r"\1XMESS_\2\3", text)
    text = re.sub(r"…{2,}", "…", text)
    text = re.sub(r"\.{3,}", "…", text)   # ASCII dot runs → ellipsis
    text = _dedup_ids(text)
    return text


def _dedup_ids(text: str) -> str:
    """Remove duplicate (file, id) entries globally, keeping the last occurrence.
    Keys by (current_file, id) so same-ID entries from different files are kept.
    The model sometimes echoes the input or repeats the same file+id pair."""
    segments = re.split(r"(?=^###(?:FILE|ID):)", text, flags=re.MULTILINE)
    # First pass: find last segment index for each (file, id) pair
    cur_file = ""
    last_idx: dict[tuple[str, str], int] = {}
    for i, seg in enumerate(segments):
        if seg.startswith("###FILE:"):
            m = re.match(r"^###FILE:\s*(\S+)", seg)
            if m:
                cur_file = m.group(1)
        elif seg.startswith("###ID:"):
            m = re.match(r"^###ID:\s*([^\s|]+)", seg)
            if m:
                last_idx[(cur_file, m.group(1))] = i
    # Second pass: emit all segments, skip ###ID: entries that aren't the last
    cur_file = ""
    result = []
    for i, seg in enumerate(segments):
        if seg.startswith("###FILE:"):
            m = re.match(r"^###FILE:\s*(\S+)", seg)
            if m:
                cur_file = m.group(1)
            result.append(seg)
        elif seg.startswith("###ID:"):
            m = re.match(r"^###ID:\s*([^\s|]+)", seg)
            if m and last_idx.get((cur_file, m.group(1))) != i:
                continue  # earlier duplicate for same (file, id) — skip
            result.append(seg)
        else:
            result.append(seg)
    return "".join(result)


# ── chunk splitting ───────────────────────────────────────────────────────────

def split_file_block(header: str, entries: list[str], max_ids: int) -> list[str]:
    batches = []
    for start in range(0, len(entries), max_ids):
        batches.append(header + "".join(entries[start:start + max_ids]))
    return batches


def split_into_batches(chunk_text: str, max_ids: int) -> list[str]:
    file_blocks = re.split(r"(?=^###FILE:)", chunk_text, flags=re.MULTILINE)
    file_blocks = [b for b in file_blocks if b.strip()]

    sub_blocks: list[tuple[int, str]] = []
    for block in file_blocks:
        m = re.match(r"(^###FILE:[^\n]*\n)", block, re.MULTILINE)
        header = m.group(1) if m else ""
        body   = block[len(header):]
        entries = [e for e in re.split(r"(?=^###ID:)", body, flags=re.MULTILINE) if e.strip()]
        if len(entries) <= max_ids:
            sub_blocks.append((len(entries), block))
        else:
            for sub in split_file_block(header, entries, max_ids):
                sub_blocks.append((len(re.findall(r"^###ID:", sub, re.MULTILINE)), sub))

    batches: list[str] = []
    current: list[str] = []
    current_count = 0
    for count, text in sub_blocks:
        if current and current_count + count > max_ids:
            batches.append("".join(current))
            current = []
            current_count = 0
        current.append(text)
        current_count += count
    if current:
        batches.append("".join(current))

    return batches


# ── main ──────────────────────────────────────────────────────────────────────

def check_server(model: str) -> None:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        names = [m["name"] for m in data.get("models", [])]
        if not any(model in n for n in names):
            print(f"WARNING: model '{model}' not found on server.")
            print(f"  Available: {names}")
            print(f"  Run: ollama pull {model}")
            sys.exit(1)
        print(f"Server OK — model '{model}' ready.")
    except (urllib.error.URLError, OSError) as e:
        print(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")
        sys.exit(1)


def warmup(model: str, system: str) -> None:
    """Send a trivial request so the model is fully loaded before real work starts."""
    print("Warming up model… ", end="", flush=True)
    t0 = time.time()
    ollama_chat(model, system, WARMUP_PROMPT, display=None)
    print(f"done ({time.time() - t0:.1f}s)")


def load_system_prompt() -> str:
    path = os.path.join(CHUNKS_DIR, "chunk_000_INSTRUCTIONS.txt")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"=== END OF INSTRUCTIONS.*$", "", text, flags=re.DOTALL).strip()
    return text


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--model",       default=DEFAULT_MODEL)
    parser.add_argument("--chunk",       help="Translate only this chunk number, e.g. 011")
    parser.add_argument("--from-chunk",  help="Skip all chunks before this number, e.g. 020")
    parser.add_argument("--force",       action="store_true")
    args = parser.parse_args()

    check_server(args.model)
    system_prompt = load_system_prompt()
    warmup(args.model, system_prompt)

    all_chunks = sorted(glob.glob(os.path.join(CHUNKS_DIR, "chunk_[0-9][0-9][0-9].txt")))

    if args.chunk:
        target = f"chunk_{args.chunk.zfill(3)}.txt"
        all_chunks = [c for c in all_chunks if os.path.basename(c) == target]
        if not all_chunks:
            print(f"Chunk '{target}' not found in {CHUNKS_DIR}/")
            sys.exit(1)

    if args.from_chunk:
        threshold = int(args.from_chunk)
        all_chunks = [c for c in all_chunks
                      if int(re.search(r"(\d+)", os.path.basename(c)).group(1)) >= threshold]

    todo: list[tuple[str, str, str]] = []
    skipped = 0
    for chunk_path in all_chunks:
        num = re.search(r"(\d+)", os.path.basename(chunk_path)).group(1)
        resp_path = os.path.join(CHUNKS_DIR, f"response_{num}.txt")
        if not args.force and os.path.exists(resp_path):
            skipped += 1
            continue
        todo.append((num, chunk_path, resp_path))

    if not todo:
        print(f"Nothing to do — all {skipped} chunk(s) already have responses.")
        print("Use --force to re-translate, or --from-chunk N to start from a specific chunk.")
        return

    print(f"Model:   {args.model}")
    print(f"Server:  {OLLAMA_HOST}")
    print(f"To do:   {len(todo)} chunk(s)  (skipping {skipped} already done)")

    failed: list[str] = []
    start_all  = time.time()
    total_toks = 0

    for i, (num, chunk_path, resp_path) in enumerate(todo, 1):
        with open(chunk_path, encoding="utf-8") as f:
            chunk_text = f.read()

        expected = len(ID_RE.findall(chunk_text))

        # Build flat (file_header, entry_text) list for adaptive batching.
        _fblocks = re.split(r"(?=^###FILE:)", chunk_text, flags=re.MULTILINE)
        _flat: list[tuple[str, str]] = []
        for _fb in _fblocks:
            if not _fb.strip():
                continue
            _m = re.match(r"(^###FILE:[^\n]*\n)", _fb, re.MULTILINE)
            _hdr = _m.group(1) if _m else ""
            _body = _fb[len(_hdr):]
            for _e in re.split(r"(?=^###ID:)", _body, flags=re.MULTILINE):
                if _e.strip():
                    _flat.append((_hdr, _e))

        est_batches = max(1, (len(_flat) + MAX_IDS_PER_REQUEST - 1) // MAX_IDS_PER_REQUEST)
        print(f"\n[{i}/{len(todo)}] chunk_{num}.txt  —  {expected} entries"
              + (f"  (~{est_batches} batches)" if est_batches > 1 else ""))

        t0 = time.time()
        response_parts: list[str] = []
        chunk_toks = 0
        pos = 0
        batch_size = MAX_IDS_PER_REQUEST
        b_idx = 0
        failed_chunk = False

        try:
            while pos < len(_flat):
                b_idx += 1
                end = min(pos + batch_size, len(_flat))
                items = _flat[pos:end]

                # Reconstruct batch text, re-emitting ###FILE: header on file change.
                # Annotate multi-line entries with [N lines] so the model knows
                # exactly how many output lines are required.
                batch_txt = ""
                cur_hdr: str | None = None
                for hdr, entry in items:
                    if hdr != cur_hdr:
                        batch_txt += hdr
                        cur_hdr = hdr
                    batch_txt += annotate_lines(entry)

                batch_expected = len(items)
                disp = BatchDisplay(b_idx, "?", batch_expected)
                user_msg = (
                    "IMPORTANT: All translations must be in English only."
                    " Do not use Chinese or any other language.\n\n" + batch_txt
                )
                text, stats = ollama_chat(args.model, system_prompt, user_msg, display=disp)

                eval_tok    = stats.get("eval_count", 0)
                p_tok       = stats.get("prompt_eval_count", 0)
                p_s         = stats.get("prompt_eval_duration", 0) / 1e9
                chunk_toks += eval_tok

                batch_got = len(ID_RE.findall(text))
                disp.finish(eval_tok, p_tok, p_s)

                if batch_got >= batch_expected * 0.9:
                    response_parts.append(text)
                    pos = end
                    batch_size = MAX_IDS_PER_REQUEST  # reset after clean success
                elif batch_got >= min(3, batch_expected):
                    # Partial: keep what we got, next batch = same size so it ends at trigger.
                    # Check if the last counted ID has actual translation content after it.
                    # EOS sometimes fires right after the ID marker with no content.
                    last_id_match = list(re.finditer(r"^###ID:", text, re.MULTILINE))[-1]
                    after = text[last_id_match.start():].split("\n", 1)
                    content_lines = [l for l in (after[1].split("\n") if len(after) > 1 else [])
                                     if l.strip() and not l.startswith("###")]
                    if not content_lines:
                        # Last ID has no content — exclude it so pos doesn't skip past it
                        effective = batch_got - 1
                        text = text[:last_id_match.start()].rstrip("\n") + "\n"
                    else:
                        effective = batch_got
                    response_parts.append(text)
                    pos += effective
                    batch_size = effective or MAX_IDS_PER_REQUEST
                else:
                    print(f"  Batch {b_idx} unrecoverable ({batch_got}/{batch_expected}) — skipping chunk")
                    failed_chunk = True
                    break

        except Exception as e:
            print(f"\n  FAILED ({e})")
            failed.append(f"chunk_{num}.txt")
            continue

        if failed_chunk:
            failed.append(f"chunk_{num}.txt")
            continue

        elapsed = time.time() - t0
        response = fix_ids("\n".join(response_parts))
        got = len(ID_RE.findall(response))

        with open(resp_path, "w", encoding="utf-8") as f:
            f.write(response)

        total_toks    += chunk_toks
        elapsed_all    = time.time() - start_all
        avg_per_chunk  = elapsed_all / i
        eta_s          = avg_per_chunk * (len(todo) - i)
        eta            = (f"{int(eta_s // 3600)}h{int((eta_s % 3600) // 60)}m"
                          if eta_s >= 3600 else f"{int(eta_s // 60)}m{int(eta_s % 60)}s")
        overall_rate   = total_toks / elapsed_all if elapsed_all > 0 else 0
        warn           = f"  *** only {got}/{expected} IDs" if got < expected * 0.9 else ""

        print(f"  → {got}/{expected} IDs  {elapsed:.0f}s"
              f"  {overall_rate:.1f} tok/s avg  ETA {eta}{warn}")

    print()
    if failed:
        print(f"Failed chunks ({len(failed)}) — re-run to retry: {', '.join(failed)}")
    else:
        print("All chunks translated successfully.")
    print("Next step: python scripts/apply_translations.py")


if __name__ == "__main__":
    main()
