"""
Bundles texts/ja/**/*.csv into a handful of plain-text chunk files, sized to
paste/upload into a single LLM chat turn, plus one instructions file
(with the glossary embedded) to send first.

Run from the project root:  python scripts/consolidate_chunks.py

Output goes to texts/en/_chunks/:
  chunk_000_INSTRUCTIONS.txt   <- paste this first, once, at the start of the chat
  chunk_001.txt, chunk_002.txt, ...  <- paste one per turn, in order

A custom ###FILE/###ID marker format is used instead of raw CSV, because
dialogue `target` fields contain literal embedded newlines that would be
ambiguous (and easy for a chat UI to mangle) if pasted as CSV text.
"""
import csv
import glob
import os
import re

SRC_DIR = "texts/ja"
GLOSSARY_PATH = "texts/en/GLOSSARY.md"
OUT_DIR = "texts/en/_chunks"

# Target size budget per chunk, in source (Japanese) characters. This is a
# proxy for how much the model will need to produce in English; if replies come
# back truncated, lower this and re-run. If there's headroom, raise it.
MAX_CHARS_PER_CHUNK = 8000


def load_glossary_blocks(path: str) -> str:
  """Pull the fenced ``` code blocks out of GLOSSARY.md so they can be
  embedded directly in the instructions — no manual copy/paste needed."""
  with open(path, "r", encoding="utf-8") as f:
    text = f.read()
  blocks = re.findall(r"```\n(.*?)```", text, re.DOTALL)
  return "\n".join(block.strip("\n") for block in blocks)


def build_instructions(glossary_text: str) -> str:
  return f"""\
You are translating an otome/visual-novel game ("STRAH: Another Horizon", a
side-story set in the world of "Summer Time Rendering") from Japanese into
natural, fluent English. I will paste the script in numbered chunks across
several messages in this chat — please keep track of established names,
terminology, and character voices across all of them for consistency.

=== OUTPUT FORMAT (read carefully — this will be parsed by a script) ===

Each entry below looks like:

  ###FILE: <path>
  ###ID: <id> | SPEAKER(JA): <name>
  <Japanese text, possibly multiple lines>

For EVERY entry, reply with the SAME ###FILE / ###ID marker lines, completely
unchanged (do not translate, remove, renumber, or reformat them — I match
your translations back to the source files using these exact strings),
followed by your English translation in place of the Japanese text.

Do not add commentary, headers, explanations, or extra blank lines beyond
what's needed to separate entries. Just the markers and the translations,
so the whole reply can be parsed mechanically.

=== LINE BREAKS ARE FUNCTIONAL — PRESERVE THEM ===

Each line break in the source becomes a literal on-screen line break in the
game (the engine does not auto-wrap dialogue). Keep the SAME NUMBER of lines
in your translation, with similar relative balance/length per line — don't
collapse multi-line dialogue into one paragraph, and don't introduce breaks
that aren't in the source.

=== SPEAKER CONTEXT ===

"SPEAKER(JA)" names the character speaking, in Japanese — cross-reference
the glossary below to identify them and match their established voice/tone
(e.g., protagonist Shinpei Ajiro speaks casually; adjust register per
character and scene as the glossary's character notes indicate).

=== STYLE CONVENTIONS (apply consistently, including to names/terms not yet in the glossary) ===

- Keep Japanese honorifics (-san, -chan, -kun, -senpai, -sama, etc.) in romanized form.
- Render "……" as a single "…" character, and "〜" as "~".
- No special formatting (italics, quote styles, etc.) is needed to distinguish
  internal monologue from spoken dialogue — the game engine already handles that.

=== GLOSSARY ===

{glossary_text}

=== END OF INSTRUCTIONS ===

Reply "Ready" and I'll paste the first chunk.
"""


def gather_files() -> list[tuple[str, list[dict], int]]:
  """Returns (relative_path, rows_needing_translation, char_budget) per file,
  in a stable order, skipping files with nothing to translate."""
  results = []
  pattern = os.path.join(SRC_DIR, "**", "*.csv")
  for path in sorted(glob.glob(pattern, recursive=True)):
    rel = os.path.relpath(path, SRC_DIR).replace(os.sep, "/")
    with open(path, "r", encoding="utf-8", newline="") as f:
      rows = [row for row in csv.DictReader(f) if row["target"].strip()]
    if not rows:
      continue
    char_budget = sum(len(row["target"]) for row in rows)
    results.append((rel, rows, char_budget))
  return results


def pack_into_chunks(files: list[tuple[str, list[dict], int]]) -> list[list[tuple[str, list[dict]]]]:
  """Greedy bin-packing by character budget. Never splits a single file
  across chunks, so each ###FILE block stays intact and easy to track."""
  chunks: list[list[tuple[str, list[dict]]]] = []
  current: list[tuple[str, list[dict]]] = []
  current_chars = 0
  for rel, rows, char_budget in files:
    if current and current_chars + char_budget > MAX_CHARS_PER_CHUNK:
      chunks.append(current)
      current = []
      current_chars = 0
    current.append((rel, rows))
    current_chars += char_budget
  if current:
    chunks.append(current)
  return chunks


def write_chunk(path: str, chunk: list[tuple[str, list[dict]]]) -> None:
  with open(path, "w", encoding="utf-8") as out:
    for rel, rows in chunk:
      out.write(f"###FILE: {rel}\n")
      for row in rows:
        speaker = row["developer_comments"].strip()
        marker = f"###ID: {row['id']}"
        if speaker:
          marker += f" | SPEAKER(JA): {speaker}"
        out.write(marker + "\n")
        out.write(row["target"])
        out.write("\n")
      out.write("\n")


def main() -> None:
  os.makedirs(OUT_DIR, exist_ok=True)

  glossary_text = load_glossary_blocks(GLOSSARY_PATH)
  with open(os.path.join(OUT_DIR, "chunk_000_INSTRUCTIONS.txt"), "w", encoding="utf-8") as f:
    f.write(build_instructions(glossary_text))

  files = gather_files()
  total_rows = sum(len(rows) for _, rows, _ in files)
  total_chars = sum(c for _, _, c in files)
  print(f"Found {len(files)} files with translatable text ({total_rows} rows, {total_chars} source chars)")

  chunks = pack_into_chunks(files)
  for i, chunk in enumerate(chunks, start=1):
    chunk_path = os.path.join(OUT_DIR, f"chunk_{i:03d}.txt")
    write_chunk(chunk_path, chunk)
    rows = sum(len(r) for _, r in chunk)
    chars = sum(sum(len(row["target"]) for row in r) for _, r in chunk)
    print(f"  {chunk_path}: {len(chunk)} files, {rows} rows, {chars} source chars")

  print(f"\nWrote {len(chunks)} chunks + instructions to {OUT_DIR}/")
  print("Paste chunk_000_INSTRUCTIONS.txt first (once), then chunk_001.txt, chunk_002.txt, ... in order.")


if __name__ == "__main__":
  main()
