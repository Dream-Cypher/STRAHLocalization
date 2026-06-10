"""
Builds texts/en/_speaker_names.json — a map from each Japanese speaker `name`
(the plate shown in the dialogue box) to its English form. convert_csv_to_json.py
loads this and rewrites item["name"] so speaker plates show in English.

Covers ~99% of on-screen name occurrences via a base-name map + composition of
parenthetical qualifiers (e.g. 菱形窓（影ソウ） -> "Sou Hishigata (Shadow Sou)")
and a few patterns (〜の声 -> "X's Voice", N日の〜 -> "X (Nth)"). Rare descriptive
one-off labels are left untranslated (reported at the end).

  python scripts/build_speaker_names.py
"""
import re, json, glob, sys, collections

BASE = {
 '網代慎平':'Shinpei Ajiro','シンペイ':'Shinpei','小舟澪':'Mio Kofune','ミオ':'Mio','ウシオ':'Ushio',
 '小舟潮':'Ushio Kofune','潮':'Ushio','南方ひづる':'Hizuru Minakata','菱形窓':'Sou Hishigata','窓':'Sou','ソウ':'Sou',
 '小弓場かおり':'Kaori Koyumiba','カオリ':'Kaori','凸村哲':'Tetsu Totsumura','トツムラ':'Totsumura',
 '菱形朱鷺子':'Tokiko Hishigata','トキコ':'Tokiko','チトセ':'Chitose','根津銀次郎':'Ginjiro Nezu','ネゴロ':'Negoro',
 '根来小百合':'Sayuri Negoro','南方竜之介':'Ryunosuke Minakata','南雲竜之介':'Ryunosuke Nagumo','竜之介':'Ryunosuke',
 'シデ':'Shide','ハイネ':'Heine','雁切真砂人':'Masahito Karikiri','雁切':'Karikiri','小舟アラン':'Alan Kofune',
 '菱形青銅':'Seidou Hishigata','菱形紙垂彦':'Shidehiko Hishigata','南方波稲':'Hoine Minakata','波稲':'Hoine',
 '小早川朝子':'Asako Kobayakawa','シオリ':'Shiori','小早川しおり':'Shiori Kobayakawa','ギルデンスターン':'Guildenstern',
 'ローゼンクランツ':'Rosencrantz','菱形千登勢':'Chitose Hishigata','人渕先生':'Hitobuchi-sensei',
 '人渕かなえ':'Kanae Hitobuchi','役場の職員':'Town Hall Clerk','野良の影':'Stray Shadow','野良の影Ａ':'Stray Shadow A',
 '野良の影Ｂ':'Stray Shadow B','（ト書き）':'(Stage Direction)','先生':'Sensei','汐見静':'Shizuka Shiomi',
 '黒スーツの女':'Woman in Black Suit','動画の潮':'Ushio (Video)','浜路俊':'Shun Hamaji','浜路あかり':'Akari Hamaji',
 'ヒルコ':'Hiruko','四本腕の影':'Four-Armed Shadow','？？？':'???','中村':'Nakamura','網代暁見':'Akemi Ajiro',
 '網代透':'Toru Ajiro','影Ａ':'Shadow A','影Ｂ':'Shadow B','影Ｃ':'Shadow C','影たち':'Shadows',
 '島内放送':'Island Broadcast','商工会の人':'Chamber Member','動画配信者':'Streamer','動画のウシオ':'Ushio (Video)',
 '船内アナウンス':'Ship Announcement','ファンたち':'Fans','灯台照':'Akari Toudai','観光客':'Tourist',
 '船長':'Captain','男':'Man','女':'Woman','三浦':'Miura',
}
QUAL = {'過去':'Past','収録':'Recording','大人':'Adult','ポニテ':'Ponytail','14年前':'14 Years Ago',
 '１４年前':'14 Years Ago','素顔':'True Face','欠損素顔':'Damaged True Face','赤ん坊':'Baby','ブッチー':'Bucchi'}


def tr_qual(q):
    if q in QUAL: return QUAL[q]
    if q.startswith('影'): return 'Shadow ' + BASE.get(q[1:], q[1:])
    return translate(q) or BASE.get(q, q)


def translate(name):
    if name in BASE: return BASE[name]
    m = re.match(r'^(.*?)（(.+)）$', name)          # Base（Qual）
    if m and BASE.get(m.group(1)): return f'{BASE[m.group(1)]} ({tr_qual(m.group(2))})'
    m = re.match(r'^(.+)の声$', name)               # 〜の声 -> X's Voice
    if m and BASE.get(m.group(1)): return f"{BASE[m.group(1)]}'s Voice"
    m = re.match(r'^(\d+)日の(.+)$', name)          # N日の〜 -> X (Nth)
    if m and BASE.get(m.group(2)): return f"{BASE[m.group(2)]} ({int(m.group(1))}th)"
    return None


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    spk = collections.Counter()
    for p in glob.glob('original_files/json/scrpt.cpk/*.json'):
        for it in json.load(open(p, encoding='utf-8')).get('message', []):
            if it.get('name'): spk[it['name']] += 1
    out, miss = {}, []
    for n, c in spk.items():
        t = translate(n)
        (out.__setitem__(n, t) if t else miss.append((n, c)))
    json.dump(out, open('texts/en/_speaker_names.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    occ = sum(spk.values()); cov = sum(spk[n] for n in out)
    print(f'mapped {len(out)}/{len(spk)} names  ({cov}/{occ} occurrences, {100*cov/occ:.1f}%)')
    print(f'unmapped one-off labels left as-is: {len(miss)}')


if __name__ == '__main__':
    main()
