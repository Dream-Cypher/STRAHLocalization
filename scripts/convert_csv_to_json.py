from collections.abc import Callable
import csv
import hashlib
import json
import os
import re
import textwrap
from typing import Any

LANGUAGE = os.getenv("XZ_LANGUAGE") or "zh_Hans"

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
try:
  with open(f"{DIR_CSV_TRANSLATED}/_speaker_names.json", "r", encoding="utf-8") as _f:
    SPEAKER_NAMES = json.load(_f)
except FileNotFoundError:
  SPEAKER_NAMES = {}


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
      translations[item_dict["id"]] = item_dict["target"].replace("\\r", "\r")

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
