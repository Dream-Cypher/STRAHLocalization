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

# Dialogue box width (chars). English lines wider than this clip at the right edge,
# so re-wrap them at word boundaries. Existing (short-enough) line breaks are kept;
# only over-long lines are split, and never mid-word.
DIALOGUE_WIDTH = 48


_RICH_TAG = re.compile(r"<[^>]+>")   # TextMeshPro tags (e.g. <color=#..>..</color>) are zero-width


def _visible_len(s: str) -> int:
  return len(_RICH_TAG.sub("", s))


def wrap_dialogue(text: str, width: int = DIALOGUE_WIDTH) -> list[str]:
  """Re-flow the whole entry to lines of <= width VISIBLE chars, breaking only at
  spaces (never mid-word) and treating rich-text tags as zero-width. The source's
  own line breaks are collapsed and re-wrapped, which uses the box far more
  efficiently than preserving them."""
  out: list[str] = []
  cur = ""
  for word in text.replace("\n", " ").split(" "):
    if not word:
      continue
    cand = word if not cur else f"{cur} {word}"
    if not cur or _visible_len(cand) <= width:
      cur = cand
    else:
      out.append(cur)
      cur = word
  if cur:
    out.append(cur)
  return out or [""]

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
