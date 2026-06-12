from collections.abc import Callable
import argparse
import csv
import hashlib
import json
import os
import re
import textwrap
from typing import Any

LANGUAGE = os.getenv("XZ_LANGUAGE") or "en"

# The original CJK wrap (11 full-width chars/line) doesn't translate to a
# proportional Latin font; this is a starting character budget per line for
# the flow-chart info box and may need tuning once seen rendered in-game.
FLOW_CHART_LINE_WIDTH = 32

DIR_JSON_ORIGINAL = "original_files/json"
DIR_JSON_TRANSLATED = f"texts/{LANGUAGE}"
DIR_CSV_TRANSLATED = f"texts/{LANGUAGE}"

# Dialogue box width (chars). The real ADV text box ("Text_Main", uGUI Text in
# adv2.unity3d) is 1248x180px @1920x1080, font FOT-NewRodin Pro DB size 40, with
# HorizontalOverflow=Overflow -- the engine does NOT word-wrap, it shows our
# pre-wrapped lines and clips past 1248px. 51 chars wraps to a widest line of
# ~1119px (comfortably under 1248) and keeps every entry to <=4 lines (the box
# fits ~4.6). The whole entry is re-flowed (source newlines collapsed first) to
# <= width VISIBLE chars, breaking only at spaces (never mid-word); among wraps
# that fit, breaks prefer sentence/clause boundaries but never at the cost of an
# extra line, so line counts match the plain greedy wrap exactly.
DIALOGUE_WIDTH = 51


_RICH_TAG = re.compile(r"<[^>]+>")   # TextMeshPro tags (e.g. <color=#..>..</color>) are zero-width
_SENT_ENDERS = ("。", "！", "？", "!", "?", ".")
_CLAUSE_ENDERS = (",", "、", ";", ":")
_OPEN = "\"'“‘「『（([ "
_CLOSE = "\"'”’」』）)] "

# TIPS/keyword highlight: <color=#GF_TIPS_NNN> / <color=#GF_KEY_*> are symbolic color NAMES the game
# resolves at runtime via a special keyword-highlight pass positioned by char-index * fixed advance.
# That positioning matches the full-width CJK grid (zh_Hans/ja look fine) but drifts against
# proportional Latin glyphs, producing a misaligned duplicate "ghost" of the keyword (e.g. "ocean"
# shows once correctly inline and again, offset, further right).
#
# *** DO NOT replace #GF_* with a literal hex color (e.g. "#6FC44F"). This was tried (patch v0.05) and
# *** IT BREAKS THE GAME: the text component's color resolver only recognizes the symbolic #GF_* NAMES
# *** (the original game data uses 171 such tags and ZERO real-hex colors, and no other rich-text tags
# *** like <b>/<i>/<size> appear anywhere). A literal hex is rejected, the line fails to render, TIPS
# *** pages go blank, and the game eventually locks. There is also no separate position field to move
# *** the ghost copy -- its offset is derived purely from the keyword's char index in this same string.
#
# *** ALSO: <color=#GF_TIPS_NNN> is not purely cosmetic -- NNN is the TIPS entry id, and the tag's
# *** presence is what makes the engine fire the "new tip found" popup / register the entry in the
# *** in-game TIPS encyclopedia on first encounter (patch v0.06, which stripped the tag entirely,
# *** confirmed on-device that the popup stops firing without it). Note there's ALSO a separate
# *** `FSG ['GF_TIPS_NNN']` script command right before the dialogue line (untouched by this script,
# *** since it's structural script data, not translated text) -- if re-emitting the tag empty turns
# *** out not to be enough, the FSG command is the next place to look, though editing it is out of
# *** this script's scope (would need helper/scrpt-structure changes, not just text normalization).
#
# So on Latin builds we replace the keyword span `<color=#GF_...>keyword</color>` with plain text for
# display, but RE-EMIT the original `<color=#GF_...>` tag EMPTY (no content) right after it: the
# engine's ghost-duplicate pass draws the tag's *content* a second time, so an empty tag has nothing
# to ghost-draw, while the `#GF_TIPS_NNN`/`#GF_KEY_*` reference itself survives for whatever fires the
# popup. HIGHLIGHT_MODE picks the display form:
#   "mark"  (default) -- wrap the keyword in HL_OPEN/HL_CLOSE for visual emphasis without color.
#   "strip"           -- drop the tags entirely, leaving the bare keyword (no emphasis).
#   "keep"            -- leave the original <color=#GF_...> tags untouched. KNOWN BROKEN on Latin
#                         (misaligned ghost duplicate, as in v0.04); kept only as an escape hatch /
#                         for comparing against the CJK behavior. TIP_TRIGGER has no effect here.
# Override from the command line with --highlight {mark,strip,keep}, --highlight-marker "OPENCLOSE",
# and --tip-trigger {keep,drop}.
HIGHLIGHT_MODE = "mark"

# TIP_TRIGGER: when True (default), re-emit the original <color=#GF_...></color> tag (now empty)
# after the marked/stripped keyword, so the in-game TIPS "new tip" popup still fires. Set to False
# (--tip-trigger drop) to omit it entirely (v0.06 behavior: marker only, no popup). No effect on CJK
# builds or in HIGHLIGHT_MODE "keep".
#
# This is a HYPOTHESIS pending on-device confirmation: if an empty tag turns out not to be enough to
# fire the popup (the engine might require non-empty content), the fallback is a single space inside
# the tag (`<color=#GF_...> </color>` -- the space's ghost-copy is invisible). That would be a
# one-line tweak to the f-string in _replace_gf_span below.
TIP_TRIGGER = True

# HL_OPEN/HL_CLOSE are the "mark" wrapper chars -- single outward-pointing guillemets by default
# (U+2039 SINGLE LEFT-POINTING ANGLE QUOTATION MARK, U+203A SINGLE RIGHT-POINTING ANGLE QUOTATION
# MARK), e.g. "It's a ‹present›". Both are confirmed present in the in-game fonts (fonts.unity3d:
# "Default Font" and "FOT-NewRodin Pro DB"), so there's no tofu risk. Other glyphs from the same fonts
# that work as drop-in replacements via --highlight-marker, if you want a different look:
#   "»«"   double angle quotes, inward
#   "›‹"   single angle quotes, inward (used by v0.06)
#   "→←"   arrows pointing at the keyword (U+2192/U+2190, confirmed present)
#   "⇒⇐"   double arrows (U+21D2/U+21D0, confirmed present, bolder)
#   "[]"   plain brackets
#   "【】"  CJK black lenticular brackets (heavier, very visible)
#   "§§"   section signs (used in the original "could we use § »«" suggestion)
#   "**"   asterisks (markdown-style emphasis)
#   "★★" / "◆◆"  star / diamond bullets (decorative)
# NOTE: the halfwidth arrows "￫￩" (U+FFEB/U+FFE9) are MISSING from both in-game fonts -- do not use.
# Any 2-character string works via --highlight-marker "OPENCLOSE"; the script does not check the
# target font for the chosen chars, so pick something you've confirmed renders (no tofu prevention).
HL_OPEN, HL_CLOSE = "‹", "›"

# Captures the opener tag (group 1, e.g. "<color=#GF_TIPS_058>") and the keyword text (group 2) so
# the opener can be re-emitted empty for TIP_TRIGGER. Non-greedy (.*?) so a line with two keywords
# pairs each opener with its own closer rather than spanning across both.
_GF_SPAN = re.compile(r"(<color=#GF_(?:TIPS|KEY)_[A-Za-z0-9_]+>)(.*?)</color>")


def _replace_gf_span(m: re.Match) -> str:
  opener, keyword = m.group(1), m.group(2)
  trigger = f"{opener}</color>" if TIP_TRIGGER else ""
  if HIGHLIGHT_MODE == "strip":
    return f"{keyword}{trigger}"
  if HIGHLIGHT_MODE == "mark":
    return f"{HL_OPEN}{keyword}{HL_CLOSE}{trigger}"
  return m.group(0)  # "keep": leave the original tag untouched (known-broken ghost on Latin)

# Japanese wave-dash (～ U+FF5E, the glyph the original game data uses 800x and the default JP
# dialogue font renders natively) reads as cheerful/sing-song/teasing elongation. The CSVs carry it
# over as ASCII '~' (or occasionally '〜' U+301C), which looks like noise in English -- normalize back
# to '～'. Digit~digit ("1~9") is a Japanese-style range, not elongation -> hyphenate instead.
WAVE = "～"
_TILDE_RANGE = re.compile(r"(?<=\d)\s*[~〜～]+\s*(?=\d)")
_TILDE_RUN = re.compile(r"[~〜～]+")


def normalize_latin(text: str, sheet_name: str) -> str:
  """Build-time cosmetic fixes for Latin-script languages (no-op for CJK languages, whose source
  data already uses the correct glyphs/colors)."""
  if LANGUAGE in ("ja", "zh_Hans", "zh_Hant"):
    return text
  if HIGHLIGHT_MODE in ("mark", "strip"):
    text = _GF_SPAN.sub(_replace_gf_span, text)
  # "keep": leave <color=#GF_...> tags untouched (known-broken on Latin, see comment above)
  if sheet_name != "Metadata":  # global-metadata.dat slots are fixed-width; '～' is multi-byte vs '~'
    text = _TILDE_RANGE.sub("-", text)
    text = _TILDE_RUN.sub(WAVE, text)
  return text


def _visible_len(s: str) -> int:
  return len(_RICH_TAG.sub("", s))


def _vis(word: str) -> str:
  return _RICH_TAG.sub("", word)


def _is_sentence_break(word: str, next_word: str | None) -> bool:
  """True if `word` ends a sentence. Hard enders (. ! ? 。 ！ ？) always count;
  an ellipsis (… or ..) only counts when the next word starts a NEW sentence
  (capitalized / non-ASCII), so "I…/don't know" stays together."""
  v = _vis(word).rstrip(_CLOSE)
  if not v:
    return False
  if v.endswith("…") or v.endswith(".."):
    if next_word is None:
      return True
    nv = _vis(next_word).lstrip(_OPEN)
    return bool(nv) and (nv[0].isupper() or not nv[0].isascii())
  return v[-1] in _SENT_ENDERS


def _is_clause_break(word: str) -> bool:
  v = _vis(word).rstrip(_CLOSE)
  return bool(v) and v[-1] in _CLAUSE_ENDERS


def _greedy_lines(words: list[str], width: int) -> list[str]:
  """Minimal-line word wrap (the original behavior; also the fallback)."""
  out: list[str] = []
  cur = ""
  for word in words:
    cand = word if not cur else f"{cur} {word}"
    if not cur or _visible_len(cand) <= width:
      cur = cand
    else:
      out.append(cur)
      cur = word
  if cur:
    out.append(cur)
  return out or [""]


def _boundary_lines(words: list[str], width: int) -> list[str]:
  """Like greedy, but when a line must break, retract the break to the latest
  sentence boundary in the line (else clause boundary, else the word boundary)."""
  out: list[str] = []
  n = len(words)
  i = 0
  while i < n:
    # how many words greedily fit starting at i
    j, cur = i, ""
    while j < n:
      cand = words[j] if not cur else f"{cur} {words[j]}"
      if cur and _visible_len(cand) > width:
        break
      cur, j = cand, j + 1
    if j >= n:
      out.append(" ".join(words[i:j]))
      break
    # break is forced after word j-1; prefer the latest sentence, then clause, boundary
    brk = None
    for k in range(j - 1, i - 1, -1):
      if _is_sentence_break(words[k], words[k + 1] if k + 1 < n else None):
        brk = k + 1
        break
    if brk is None:
      for k in range(j - 1, i - 1, -1):
        if _is_clause_break(words[k]):
          brk = k + 1
          break
    if brk is None or brk <= i:
      brk = j   # no usable boundary -> greedy word break
    out.append(" ".join(words[i:brk]))
    i = brk
  return out or [""]


def wrap_dialogue(text: str, width: int = DIALOGUE_WIDTH) -> list[str]:
  """Re-flow the whole entry to <= width VISIBLE chars per line (rich-text tags
  zero-width, never breaking mid-word). Prefer breaking at sentence/clause
  boundaries, but only when it doesn't add a line: the result never uses more
  lines than the plain greedy wrap, preserving the 3-line dialogue box."""
  words = [w for w in text.replace("\n", " ").split(" ") if w]
  if not words:
    return [""]
  greedy = _greedy_lines(words, width)
  nice = _boundary_lines(words, width)
  return nice if len(nice) <= len(greedy) else greedy

# Speaker-name map (JA name -> localized name) for the dialogue `name` field.
# Built by scripts/build_speaker_names (saved to texts/<lang>/_speaker_names.json).
def _load_speaker_names(dir_csv_translated: str) -> dict[str, str]:
  try:
    with open(f"{dir_csv_translated}/_speaker_names.json", "r", encoding="utf-8") as _f:
      return json.load(_f)
  except FileNotFoundError:
    return {}


SPEAKER_NAMES = _load_speaker_names(DIR_CSV_TRANSLATED)


def handle_json(sheet_name: str, handler: Callable[[dict[str, str], Any], Any]) -> bool:
  if not os.path.exists(f"{DIR_CSV_TRANSLATED}/{sheet_name}.csv") or not os.path.exists(
      f"{DIR_JSON_ORIGINAL}/{sheet_name}.json"):
    return False

  with open(f"{DIR_JSON_ORIGINAL}/{sheet_name}.json", "r", -1, "utf8") as reader:
    data = json.load(reader)

  with open(f"{DIR_CSV_TRANSLATED}/{sheet_name}.csv", "r", -1, "utf-8-sig", "ignore", "") as csvfile:
    reader = csv.reader(csvfile)

    row_iter = reader
    headers = next(row_iter)
    translations: dict[str, str] = {}
    for row in row_iter:
      item_dict = dict(zip(headers, row))
      translations[item_dict["id"]] = normalize_latin(item_dict["target"].replace("\\r", "\r"), sheet_name)

  if not handler(translations, data):
    return False

  with open(f"{DIR_JSON_TRANSLATED}/{sheet_name}.json", "w", -1, "utf8", None, "\n") as writer:
    json.dump(data, writer, ensure_ascii=False, indent=2)
  print(f"Converted: {sheet_name}.json")
  return True


def scripts_handler(translations: dict[str, str], data: dict[str, Any]) -> bool:
  messages = data["message"]
  if len(messages) < 1:
    return False

  for i, item in enumerate(messages):
    function = item["function"]
    # NOTE: do NOT translate item["name"] (the speaker plate). It is a render/lookup
    # key, not display text — feeding it English produces a BLANK name plate in-game
    # (the dialogue names are "image-form" per the project README). Left as the
    # original Japanese. SPEAKER_NAMES / build_speaker_names.py kept for a future
    # name-image approach.
    text_id = f"{function}_{i:04d}"
    translation = translations.get(text_id, "")
    if function == "XMESS":
      text_id = f"{function}_{item['msgidx']:04d}"
      translation = translations[text_id]
      item["argument"] = wrap_dialogue(translation)
    elif item["function"] == "XCHAPTITLE":
      item["argument"][0] = f"”{translation}”"
    elif item["function"] == "XCOMMENTVIEW":
      item["argument"][0] = f"”{translation}”"
    elif item["function"] == "XRETURNTODEATH":
      item["argument"][2] = f"”{translation}”"
    elif function == "MSTD":
      for choice_i, choice in enumerate(item["argument"][3:]):
        text_id = f"{function}_{i:04d}-{choice_i}"
        line, _ = choice.split(",", 1)
        translation = translations[text_id]
        item["argument"][3 + choice_i] = f"{translation},{_}"
      continue
    else:
      continue

  return True


def app_game_data_tips_data_handler(translations: dict[str, str], data: dict[str, Any]) -> bool:
  for item in data["datas"]:
    index = item["index"]
    item["titleName"] = translations[f"tip_title#{index:03d}"]
    item["explanation"] = translations[f"tip_explanation#{index:03d}"]

  return True


def flow_chart_data_handler(translations: dict[str, str], data: dict[str, Any]) -> bool:
  for sublist_i, sublist in enumerate(map(lambda x: x["listData"], data["flowChartList"]["listRoot"])):
    for i, item in enumerate(sublist):
      title = translations.get(f"flow_title#{sublist_i:02d}-{i:03d}", "")
      if title:
        item["chapTitle"] = title
      information = translations.get(f"flow_information#{sublist_i:02d}-{i:03d}", "")
      if information:
        if LANGUAGE in ("ja", "zh_Hans", "zh_Hant"):
          # CJK: fixed-width wrap every 11 full-width chars, keeping trailing punctuation on the line
          item["information"] = re.sub(r"(.{11}[，。！？…]*)", r"\1\n", information).strip("\n")
        else:
          # Latin scripts: wrap at word boundaries instead of a fixed character count
          item["information"] = "\n".join(textwrap.wrap(information, FLOW_CHART_LINE_WIDTH, break_long_words=False))

  return True


def text_fly_move_data_handler(translations: dict[str, str], data: dict[str, Any]) -> bool:
  for i, item in enumerate(data["dataList"]):
    item["drawMessage"] = translations[f"fly#{i:02d}"]

  return True


def text_handler(translations: dict[str, str], data: dict[str, str]) -> bool:
  for k, v in data.items():
    md5 = hashlib.md5(k.encode("utf-8")).hexdigest()
    if f"text#{md5}" not in translations:
      continue
    data[k] = translations[f"text#{md5}"]

  return True


def metadata_handler(translations: dict[str, str], data: dict[str, dict[str, int | str]]) -> bool:
  for i, item in enumerate(data):
    item["text"] = translations[f"metadata#0x{item['position']:08x}+{item['length']}"]

  return True


def main() -> None:
  global LANGUAGE, DIR_JSON_TRANSLATED, DIR_CSV_TRANSLATED, SPEAKER_NAMES, HIGHLIGHT_MODE, HL_OPEN, HL_CLOSE, TIP_TRIGGER

  parser = argparse.ArgumentParser(description="Convert translated CSVs to JSON for the patch build.")
  parser.add_argument("--language", "-l", default=None, help="Target language (e.g. en, zh_Hans). "
                       "Overrides $XZ_LANGUAGE; defaults to en.")
  parser.add_argument("--highlight", choices=["mark", "strip", "keep"], default="mark",
                       help="TIPS/keyword color spans (<color=#GF_TIPS_*>/<color=#GF_KEY_*>) on Latin "
                            "builds: 'mark' (default) replaces the span with the keyword wrapped in "
                            "--highlight-marker chars; 'strip' replaces it with the bare keyword (no "
                            "tags, no emphasis); 'keep' leaves the original symbolic color tags "
                            "untouched (KNOWN BROKEN on Latin -- misaligned ghost duplicate, see the "
                            "comment above HIGHLIGHT_MODE in this file). No effect on CJK builds.")
  parser.add_argument("--highlight-marker", default="‹›", metavar="OPENCLOSE",
                       help="Two characters (opener then closer) used by --highlight mark. Default "
                            "'‹›' (single outward-pointing guillemets). Other font-verified "
                            "options: '»«', '›‹', '→←', '⇒⇐', '[]', '【】', '§§'. "
                            "Any 2-char string is accepted; font coverage for the chosen chars is not "
                            "checked (no tofu prevention).")
  parser.add_argument("--tip-trigger", choices=["keep", "drop"], default="keep",
                       help="On Latin builds with --highlight mark/strip, 'keep' (default) re-emits "
                            "an EMPTY <color=#GF_...></color> after the marked keyword so the in-game "
                            "TIPS 'new tip' popup still fires; 'drop' omits it (marker only, v0.06 "
                            "behavior, no popup). No effect on CJK builds or --highlight keep.")
  args = parser.parse_args()

  language = args.language or os.getenv("XZ_LANGUAGE") or "en"
  if language != LANGUAGE:
    LANGUAGE = language
    DIR_JSON_TRANSLATED = f"texts/{LANGUAGE}"
    DIR_CSV_TRANSLATED = f"texts/{LANGUAGE}"
    SPEAKER_NAMES = _load_speaker_names(DIR_CSV_TRANSLATED)

  HIGHLIGHT_MODE = args.highlight
  if len(args.highlight_marker) != 2:
    parser.error("--highlight-marker must be exactly 2 characters (opener then closer)")
  HL_OPEN, HL_CLOSE = args.highlight_marker[0], args.highlight_marker[1]
  TIP_TRIGGER = args.tip_trigger == "keep"

  print(f"Language: {LANGUAGE}")

  os.makedirs(f"{DIR_JSON_TRANSLATED}/scrpt.cpk", exist_ok=True)
  for file_name in os.listdir(f"{DIR_JSON_ORIGINAL}/scrpt.cpk"):
    if not file_name.endswith(".json"):
      continue

    handle_json(f"scrpt.cpk/{file_name.removesuffix('.json')}", scripts_handler)

  handle_json("AppGameDataTipsData", app_game_data_tips_data_handler)
  handle_json("FlowChartData", flow_chart_data_handler)
  handle_json("TextFlyMoveData", text_fly_move_data_handler)
  handle_json("Text", text_handler)
  handle_json("Metadata", metadata_handler)


# Importing this module (e.g. to reuse wrap_dialogue) must NOT run a build.
if __name__ == "__main__":
  main()
