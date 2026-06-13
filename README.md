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

- **Speaker name plates** — English text over the dimmed original artwork
- **QTE / action prompts** — the on-screen button prompts during quick-time events
- The in-game **manual** pages

Character-name spellings follow the official *Summer Time Rendering* romanizations
(e.g. Kofune, Minakata, Sou Hishigata). The full glossary is in
[**texts/en/GLOSSARY.md**](texts/en/GLOSSARY.md).

Nintendo Switch version only — it cannot be used on other platforms.

## Major changes & accepted limitations

A few places where this translation works a little differently from the original:

- **TIPS glossary terms are marked with ‹guillemets›** (e.g. "the ‹Hiruko Cave›")
  instead of the original's gold highlight color, which didn't display correctly
  with English text. The "new TIPS entry found" popup still works as normal.
- **A few of the longest TIPS entries are shortened**, since the TIPS encyclopedia's
  text box can only show so many lines. These end with "[Summarized - see notes]". The
  full, unabridged text of **every** TIPS entry is available online at the
  [**TIPS Reference**](https://dream-cypher.github.io/STRAHLocalization/TIPS_reference.html).
- **Three tabs on the Settings screen (Sound/System/Voice) remain in Japanese.**
  Everything else on that screen is in English — these three labels are built into
  the game's program itself rather than its translatable files, so this patch can't
  change them.

## Install

You need a Switch running Atmosphere custom firmware (CFW). Download or build the
patch, then:

1. Unzip the patch.
2. Move the **01005940182ec000** folder into **SD:/atmosphere/contents/**.
3. Launch the game.

> If your console has no **atmosphere** folder and you don't know what CFW is, this patch is not for you.

## Build from source

Requires **Windows x64**, **Python 3.10+** (the pipeline is stdlib-only), and
**pip install UnityPy Pillow** for the image work. The patch tool,
[**STRAHLocalizationHelper**](https://github.com/Dream-Cypher/STRAHLocalizationHelper) (our
fork, with a small language fix), can be downloaded as a prebuilt release — no need to clone or
compile anything. You also need your own dump of the game under **original_files/Switch/** (not
included).

```powershell
$env:XZ_LANGUAGE = "en"           # default is Chinese (zh_Hans)!
python scripts/convert_csv_to_json.py
tools\STRAHLocalizationHelper.exe
# then zip out/01005940182ec000/
```

Full step-by-step guide: [**docs/build.md**](docs/build.md) (also published as the
[**Build Guide**](https://dream-cypher.github.io/STRAHLocalization/build.html)).

## Documentation

The **[documentation site](https://dream-cypher.github.io/STRAHLocalization/)**
(built from [`docs/`](docs/)) has the full TIPS reference, build guide, and
glossary in a readable web format.

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

See the [**LICENSE**](LICENSE) file for the full text. The original Chinese README is preserved as
[**README.zh.md**](README.zh.md).
