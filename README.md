# Summer Time Rendering: Another Horizon — English Localization

[![CC-BY-NC-SA 4.0](https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-nc-sa.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)

An **English** fan-translation patch for the Nintendo Switch visual novel
*STRAH: Another Horizon* (<span lang="ja">サマータイムレンダ Another Horizon</span>).

This project is an English adaptation built on top of
**[Xzonn's Simplified-Chinese localization](https://github.com/Xzonn/STRAHChsLocalization)**
and its patch tool. It reuses that framework and translates the game into English.

> **For technical and educational exchange only. Please use it only with a legally-owned copy of the game.**

## What's translated

All in-game **dialogue, tips, chapter intros, the flowchart, and menus** are fully translated.
Unlike the original (which left some image-based text in Japanese), this fork also localizes the
**image-form text**:

- **Speaker name plates** (the `talker_*` images) — English over the dimmed original art
- **QTE / action prompts** (the `adv_action_*` images)
- The in-game **manual** pages

Character-name spellings follow the official *Summer Time Rendering* romanizations
(e.g. Kofune, Minakata, Sou Hishigata). The full glossary is in
[`texts/en/GLOSSARY.md`](texts/en/GLOSSARY.md).

Nintendo Switch version only — it cannot be used on other platforms.

## Install

You need a Switch running [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere) custom
firmware (CFW). Download or build the patch, then:

1. Unzip the patch.
2. Move the `01005940182ec000` folder into `SD:/atmosphere/contents/`.
3. Launch the game.

> If your console has no `atmosphere` folder and you don't know what CFW is, this patch is not for you.

## Build from source

Requires **Windows x64**, **Python 3.10+** (the pipeline is stdlib-only), **.NET 8** (only if you
recompile the helper), and `pip install UnityPy Pillow` for the image work. The patch tool,
[`STRAHLocalizationHelper`](https://github.com/Dream-Cypher/STRAHLocalizationHelper) (our fork,
with the language fix described in its `CLAUDE.md`), must be cloned as a **sibling** folder. You
also need your own dump of the game under `original_files/Switch/` (not included — copyrighted).

```powershell
$env:XZ_LANGUAGE = "en"           # default is Chinese (zh_Hans)!
python scripts/convert_csv_to_json.py
..\STRAHLocalizationHelper\STRAHLocalizationHelper\bin\Release\net8.0-windows\win-x64\publish\STRAHLocalizationHelper.exe
# then zip out/01005940182ec000/
```

Full step-by-step guide: **[`BUILD_ENGLISH_PATCH.txt`](BUILD_ENGLISH_PATCH.txt)**.
Project/architecture map (scripts, overlay pipeline, gotchas): **`CLAUDE.md`**.

## Credits

- **Original Simplified-Chinese localization, reverse engineering, and the patch tool:
  [Xzonn](https://github.com/Xzonn)** — [STRAHChsLocalization](https://github.com/Xzonn/STRAHChsLocalization)
  and [STRAHChsLocalizationHelper](https://github.com/Xzonn/STRAHChsLocalizationHelper). This fork
  would not exist without that work.
- English translation and image localization: this fork.

## License

Licensed under **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)**,
the same license as the upstream project. If you build on this work, you must:

- **Attribution** — credit the original author (Xzonn) and this project, with links back.
- **NonCommercial** — do not use it for commercial purposes.
- **ShareAlike** — license your derivative under the same terms.

See the [`LICENSE`](LICENSE) file for the full text. The original Chinese README is preserved as
[`README.zh.md`](README.zh.md).
