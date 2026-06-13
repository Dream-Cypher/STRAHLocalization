---
layout: default
title: Glossary
---

> **Canonical source:** [`texts/en/GLOSSARY.md`](https://github.com/Dream-Cypher/STRAHLocalization/blob/main/texts/en/GLOSSARY.md)
> in the repo — used in-place by the translation pipeline. This page is a
> read-only mirror for the web.

# Summer Time Rendering: Another Horizon — English Localization Glossary (finalized for pasting)

The three code blocks below (Characters / Places / Terminology) are ready to
copy-paste as-is into the translation prompt's `[PASTE YOUR GLOSSARY HERE]`
placeholder. Style decisions and judgment calls on ambiguous readings have
already been made (see "Decisions made for you" at the bottom) so you don't
need to read Japanese to use this.

Everything was extracted directly from the game data (speaker names in
`developer_comments`, chapter titles in `original_files/json/FlowChartData.json`,
and tip titles in `original_files/json/AppGameDataTipsData.json`) — it's a
verified roster of what's actually in the game, not a guess at what might be
in it. The English *spellings* are Hepburn-romanization judgment calls (see
notes below); they're internally consistent and good enough to ship with.

**One optional check**: this game shares its cast/setting with the
"サマータイムレンダ" (Summer Time Rendering) anime, which had an official
English dub release (Disney+). If you happen to recognize any of these
character names from that, feel free to swap in the spelling you remember —
otherwise the ones below are perfectly fine to use as-is.

---

## 1. Characters (canonical name = EN, with variant labels)

Ranked by dialogue-line count (from `developer_comments` across all 180
script CSVs). Top ~10 cover the large majority of all dialogue.

```
網代慎平 = Shinpei Ajiro                       [6320 lines — protagonist]
  網代慎平（収録） = Shinpei Ajiro (Recording)
  網代慎平（影シンペイ） = Shinpei Ajiro (Shadow Shinpei)
  シンペイ = Shinpei                            [nickname/short form, 83]
  シンペイ（ハイネ） = Shinpei (Haine)
  網代慎平（影シンペイ） = Shinpei Ajiro (Shadow Shinpei)

小舟澪 = Mio Kofune                            [1508 lines]
  小舟澪（ミオ） = Mio Kofune (Mio)
  菱形朱鷺子（ミオ） = Tokiko Hishigata (Mio)    [shadow/possession variant]

ウシオ = Ushio                                  [1339]
  ２１日のウシオ = Ushio (21st)
  小舟潮（影ウシオ） = Ushio Kofune (Shadow Ushio)

南方ひづる = Hizuru Minakata                  [951]
  南方ひづる（過去） = Hizuru Minakata (Past)
  南方ひづる（ポニテ） = Hizuru Minakata (Ponytail)
  ？？？（南方ひづる） = ??? (Hizuru Minakata)
  南雲竜之介（ポニテひづる） = Ryunosuke Nagumo (Ponytail Hizuru)
  南雲竜之介（ひづる） = Ryunosuke Nagumo (Hizuru)

菱形窓 = Sou Hishigata                         [843]

小弓場かおり = Kaori Koyuba                     [734]

凸村哲 = Tetsu Totsumura                        [581]

小舟潮 = Ushio Kofune                           [564]
  小舟潮（影ウシオ） = Ushio Kofune (Shadow Ushio)

ミオ = Mio                                       [485]

菱形朱鷺子 = Tokiko Hishigata                   [477]
  菱形朱鷺子（影トキコ） = Tokiko Hishigata (Shadow Tokiko)
  菱形朱鷺子（ミオ） = Tokiko Hishigata (Mio)
  朱鷺子が影！？ = "Tokiko's a Shadow!?"          [tip title — same name]

根津銀次郎 = Ginjiro Nezu
  根津銀次郎（１４年前） = Ginjiro Nezu (14 Years Ago)

南方竜之介 = Ryunosuke Minakata
  南方竜之介（大人） = Ryunosuke Minakata (Adult)
  南雲竜之介 = Ryunosuke Nagumo                  [different surname — alt-timeline self?]

シデ = Shide
  四本腕の影（シデ） = Four-Armed Shadow (Shide)
  シデ（欠損素顔） = Shide (Damaged True Face)

ハイネ = Haine
トキコ = Tokiko
小舟アラン = Alain Kofune
  小舟アラン（影アラン） = Alain Kofune (Shadow Alain)
南方波稲 = Hoine Minakata
  波稲 = Hoine
小早川朝子 = Asako Kobayakawa
  小早川朝子（影アサコ） = Asako Kobayakawa (Shadow Asako)
小早川しおり = Shiori Kobayakawa
  シオリ（ハイネ） = Shiori (Haine)
  シオリ = Shiori
ギルデンスターン = Guildenstern                  [likely Hamlet reference — keep as-is]
菱形青銅 = Seidou Hishigata
菱形千登勢（影チトセ） = Chitose Hishigata (Shadow Chitose)
野良の影Ａ = Stray Shadow A
役場の職員 = Town Hall Clerk
（ト書き） = (Stage Direction)                   [non-character — formatting label]
カオリ = Kaori
トツムラ = Totsumura
汐見静 = Shizuka Shiomi
根来小百合 = Sayuri Negoro
根津薫 = Kaoru Nezu
```

## 2. Place names (from chapter titles / tips)

```
日都ヶ島 = Hitogashima Island                   [main setting]
タカノス山 = Mt. Takanosu
深蛇池 = Shinja Marsh
虎島 = Torashima (Tiger Island)
万年青浜 = Omoto Beach
スナック都 = Snack Miyako                        [bar/snack-stand name]
コバマート = Koba Mart                            [convenience store]
海の宿魚住 = Uozumi Inn                           [seaside inn]
菱形医院 = Hishigata Clinic
ヒルコ洞 = Hiruko Cave
下水道 = the sewers
```

## 3. Recurring in-universe terminology

NOTE: `AppGameDataTipsData` (168 entries) is essentially the developers' own
in-game glossary of key concepts — translate it carefully and consistently,
since these exact terms recur throughout the dialogue.

```
影 = Shadow(s)                          [central concept — capitalize as proper noun in-story]
影の病 = Shadow Sickness
影の能力 = Shadow's Ability / Power of the Shadow
観測者の力 = the Observer's Power
事象の地平線 = Event Horizon              [real physics term, used as a story concept]
過去への干渉 = Interference with the Past
御海送り = Umi-okuri (Sea Send-off)       [local ritual — consider keeping JA term + gloss on first use]
天沼矛 = Amenonuhoko                       [mythological spear, Japanese creation myth — keep as proper noun]
常世 = Tokoyo                              [mythological "eternal realm" — keep as proper noun + gloss]
ドッペルゲンガー = doppelgänger
カプグラ症候群 = Capgras syndrome           [real psychological condition]
惨劇の夜 = the Night of the Tragedy
正義の味方 = Hero of Justice / Champion of Justice
```

## 4. Decisions made for you (so you don't have to call these yourself)

- **Honorifics (`-san`/`-chan`/`-kun`/`-senpai`): KEEP them.** This is the
  prevailing convention in modern English visual-novel/anime localization —
  English-reading fans of this genre expect them, and dropping them erases
  relationship nuance (who's being formal/familiar with whom) that the story
  relies on. Add to the prompt: *"Preserve Japanese honorifics (-san, -chan,
  -kun, -senpai, etc.) in romanized form rather than translating or dropping
  them."*
- **Ellipses `……` → single-character `…` (not `...`).** Keeps spacing/rhythm
  closer to the original and is the standard in professional VN localization.
  Tildes `〜` → `~`.
- **Internal monologue vs. spoken dialogue: no special text formatting
  needed.** The game engine already controls how these are displayed
  (different text boxes/styling); the translated string itself doesn't need
  added markup like italics or quotation conventions.
- **Parenthetical character-state qualifiers** (e.g. "（影シンペイ）" =
  "Shadow Shinpei"): translate them inline, exactly as shown in section 1
  above — e.g. "Shinpei Ajiro (Shadow Shinpei)". These only ever appear in
  `developer_comments` (translator/AI context — not shown on screen), so
  consistency there just keeps the AI from confusing which "version" of a
  character is speaking in a given scene.

- **Long vowels: ASCII only, no macrons.** Don't write *Ryūnosuke / Sō /
  Seidō* (Wikipedia/Disney+ house style); they don't render reliably in the
  game font/UI. The rule: **simplify the long vowel away** (竜之介 → *Ryunosuke*,
  銀次郎 → *Ginjiro*) **unless** dropping it leaves an ugly/confusing 1–2-letter
  name or collides with an English word — then keep the `ou`/`uu` form
  (菱形窓 → *Sou*, not "So"; 青銅 → *Seidou*). Apply this consistently to any new
  name with a long vowel.
- **Name spellings verified against the official release** (Disney+ /
  Wikipedia / Fandom, cross-checked with the anime subs, 2026-06):
  - ハイネ → **Haine** (was "Heine" — corrected everywhere, incl. the
    `talker_013` name plate). Confirmed by both the official wiki *and* the subs.
  - エリカ → **Erika** (was "Erica" — minor; unified across all lines).
  - 小舟アラン → **Alain** (French spelling; was "Alan" — corrected everywhere,
    incl. the `talker_012` / `talker_012s` name plates). Confirmed by both
    en.wikipedia *and* VNDB's entry for this game.
  - 小弓場かおり → **Kaori Koyuba** (was "Koyumiba"; 弓 read as "yu", not
    "yumi"). Per VNDB, user-confirmed; `talker_020` plate regenerated.

These are now baked into section 1's formatting — you don't need to do
anything further with them other than tell the AI to follow the same
conventions for any names/terms it encounters that aren't in this list yet.
