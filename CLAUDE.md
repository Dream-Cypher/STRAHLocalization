# STRAH: Another Horizon — English localization

English fan-localization of the Switch VN "STRAH: Another Horizon" (サマータイムレンダ
Another Horizon), forked from the Chinese `STRAHChsLocalization`. As of 2026-06, fully
translated and building; the working patch is `out/patch-switch.zip`.

> This file travels with the repo. If you're a fresh Claude session, this is your context.
> The authoritative build steps are in `BUILD_ENGLISH_PATCH.txt` (this repo).

## Two repos
This is a DERIVATIVE of two upstream GitHub repos (forks recommended — see below):
- THIS repo `STRAHLocalization` — the EN localization (texts, scripts, files, original_files, this CLAUDE.md, BUILD_ENGLISH_PATCH.txt, issues/). Run everything from here.
- `STRAHLocalizationHelper` — the patcher tool (C#/.NET 8, AssetStudio-based), a SEPARATE repo. We made one fix there (see Gotchas). Clone it as a SIBLING directory so the `../STRAHLocalizationHelper` paths resolve, or adjust the paths. Prebuilt exe: `../STRAHLocalizationHelper/.../win-x64/publish/STRAHLocalizationHelper.exe` (keep its `x64/` native folder next to it).
- Upstream: github.com/Xzonn/STRAHChsLocalization and .../STRAHChsLocalizationHelper. License: CC BY-NC-SA 4.0 (localization) — keep attribution + same license.
- `original_files/Switch` is the actual game dump (copyright; .gitignored — provide your own).

## Building the patch (summary; see BUILD_ENGLISH_PATCH.txt)
Run from THIS repo with env `XZ_LANGUAGE=en` (the helper defaults to `zh_Hans` = Chinese!), `XZ_GAME=STRAH`:
1. `python scripts/convert_csv_to_json.py`  (texts/en/*.csv → texts/en/*.json)
2. run the helper exe (uses this repo as its working dir; loads original_files/Switch + files/)
3. zip `out/01005940182ec000/` → keep it VERSIONED in `out/_archive/patch-en-<timestamp>.zip` + copy to `out/patch-switch.zip`.
- LayeredFS patch for Atmosphere CFW (title `01005940182EC000`). To test: DELETE the old `01005940182ec000` off the SD first, then copy the new one.
- Prereqs: Python 3.10+ (pipeline is pure stdlib). Non-stdlib deps go in a **project venv** (`.venv/`, gitignored) — `py -3.10 -m venv .venv` then `.venv\Scripts\python -m pip install -r requirements.txt` (openpyxl). For image work also `pip install UnityPy Pillow` into the venv. Don't install into system Python. .NET 8 SDK only if recompiling the helper; Windows x64 to RUN the helper.

## Pipeline scripts (scripts/)
- `convert_csv_to_json.py` — CSV→JSON. Wraps XMESS dialogue at `DIALOGUE_WIDTH` (48), re-flow, word-breaks only, `<color>` tags zero-width. Translates tips/flowchart/flymove/metadata/choices. Does NOT translate the speaker `name` field (see Gotchas).
- `translate_files.py` — Ollama (`qwen3:30b-a3b`; host `http://$OLLAMA_IP:11434`, default IP `10.219.72.133`, LAN-only — override with the `OLLAMA_IP` env var) per-file translator: gap-fill, runaway guard, keep-first dedup. `is_untranslated()` flags any kana/kanji.
- Other passes (all done/working): `fill_untranslated.py`, `condense_long.py`, `repair_speaker_echo.py`, `normalize_en.py`, `fix_terms.py`, `audit_translations.py`, `build_speaker_names.py`, `make_overlays.py`.
- **Translation review (play-through QA)** — needs the venv (openpyxl):
  - `build_review_sheet.py` → `issues/translation_review.xlsx`: one row per visible string (cols: route, chapter, file, id, type, speaker, speaker_ja, japanese, english, **proposed_fix**, notes), JA⨝EN joined on `(file,id)`, sorted by route+file. Covers the dialogue scripts AND the aux text files (tips/flowchart/metadata/UI/flymove, route label `(...)`, each joined to its `texts/ja/` source). `chapter` = each file's own `XCHAPTITLE` (the script files DON'T share the flowchart's numbering — only 80/180 titles match `FlowChartData`, so the flowchart is not a per-line chapter key). Workbook is gitignored (regenerable; shareable via OneDrive/Excel-for-web — keep it as real `.xlsx`).
  - `apply_review_fixes.py` → reads filled `proposed_fix` rows back into the EN CSV (scrpt dir or aux root, resolved from `file`) by `(file,id)`. Dry-run by default; `--apply` to write; logs to `issues/applied_fixes_<ts>.csv`. Preserves CSV format (in-field `\n`, `\r\n` records). Review `git diff texts/en` before committing.
  - `audit_gender.py` → flags he/she pronoun errors by comparing EN against the gendered Chinese (他/她) / Japanese (彼/彼女) reference (catches MT mistakes where JA omitted the pronoun). Conservative; seeds `GENDER(...)` tags into the `notes` column + a report with ±2 surrounding lines for context. `--prefill` seeds case-preserving he→she swaps into `proposed_fix` for high-conf rows. (2026-06 pass: 65 lines corrected; 7 ambiguous keeps remain, intentionally.)

## Image-form text (speaker names + QTE prompts + manual) — done via dim+overlay
These are IMAGES, not text:
- 135 `talker_*` name plates in `mgr/adv2.unity3d` (selected by the name→index table `spriteDataLists.spriteDataOnes` = {charName, nameSprite}).
- `adv_action_ACT_NNN_L/R` + `adv_action_words*` QTE prompts (~26) in the same bundle.
- 5 `manual_p*` pages in `data/manuals.unity3d` (`manual_p6` intentionally left original).
Approach: dim the original Japanese 30% + composite English (blue `#15679A` fill, white outline,
Inter SemiBold, auto-fit + word-wrap). EDITABLE maps: `files/_talker_map.json`, `files/_action_map.json`.
Regenerate with `python scripts/make_overlays.py [--only <sprite>]` → writes `files/sprites/<name>.png`.
Helper replaces Sprites from `files/sprites/`, Texture2D from `files/images/` — never put the same
name in both. Style knobs are at the top of `make_overlays.py`. (No scratch is kept in the repo;
originals can be re-dumped from the bundle with UnityPy if you need to inspect them.)

## Official name readings (use these everywhere)
小舟=Kofune (not Kobune) · 南方=Minakata (not Minamikata) · 菱形窓=Sou (not Mado) ·
人渕=Hitobuchi (nickname Bucchi) · 凸村=Totsumura · 中村=Nakamura · 暁見=Akemi · エリカ=Erika · ハイネ=Haine.
Long vowels are romanized ASCII-only (no macrons): simplify (竜之介=Ryunosuke, 銀次郎=Ginjiro)
unless that leaves an ugly/colliding name, then keep `ou`/`uu` (窓=Sou, 青銅=Seidou). See the
"Long vowels" + "verified spellings" notes in `texts/en/GLOSSARY.md` (2026-06 official cross-check).
(Sources: ja.wikipedia Another Horizon + en.wikipedia/Fandom Summer Time Rendering. Full character
glossary in `texts/en/GLOSSARY.md`.)

## Gotchas / hard-won learnings
- `<color=#GF_TIPS_NNN>` / `<color=#GF_KEY_*>` are SYMBOLIC highlight colors the game resolves at runtime (the gold "keyword" tint on TIPS terms), NOT hex and NOT a link to TIPS #NNN — preserve them verbatim around the term; only translate the text between the tags. (e.g. フカン→"bird's-eye view" stays inside the tag.)
- Romaji-only lines slip past `is_untranslated()` (it flags kana/kanji, not Latin). A few lines were left as romanized Japanese (e.g. `ST_TET_007/XMESS_0020` "Fukan suru no ya!") — these read as "English" to the checker. Worth a dedicated romaji sweep if hunting stragglers.
- The scrpt `name` field is a lookup KEY (→ talker image), NOT display text — translating it makes the name plate BLANK. Leave it Japanese; English comes from the `talker_*` overlays.
- Helper `ReplaceMonoBehaviour` default case reads `texts/{language}/` (it used to hard-code `zh_Hans`, silently shipping Japanese tips/flowchart/flymove). Already fixed + recompiled.
- `qwen3` is a thinking model: model calls need `num_predict` ≥ ~2048 or `content` returns empty.
- Fonts: NO replacement by default (the original JP font has Latin). Inter is opt-in via `scripts/download_fonts_inter.ps1` (staged in `files/_optional_fonts/`).
- UnityPy reads/inspects `.unity3d` bundles; the helper writes only changed bundles (LayeredFS overlay). Patched textures are stored uncompressed (BGRA32), so image-heavy builds grow.

## Status / open items
- Done & verified in the patch: all dialogue, UI, tips, flowchart, metadata, sprites, manuals 1–5, speaker-name + QTE overlays.
- LineMismatch ~2829 (89% off-by-one, content intact) — judged a non-issue; revisit only if it overflows in-game.
- Accepted minor compromises: a few metadata labels kept as kanji (no ≤byte-budget English), date placeholder "??/??", `manual_p6` original.

## Working preferences (from the user)
- Don't rebuild the patch until ALL pending edits are staged — one batched, versioned build.
- On any "revert to a previous model's translation", preserve the discarded version with a suffix (e.g. `_old`, or the model name) instead of overwriting; never delete either version.
