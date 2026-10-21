# Maç tekrarı (resmî PUBG telemetrisi, pubg.sh benzeri)
import datetime
import json
import os
import urllib.request, urllib.parse, urllib.error
from ..config import DATA
from ..pubg.api import account_id_from_ini, pubg_get

REPLAYS = os.path.join(DATA, 'tekrarlar')
MAPDIR = os.path.join(DATA, 'haritalar')
ASSETS = 'https://raw.githubusercontent.com/pubg/api-assets/master/'
ASSETS_LFS = 'https://media.githubusercontent.com/media/pubg/api-assets/master/'
# telemetri harita adı: (görünen ad, resmî resim adı, boyut cm) — boyutlar PUBG geliştirici belgelerinden
MAP_INFO = {'Baltic_Main': ('Erangel', 'Erangel_Main', 816000), 'Erangel_Main': ('Erangel', 'Erangel_Main', 816000),
            'Desert_Main': ('Miramar', 'Miramar_Main', 816000), 'Savage_Main': ('Sanhok', 'Sanhok_Main', 408000),
            'DihorOtok_Main': ('Vikendi', 'Vikendi_Main', 816000), 'Summerland_Main': ('Karakin', 'Karakin_Main', 204000),
            'Tiger_Main': ('Taego', 'Taego_Main', 816000), 'Kiki_Main': ('Deston', 'Deston_Main', 816000),
            'Chimera_Main': ('Paramo', 'Paramo_Main', 306000), 'Heaven_Main': ('Haven', 'Haven_Main', 102000),
            'Neon_Main': ('Rondo', 'Rondo_Main', 816000), 'Range_Main': ('Camp Jackal', 'Camp_Jackal_Main', 204000)}
MODE_TR = {'squad-fpp': 'Squad FPP', 'squad': 'Squad TPP', 'duo-fpp': 'Duo FPP', 'duo': 'Duo TPP', 'solo-fpp': 'Solo FPP',
           'solo': 'Solo TPP', 'tdm': 'Takım Ölüm Maçı'}


def http_bytes(url, timeout=60, progress=None, headers=None):
    req = urllib.request.Request(url, headers=dict({'User-Agent': 'PUBG-Izleyici', 'Accept-Encoding': 'gzip'}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total, chunks, done = int(r.headers.get('Content-Length') or 0), [], 0
        while True:
            c = r.read(1 << 18)
            if not c:
                break
            chunks.append(c); done += len(c)
            if progress and total:
                progress(done / total)
    b = b''.join(chunks)
    import gzip
    return gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b


def recent_matches(key, name='', limit=15):
    """Son maçların özeti (oyuncu sorgusu 1 istek; maç sorguları PUBG'nin hız sınırına takılmaz)."""
    if name:
        pl = pubg_get('/players?filter[playerNames]=' + urllib.parse.quote(name), key)['data'][0]
    else:
        aid = account_id_from_ini()
        if not aid:
            raise ValueError('Hesap kimliği bulunamadı, PUBG Hesap sekmesinde oyuncu adını yaz.')
        pl = pubg_get('/players/' + aid, key)['data']
    aid = pl['id']
    ids = [x['id'] for x in pl.get('relationships', {}).get('matches', {}).get('data', [])][:limit]
    return aid, pl['attributes']['name'], ids


def match_summary(mid, key, aid):
    d = pubg_get('/matches/' + mid, key)
    a = d['data']['attributes']
    inc = d.get('included', [])
    tel = next((x['attributes'].get('URL') for x in inc if x.get('type') == 'asset'), None)
    parts = {x['id']: x['attributes']['stats'] for x in inc if x.get('type') == 'participant'}
    me = next((s for s in parts.values() if s.get('playerId') == aid), {}) or {}
    ranks = {s.get('playerId'): s.get('winPlace') for s in parts.values()}
    return {'id': mid, 'tel': tel, 'map': a.get('mapName'), 'mode': a.get('gameMode', ''), 'type': a.get('matchType', ''),
            'date': a.get('createdAt', ''), 'dur': a.get('duration', 0), 'rank': me.get('winPlace'), 'kills': me.get('kills', 0),
            'dmg': me.get('damageDealt', 0), 'ranks': ranks, 'aid': aid}


def _ts(s):
    s = s.rstrip('Z')
    if '.' in s:
        a, b = s.split('.', 1)
        s = a + '.' + b[:6]
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc).timestamp()


_WEAPONS = {}


def weapon_names():
    if not _WEAPONS:
        pth = os.path.join(MAPDIR, 'silahlar.json')
        try:
            with open(pth, encoding='utf-8') as f:
                _WEAPONS.update(json.load(f))
        except Exception:
            try:
                _WEAPONS.update(json.loads(http_bytes(ASSETS + 'dictionaries/telemetry/damageCauserName.json', 20)))
                os.makedirs(MAPDIR, exist_ok=True)
                with open(pth, 'w', encoding='utf-8') as f:
                    json.dump(_WEAPONS, f)
            except Exception:
                pass
    return _WEAPONS


def replay_data(events, m):
    """Telemetriyi tekrar sayfasının kullandığı küçük veriye çevirir (20 MB → birkaç yüz KB).
    Koordinatlar harita boyutuna bölünür (0-1), süre maç başlangıcından saniye."""
    mapraw = next((e.get('mapName') for e in events if e['_T'] == 'LogMatchStart'), m['map'])
    mname, _, size = MAP_INFO.get(mapraw, (mapraw, '', 816000))
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    wn = weapon_names()
    W = lambda c: wn.get(c, (c or '').replace('Weap', '').replace('_C', '') or '?')
    n = lambda v: round(v / size, 5)
    P, aid, myteam = {}, m['aid'], None

    def who(c, t):
        if not isinstance(c, dict) or not c.get('accountId'):
            return None
        i = c['accountId']
        p = P.get(i)
        if p is None:
            p = P[i] = {'name': c.get('name', '?'), 'team': c.get('teamId', 0), 'bot': c.get('type') == 'user_ai' or i.startswith('ai.'),
                        'rank': m['ranks'].get(i), 'pos': [], 'death': None, 'dx': 0, 'dy': 0, 'knocks': []}
        loc = c.get('location') or {}
        if t >= 0 and (loc.get('x') or loc.get('y')):
            p['pos'].append([round(t, 1), n(loc['x']), n(loc['y']), round(c.get('health', 100))])
        return p
    kills, shots, drops, zones, phases = [], [], [], [], []
    landing = None
    for e in events:
        typ = e['_T']
        t = _ts(e['_D']) - t0 if '_D' in e else 0
        if typ == 'LogMatchStart':
            for ch in e.get('characters', []):
                who(ch.get('character'), -1)
            continue
        for f in ('character', 'attacker', 'victim', 'killer', 'finisher', 'dBNOMaker'):
            if f in e:
                who(e[f], t)
        if t < 0:
            continue
        if typ == 'LogGameStatePeriodic':
            g = e['gameState']
            z = [round(t, 1)]
            for k in ('safetyZone', 'poisonGasWarning', 'redZone'):
                pos, r = g.get(k + 'Position') or {}, g.get(k + 'Radius') or 0
                z += [n(pos.get('x', 0)), n(pos.get('y', 0)), n(r)]
            zones.append(z)
        elif typ == 'LogPlayerKillV2':
            v = who(e.get('victim'), t)
            if not v:
                continue
            v['death'] = round(t, 1)
            loc = e['victim'].get('location') or {}
            v['dx'], v['dy'] = n(loc.get('x', 0)), n(loc.get('y', 0))
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            cat = info.get('damageTypeCategory', '')
            wpn = 'Mavi bölge' if cat == 'Damage_BlueZone' else ('Kırmızı bölge' if cat == 'Damage_Explosion_RedZone' else
                                                                 W(info.get('damageCauserName')))
            kills.append({'t': round(t, 1), 'k': (k or {}).get('name', ''), 'v': v['name'], 'w': wpn,
                          'd': round((info.get('distance') or 0) / 100), 'hs': info.get('damageReason') == 'HeadShot',
                          'x': v['dx'], 'y': v['dy']})
        elif typ == 'LogPlayerMakeGroggy':
            v = who(e.get('victim'), t)
            if v:
                v['knocks'].append([round(t, 1), None])
        elif typ == 'LogPlayerRevive':
            v = who(e.get('victim'), t)
            if v and v['knocks'] and v['knocks'][-1][1] is None:
                v['knocks'][-1][1] = round(t, 1)
        elif typ == 'LogPlayerTakeDamage' and e.get('damageTypeCategory') == 'Damage_Gun' and e.get('attacker'):
            a, v = e['attacker'].get('location') or {}, e['victim'].get('location') or {}
            if a.get('x') and v.get('x'):
                shots.append([round(t, 1), n(a['x']), n(a['y']), n(v['x']), n(v['y']), e['attacker'].get('teamId', 0)])
        elif typ == 'LogCarePackageLand':
            loc = (e.get('itemPackage') or {}).get('location') or {}
            drops.append([round(t, 1), n(loc.get('x', 0)), n(loc.get('y', 0))])
        elif typ == 'LogPhaseChange':
            phases.append(round(t, 1))
        elif typ == 'LogParachuteLanding' and e['character'].get('accountId') == aid:
            landing = t
    dur = max([m.get('dur') or 0] + [p['pos'][-1][0] for p in P.values() if p['pos']])
    for i, p in P.items():
        p['pos'].sort(key=lambda a: a[0])
        out = []
        for a in p['pos']:  # 0.5 sn'den sık noktaları seyrelt
            if out and a[0] - out[-1][0] < 0.5:
                out[-1] = a
            else:
                out.append(a)
        p['pos'] = out
        p['knocks'] = [[a, b if b is not None else (p['death'] if p['death'] is not None else dur)] for a, b in p['knocks']]
        if i == aid:
            myteam = p['team']
    P = {i: p for i, p in P.items() if p['pos']}
    shots.sort(key=lambda s: s[0])
    try:
        date = datetime.datetime.fromisoformat(m['date'].rstrip('Z')).replace(tzinfo=datetime.timezone.utc).astimezone()
        date = date.strftime('%d.%m.%Y %H:%M')
    except Exception:
        date = m['date']
    return {'mapName': mname, 'mode': MODE_TR.get(m['mode'], m['mode']), 'date': date, 'myRank': m.get('rank'),
            'myKills': m.get('kills', 0), 'myDamage': m.get('dmg', 0), 'teams': len({p['team'] for p in P.values()}),
            'dur': round(dur, 1), 'start': round(max(0, (landing or 0) - 15), 1), 'me': aid, 'myTeam': myteam,
            'players': P, 'zones': zones, 'kills': kills, 'shots': shots, 'drops': drops, 'phases': phases}


def map_low(img, progress=None):
    """Küçük harita resmi (~1 MB, 819 px) — tekrar hemen açılsın diye."""
    os.makedirs(MAPDIR, exist_ok=True)
    name = 'Rondo_Main_No_Text_Low_Res.png' if img == 'Rondo_Main' else f'{img}_Low_Res.png'
    pth = os.path.join(MAPDIR, name)
    if not os.path.exists(pth):
        b = http_bytes(ASSETS + 'Assets/Maps/' + name, 60, progress)
        with open(pth + '.part', 'wb') as f:
            f.write(b)
        os.replace(pth + '.part', pth)
    return pth


def map_tiles(img):
    """Hazır yüksek çözünürlüklü döşeme klasörü ve en yüksek yakınlaştırma düzeyi, yoksa (None, 0)."""
    d = os.path.join(MAPDIR, img + '_hd')
    try:
        with open(os.path.join(d, 'hazir.txt')) as f:
            return d, int(f.read().strip())
    except (OSError, ValueError):
        return None, 0


def build_hd_tiles(img, progress=None):
    """Resmî yüksek çözünürlüklü haritayı (75-120 MB) bir kez indirir ve 256 px'lik döşemelere böler.
    Böylece tekrar sayfası yakınlaştırınca da keskin kalır ve sadece görünen parçaları yükler."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    d = os.path.join(MAPDIR, img + '_hd')
    src = os.path.join(MAPDIR, img + '_High_Res.png')
    pr = progress or (lambda f: None)
    if not os.path.exists(src):
        b = http_bytes(ASSETS_LFS + 'Assets/Maps/' + img + '_High_Res.png', 600, lambda f: pr(0.7 * f))
        with open(src + '.part', 'wb') as f:
            f.write(b)
        os.replace(src + '.part', src)
        del b
    im = Image.open(src).convert('RGB')
    size = im.size[0]
    maxz = max(0, (size // 256).bit_length() - 1)
    side = 256 << maxz
    if im.size != (side, side):
        im = im.resize((side, side), Image.LANCZOS)
    total = sum(4 ** z for z in range(maxz + 1))
    done = 0
    for z in range(maxz, -1, -1):
        n_ = 1 << z
        for x in range(n_):
            os.makedirs(os.path.join(d, str(z), str(x)), exist_ok=True)
            for y in range(n_):
                im.crop((x * 256, y * 256, x * 256 + 256, y * 256 + 256)).save(
                    os.path.join(d, str(z), str(x), f'{y}.jpg'), quality=82, optimize=True)
                done += 1
                if done % 32 == 0:
                    pr(0.7 + 0.3 * done / total)
        if z:
            im = im.resize((im.size[0] // 2, im.size[1] // 2), Image.LANCZOS)
    with open(os.path.join(d, 'hazir.txt'), 'w') as f:
        f.write(str(maxz))
    try:
        os.remove(src)  # döşemeler hazır, 100 MB'lık kaynağı tutmaya gerek yok
    except OSError:
        pass
    return d, maxz


def build_replay(m, progress=None):
    """Telemetriyi indirir, tekrar sayfasını oluşturur, dosya yolunu döner."""
    pr = progress or (lambda txt, f=None: None)
    os.makedirs(REPLAYS, exist_ok=True)
    pr('Telemetri indiriliyor…', 0)
    events = json.loads(http_bytes(m['tel'], 120, lambda f: pr('Telemetri indiriliyor…', 0.6 * f)))
    pr('Maç hesaplanıyor…', 0.65)
    data = replay_data(events, m)
    try:
        from .coach import coach_report  # döngüsel import: koç raporu da harita tablolarını kullanır
        data['report'] = coach_report(events, m, data)  # maç sonu koç raporu
    except Exception:
        data['report'] = None
    del events
    img = MAP_INFO.get(m['map'], ('', 'Erangel_Main', 0))[1]
    pr('Harita hazırlanıyor…', 0.8)
    low = map_low(img, lambda f: pr('Harita indiriliyor…', 0.8 + 0.15 * f))
    tiles, maxz = map_tiles(img)
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    from pathlib import Path
    html = (REPLAY_HTML.replace('__DATA__', js)
            .replace('__TILES__', json.dumps(Path(tiles).as_uri() + '/{z}/{x}/{y}.jpg') if tiles else 'null')
            .replace('__MAXZ__', str(maxz)).replace('__LOWIMG__', json.dumps(Path(low).as_uri())))
    out = os.path.join(REPLAYS, f"{m['id']}.html")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    pr('Hazır', 1)
    return out, img, bool(tiles), data.get('report')


# Tekrar sayfası: Leaflet (harita) + tek tuval katmanı (oyuncular, bölgeler, atışlar) 60 fps çizilir.
REPLAY_HTML = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maç Tekrarı · PUBG İzleyici</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#0e1014;--card:#161a21;--card2:#1d222b;--line:#262b36;--txt:#e8eaed;--sub:#8b93a1;--acc:#4cc2ff;--ok:#3ddc84;--warn:#ffc845;--bad:#ff5c5c;--me:#ffd84d}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px/1.4 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 330px;grid-template-rows:56px 1fr 64px;height:100%}
header{grid-column:1/3;display:flex;align-items:center;gap:18px;padding:0 18px;border-bottom:1px solid var(--line);background:#0b0d11}
header .logo{font:700 18px "Bahnschrift","Segoe UI";color:var(--acc);letter-spacing:.5px}
header .t{font-weight:600;font-size:15px}
header .chips{display:flex;gap:8px;margin-left:auto}
.chip{background:var(--card2);border:1px solid var(--line);padding:4px 10px;border-radius:999px;color:var(--sub);white-space:nowrap}
.chip b{color:var(--txt)}
#mapwrap{position:relative;background:#0a0c0f}
#map{position:absolute;inset:0;background:#0a0c0f}
#fx{position:absolute;inset:0;pointer-events:none;z-index:450}
#tip{position:absolute;z-index:500;pointer-events:none;background:rgba(14,16,20,.92);border:1px solid var(--line);border-radius:8px;padding:6px 9px;display:none;white-space:nowrap}
#tip .n{font-weight:600}#tip .s{color:var(--sub);font-size:12px}
.mapbtns{position:absolute;right:12px;top:12px;z-index:600;display:flex;flex-direction:column;gap:6px}
.mapbtns button,.toggles label{background:rgba(22,26,33,.92);border:1px solid var(--line);color:var(--txt);border-radius:8px;cursor:pointer}
.mapbtns button{width:34px;height:34px;font-size:17px}
.mapbtns button:hover{border-color:var(--acc)}
.toggles{position:absolute;left:12px;top:12px;z-index:600;display:flex;gap:6px;flex-wrap:wrap;max-width:70%}
.toggles label{padding:5px 10px;display:flex;gap:6px;align-items:center;user-select:none;font-size:12px}
.toggles input{accent-color:var(--acc);margin:0}
#follow{position:absolute;left:50%;transform:translateX(-50%);bottom:12px;z-index:600;background:rgba(76,194,255,.15);border:1px solid var(--acc);color:var(--acc);padding:5px 12px;border-radius:999px;display:none;cursor:pointer}
aside{border-left:1px solid var(--line);background:var(--card);display:flex;flex-direction:column;min-height:0}
.tabs{display:flex;border-bottom:1px solid var(--line)}
.tabs button{flex:1;background:none;border:0;color:var(--sub);padding:12px 0;font:600 13px "Segoe UI";cursor:pointer;border-bottom:2px solid transparent}
.tabs button.on{color:var(--txt);border-bottom-color:var(--acc)}
.pane{flex:1;overflow:auto;padding:8px 10px;display:none}
.pane.on{display:block}
.pane::-webkit-scrollbar{width:8px}.pane::-webkit-scrollbar-thumb{background:#2c3240;border-radius:4px}
.team{background:var(--card2);border:1px solid var(--line);border-radius:10px;margin-bottom:6px;overflow:hidden}
.team.mine{border-color:var(--me)}
.team .th{display:flex;align-items:center;gap:8px;padding:6px 10px;color:var(--sub);font-size:12px}
.team .th .sw{width:10px;height:10px;border-radius:50%}
.team .th .rk{margin-left:auto;font-weight:700;color:var(--txt)}
.pl{display:flex;align-items:center;gap:8px;padding:5px 10px;cursor:pointer;border-top:1px solid #20252e}
.pl:hover{background:#232a35}
.pl .st{width:8px;height:8px;border-radius:50%;background:var(--ok);flex:none}
.pl.knock .st{background:var(--warn)}.pl.dead{opacity:.45}.pl.dead .st{background:var(--bad)}
.pl .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pl .k{margin-left:auto;color:var(--sub);font-size:12px}
.pl .bot{font-size:10px;color:var(--sub);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.kf{display:grid;grid-template-columns:44px 1fr;gap:2px 8px;padding:7px 8px;border-bottom:1px solid #20252e;cursor:pointer;border-radius:6px}
.kf:hover{background:#232a35}
.kf .tm{color:var(--sub);font-variant-numeric:tabular-nums}
.kf .who{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kf .wp{grid-column:2;color:var(--sub);font-size:12px}
.kf.mine .who{color:var(--me)}
.kf .hs{color:var(--bad);font-weight:700}
footer{grid-column:1/3;display:flex;align-items:center;gap:14px;padding:0 18px;border-top:1px solid var(--line);background:#0b0d11}
#play{width:44px;height:44px;border-radius:50%;border:0;background:var(--acc);color:#0e1014;font-size:18px;cursor:pointer;flex:none}
#time{font:600 15px "Bahnschrift","Segoe UI";font-variant-numeric:tabular-nums;min-width:120px}
#bar{position:relative;flex:1;height:36px}
#seek{position:absolute;inset:0;width:100%;margin:0;opacity:0;cursor:pointer;z-index:2}
#track{position:absolute;left:0;right:0;top:15px;height:6px;border-radius:3px;background:var(--line)}
#fill{position:absolute;left:0;top:15px;height:6px;border-radius:3px;background:var(--acc);width:0}
#knob{position:absolute;top:10px;width:16px;height:16px;border-radius:50%;background:#fff;margin-left:-8px;box-shadow:0 0 0 4px rgba(76,194,255,.35)}
.tick{position:absolute;top:8px;width:2px;height:20px;border-radius:1px;background:var(--me);opacity:.9}
.tick.die{background:var(--bad);width:3px}
.tick.ph{background:#6f7a8c;height:10px;top:13px;opacity:.6}
#speed{background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:600 13px "Segoe UI"}
#alive{color:var(--sub);white-space:nowrap}#alive b{color:var(--txt)}
.leaflet-container{background:#0a0c0f;outline:0}
.hint{color:var(--sub);font-size:11px;padding:8px 10px;border-top:1px solid var(--line)}
.rgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}
.rc{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.rc .v{font:700 18px "Bahnschrift","Segoe UI"}.rc .l{color:var(--sub);font-size:11px}
.sec{font-weight:700;margin:12px 2px 6px;color:var(--txt)}
.death{background:linear-gradient(135deg,rgba(255,92,92,.14),rgba(255,92,92,.04));border:1px solid rgba(255,92,92,.45);border-radius:10px;padding:10px;margin-bottom:8px}
.death b{color:#ffb0b0}.death button{margin-top:8px;background:none;border:1px solid var(--line);color:var(--acc);border-radius:6px;padding:4px 10px;cursor:pointer;font:600 12px "Segoe UI"}
.tipr{display:flex;gap:8px;padding:7px 8px;border-radius:8px;margin-bottom:4px;background:var(--card2)}
.tipr .i{flex:none;font-weight:700}.tipr.bad .i{color:var(--bad)}.tipr.warn .i{color:var(--warn)}.tipr.info .i{color:var(--acc)}.tipr.good .i{color:var(--ok)}
table.wt{width:100%;border-collapse:collapse;font-size:12px}table.wt td,table.wt th{padding:5px 6px;border-bottom:1px solid #20252e;text-align:right}
table.wt th{color:var(--sub);font-weight:600}table.wt td:first-child,table.wt th:first-child{text-align:left}
#chart{width:100%;height:120px;background:var(--card2);border:1px solid var(--line);border-radius:8px;cursor:pointer;display:block}
.legend{color:var(--sub);font-size:11px;margin:4px 2px 0}.legend i{display:inline-block;width:10px;height:3px;margin:0 4px 2px 8px;vertical-align:middle}
@media (max-width:900px){#app{grid-template-columns:1fr;grid-template-rows:56px 1fr 64px 240px}aside{grid-row:4;border-left:0;border-top:1px solid var(--line)}footer{grid-row:3}}
</style>
</head>
<body>
<div id="app">
  <header>
    <div class="logo">PUBG</div>
    <div class="t" id="title"></div>
    <div class="chips" id="chips"></div>
  </header>
  <div id="mapwrap">
    <div id="map"></div>
    <canvas id="fx"></canvas>
    <div id="tip"></div>
    <div class="toggles">
      <label><input type="checkbox" id="oNames" checked>Tüm isimler</label>
      <label><input type="checkbox" id="oTracer" checked>Atış çizgileri</label>
      <label><input type="checkbox" id="oPath" checked>Rotam</label>
      <label><input type="checkbox" id="oDeaths" checked>Ölüm yerleri</label>
      <label><input type="checkbox" id="oDrops" checked>Kare paket</label>
      <label><input type="checkbox" id="oBots" checked>Botlar</label>
    </div>
    <div class="mapbtns">
      <button id="zin" title="Yakınlaştır">+</button>
      <button id="zout" title="Uzaklaştır">−</button>
      <button id="zfit" title="Tüm harita">⤢</button>
      <button id="zme" title="Beni takip et">◎</button>
    </div>
    <div id="follow"></div>
  </div>
  <aside>
    <div class="tabs"><button class="on" data-p="pRep">Rapor</button><button data-p="pTeams">Takımlar</button><button data-p="pKills">Öldürmeler</button></div>
    <div class="pane on" id="pRep"></div>
    <div class="pane" id="pTeams"></div>
    <div class="pane" id="pKills"></div>
    <div class="hint">Boşluk: oynat/durdur · ←/→: 10 sn · +/−: hız · oyuncuya tıkla: takip et</div>
  </aside>
  <footer>
    <button id="play" title="Oynat (boşluk)">▶</button>
    <div id="time">00:00 / 00:00</div>
    <div id="bar"><div id="track"></div><div id="fill"></div><div id="ticks"></div><div id="knob"></div><input type="range" id="seek" min="0" max="1000" value="0" step="1"></div>
    <select id="speed"><option>1</option><option>5</option><option selected>10</option><option>20</option><option>40</option><option>80</option></select>
    <div id="alive"></div>
  </footer>
</div>
<script>
const D = __DATA__;
const TILES = __TILES__, MAXZ = __MAXZ__, LOWIMG = __LOWIMG__;
const W = 256, B = [[-W, 0], [0, W]];
const ll = (x, y) => L.latLng(-y * W, x * W);
const map = L.map('map', {crs: L.CRS.Simple, minZoom: 0, maxZoom: 8, zoomSnap: 1, zoomDelta: 1, wheelPxPerZoomLevel: 120,
  attributionControl: false, zoomControl: false, zoomAnimation: false, fadeAnimation: false, maxBounds: [[-W * 1.2, -W * .2], [W * .2, W * 1.2]]});
if (TILES) L.tileLayer(TILES, {minZoom: 0, maxNativeZoom: MAXZ, maxZoom: 8, noWrap: true, bounds: B, tileSize: 256}).addTo(map);
else L.imageOverlay(LOWIMG, B).addTo(map);
map.fitBounds(B);

const $ = id => document.getElementById(id);
const fmt = s => { s = Math.max(0, Math.floor(s)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); };
const P = D.players, ids = Object.keys(P);
const teamColor = {};
const hue = t => { let h = (t * 137.508) % 360; if (h > 40 && h < 70) h += 40; return `hsl(${h},80%,60%)`; };
for (const id of ids) { const p = P[id]; if (!(p.team in teamColor)) teamColor[p.team] = p.team === D.myTeam ? getComputedStyle(document.documentElement).getPropertyValue('--me').trim() : hue(p.team); }
const kidx = {}; for (const id of ids) kidx[P[id].name] = id;

// başlık
$('title').textContent = `${D.mapName} · ${D.mode}`;
const me = P[D.me] || {};
$('chips').innerHTML = [`<span class="chip">${D.date}</span>`, D.myRank ? `<span class="chip">Sıra <b>#${D.myRank}</b></span>` : '',
  `<span class="chip">Öldürme <b>${D.myKills}</b></span>`, `<span class="chip">Hasar <b>${Math.round(D.myDamage)}</b></span>`,
  `<span class="chip">${D.teams} takım · ${ids.length} oyuncu</span>`].join('');

// zaman çizelgesi işaretleri
const ticks = [];
for (const k of D.kills) if (P[kidx[k.k]] && P[kidx[k.k]].team === D.myTeam) ticks.push(`<div class="tick" style="left:${k.t / D.dur * 100}%" title="${fmt(k.t)} ${k.k} → ${k.v}"></div>`);
if (me.death != null) ticks.push(`<div class="tick die" style="left:${me.death / D.dur * 100}%" title="${fmt(me.death)} öldün"></div>`);
if (D.report) for (const f of D.report.fights) ticks.push(`<div class="tick ph" style="left:${f[0] / D.dur * 100}%;background:#ffc845;opacity:.5"></div>`);
for (const z of D.phases) ticks.push(`<div class="tick ph" style="left:${z / D.dur * 100}%"></div>`);
$('ticks').innerHTML = ticks.join('');

// konum ara değerleme
function pos(p, t) {
  const a = p.pos; if (!a.length || t < a[0][0]) return null;
  let lo = 0, hi = a.length - 1;
  if (t >= a[hi][0]) return a[hi];
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m][0] <= t) lo = m; else hi = m; }
  const A = a[lo], C = a[hi], f = (t - A[0]) / (C[0] - A[0] || 1);
  return [t, A[1] + (C[1] - A[1]) * f, A[2] + (C[2] - A[2]) * f, A[3]];
}
function zoneAt(t) {
  const z = D.zones; if (!z.length || t < z[0][0]) return null;
  let i = 0; while (i + 1 < z.length && z[i + 1][0] <= t) i++;
  const A = z[i], C = z[i + 1];
  if (!C) return A;
  const f = (t - A[0]) / (C[0] - A[0] || 1), r = A.slice();
  for (let j = 1; j <= 3; j++) r[j] = A[j] + (C[j] - A[j]) * f;  // mavi bölge yumuşak daralır
  return r;
}
const state = (p, t) => p.death != null && t >= p.death ? 'dead' : (p.knocks.some(k => t >= k[0] && t < k[1]) ? 'knock' : 'alive');

// tuval
const cv = $('fx'), cx = cv.getContext('2d');
function sizeCanvas() { const r = $('mapwrap').getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d; cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px'; cx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', () => { sizeCanvas(); draw(); }); sizeCanvas();
const pt = (x, y) => map.latLngToContainerPoint(ll(x, y));
const px = r => map.latLngToContainerPoint(ll(r, 0)).x - map.latLngToContainerPoint(ll(0, 0)).x;

let T = 0, playing = false, followId = null, hoverId = null, shown = [];
const O = id => $(id).checked;
function circle(z, ix, color, fill, width, dash) {
  const r = z[ix + 2]; if (!r) return;
  const c = pt(z[ix], z[ix + 1]), R = px(r);
  cx.beginPath(); cx.arc(c.x, c.y, R, 0, Math.PI * 2);
  if (fill) { cx.fillStyle = fill; cx.fill(); }
  cx.setLineDash(dash || []); cx.lineWidth = width; cx.strokeStyle = color; cx.stroke(); cx.setLineDash([]);
}
function draw() {
  const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
  cx.clearRect(0, 0, w, h);
  const z = zoneAt(T);
  if (z) {
    if (z[3]) {  // mavi bölge dışı karartma
      const c = pt(z[1], z[2]);
      cx.save(); cx.beginPath(); cx.rect(0, 0, w, h); cx.arc(c.x, c.y, px(z[3]), 0, Math.PI * 2, true);
      cx.fillStyle = 'rgba(40,90,255,.16)'; cx.fill('evenodd'); cx.restore();
    }
    circle(z, 1, '#3d7bff', null, 2.5);
    circle(z, 4, '#ffffff', null, 2, [8, 6]);
    circle(z, 7, 'rgba(255,60,60,.9)', 'rgba(255,40,40,.18)', 1.5);
  }
  if (O('oDrops')) for (const d of D.drops) if (d[0] <= T) { const c = pt(d[1], d[2]); cx.fillStyle = '#ff7a2f'; cx.fillRect(c.x - 5, c.y - 5, 10, 10); cx.strokeStyle = '#2a1508'; cx.lineWidth = 1.5; cx.strokeRect(c.x - 5, c.y - 5, 10, 10); }
  if (O('oPath') && P[D.me]) {
    cx.beginPath(); let first = true;
    for (const a of P[D.me].pos) { if (a[0] > T) break; const c = pt(a[1], a[2]); first ? cx.moveTo(c.x, c.y) : cx.lineTo(c.x, c.y); first = false; }
    const cur = pos(P[D.me], T); if (cur && !first) { const c = pt(cur[1], cur[2]); cx.lineTo(c.x, c.y); }
    cx.strokeStyle = 'rgba(255,216,77,.55)'; cx.lineWidth = 2; cx.stroke();
  }
  if (O('oDeaths')) for (const id of ids) { const p = P[id]; if (p.death == null || T < p.death || (p.bot && !O('oBots'))) continue;
    const c = pt(p.dx, p.dy), s = p.team === D.myTeam ? 6 : 4; cx.strokeStyle = p.team === D.myTeam ? '#ff5c5c' : 'rgba(255,255,255,.55)'; cx.lineWidth = 2;
    cx.beginPath(); cx.moveTo(c.x - s, c.y - s); cx.lineTo(c.x + s, c.y + s); cx.moveTo(c.x + s, c.y - s); cx.lineTo(c.x - s, c.y + s); cx.stroke(); }
  if (O('oTracer')) for (const s of D.shots) { if (s[0] > T) break; const age = T - s[0]; if (age > 1.5) continue;
    const a = pt(s[1], s[2]), b = pt(s[3], s[4]); cx.globalAlpha = 1 - age / 1.5; cx.strokeStyle = teamColor[s[5]] || '#fff'; cx.lineWidth = s[5] === D.myTeam ? 2 : 1.3;
    cx.beginPath(); cx.moveTo(a.x, a.y); cx.lineTo(b.x, b.y); cx.stroke(); cx.globalAlpha = 1; }
  shown = [];
  const order = ids.slice().sort((a, b) => (P[a].team === D.myTeam) - (P[b].team === D.myTeam));
  cx.font = '600 11px "Segoe UI"'; cx.textAlign = 'center';
  for (const id of order) {
    const p = P[id]; if (p.bot && !O('oBots')) continue;
    const st = state(p, T); if (st === 'dead') continue;
    const q = pos(p, T); if (!q) continue;
    const c = pt(q[1], q[2]), mine = p.team === D.myTeam, isMe = id === D.me, r = isMe ? 7 : (mine ? 6 : 4.5);
    shown.push([id, c.x, c.y]);
    cx.beginPath(); cx.arc(c.x, c.y, r, 0, Math.PI * 2);
    cx.fillStyle = st === 'knock' ? '#ff5c5c' : teamColor[p.team]; cx.fill();
    cx.lineWidth = isMe ? 2.5 : 1.5; cx.strokeStyle = isMe ? '#fff' : 'rgba(0,0,0,.75)'; cx.stroke();
    if (id === followId || id === hoverId) { cx.beginPath(); cx.arc(c.x, c.y, r + 5, 0, Math.PI * 2); cx.strokeStyle = 'rgba(255,255,255,.8)'; cx.lineWidth = 1.5; cx.stroke(); }
    if (mine || O('oNames') && map.getZoom() >= 2.5 || id === hoverId) {
      cx.lineWidth = 3; cx.strokeStyle = 'rgba(0,0,0,.85)'; cx.strokeText(p.name, c.x, c.y - r - 5);
      cx.fillStyle = mine ? '#ffe9a0' : '#e8eaed'; cx.fillText(p.name, c.x, c.y - r - 5);
    }
  }
}

// yan panel
const teams = {};
for (const id of ids) (teams[P[id].team] = teams[P[id].team] || []).push(id);
const tlist = Object.keys(teams).map(Number).sort((a, b) => (b === D.myTeam) - (a === D.myTeam) || (P[teams[a][0]].rank || 99) - (P[teams[b][0]].rank || 99));
$('pTeams').innerHTML = tlist.map(t => `<div class="team${t === D.myTeam ? ' mine' : ''}"><div class="th"><span class="sw" style="background:${teamColor[t]}"></span>Takım ${t}<span class="rk">${P[teams[t][0]].rank ? '#' + P[teams[t][0]].rank : ''}</span></div>` +
  teams[t].map(id => `<div class="pl" data-id="${id}"><span class="st"></span><span class="nm">${P[id].name}</span>${P[id].bot ? '<span class="bot">BOT</span>' : ''}<span class="k"></span></div>`).join('') + '</div>').join('');
const kfHtml = k => { const mine = P[kidx[k.k]] && P[kidx[k.k]].team === D.myTeam || P[kidx[k.v]] && P[kidx[k.v]].team === D.myTeam;
  return `<div class="kf${mine ? ' mine' : ''}" data-t="${k.t}" data-x="${k.x}" data-y="${k.y}"><span class="tm">${fmt(k.t)}</span><span class="who">${k.k || '—'} ✕ ${k.v}</span><span class="wp">${k.w}${k.d ? ' · ' + k.d + ' m' : ''}${k.hs ? ' · <span class="hs">kafa</span>' : ''}</span></div>`; };
let lastKf = -1, lastSide = 0;
function side() {
  const now = performance.now(); if (now - lastSide < 250) return; lastSide = now;
  for (const el of document.querySelectorAll('.pl')) { const p = P[el.dataset.id], st = state(p, T);
    el.className = 'pl' + (st === 'dead' ? ' dead' : st === 'knock' ? ' knock' : '');
    const k = D.kills.filter(x => x.k === p.name && x.t <= T).length; el.querySelector('.k').textContent = k ? k + ' öldürme' : ''; }
  const n = D.kills.filter(k => k.t <= T).length;
  if (n !== lastKf) { lastKf = n; $('pKills').innerHTML = D.kills.filter(k => k.t <= T).reverse().map(kfHtml).join('') || '<div class="kf"><span></span><span class="who" style="color:var(--sub)">Henüz öldürme yok</span></div>'; }
  const alive = ids.filter(id => state(P[id], T) !== 'dead' && pos(P[id], T)).length;
  $('alive').innerHTML = `Hayatta <b>${alive}</b>`;
}
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => { document.querySelectorAll('.tabs button,.pane').forEach(e => e.classList.remove('on')); b.classList.add('on'); $(b.dataset.p).classList.add('on'); });
$('pTeams').onclick = e => { const el = e.target.closest('.pl'); if (el) setFollow(el.dataset.id); };
$('pKills').onclick = e => { const el = e.target.closest('.kf'); if (!el || !el.dataset.t) return; setFollow(null); seek(+el.dataset.t - 4); map.setView(ll(+el.dataset.x, +el.dataset.y), Math.max(map.getZoom(), 4)); };
function setFollow(id) { followId = id === followId ? null : id; $('follow').style.display = followId ? 'block' : 'none'; if (followId) $('follow').textContent = '◎ ' + P[followId].name + ' takip ediliyor · bırakmak için tıkla'; draw(); }
$('follow').onclick = () => setFollow(null);

// ipucu
$('mapwrap').addEventListener('mousemove', e => {
  const r = $('mapwrap').getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 12;
  for (const s of shown) { const d = Math.hypot(s[1] - mx, s[2] - my); if (d < bd) { bd = d; best = s; } }
  hoverId = best ? best[0] : null;
  const tip = $('tip');
  if (best) { const p = P[best[0]], q = pos(p, T);
    tip.innerHTML = `<div class="n" style="color:${teamColor[p.team]}">${p.name}${p.bot ? ' (bot)' : ''}</div><div class="s">Takım ${p.team} · can ${q ? Math.round(q[3]) : '?'}${p.rank ? ' · sıra #' + p.rank : ''}</div>`;
    tip.style.display = 'block'; tip.style.left = (mx + 14) + 'px'; tip.style.top = (my + 10) + 'px'; } else tip.style.display = 'none';
  if (!playing) draw();
});
$('mapwrap').addEventListener('click', () => { if (hoverId) setFollow(hoverId); });

// maç sonu raporu
const RP = D.report;
function renderReport() {
  const el = $('pRep'); if (!RP) { el.innerHTML = '<div class="tipr info"><span class="i">i</span><span>Rapor yok.</span></div>'; return; }
  const card = (v, l) => `<div class="rc"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  let h = '<div class="rgrid">' + card(RP.rank ? '#' + RP.rank : '—', 'Sıra') + card(RP.kills, 'Öldürme') + card(RP.dmg, 'Hasar') +
    card(fmt(RP.alive), 'Hayatta kalma') + card(RP.acc == null ? '—' : '%' + Math.round(RP.acc), 'İsabet (yaklaşık)') + card(RP.hits ? '%' + RP.hsPct : '—', 'Kafa vuruşu') + '</div>';
  if (RP.death) { const d = RP.death;
    h += `<div class="death">Öldün: <b>${fmt(d.t)}</b> · ${d.by || '—'} · ${d.w}${d.d ? ' · ' + d.d + ' m' : ''}${d.hs ? ' · kafadan' : ''}` +
      `${d.knocked_by && d.knocked_by !== d.by ? `<br><span style="color:var(--sub)">Seni düşüren: ${d.knocked_by}</span>` : ''}` +
      `<br><button onclick="goTo(${d.t - 12}, true)">▶ Ölümünden 12 sn öncesini izle</button></div>`; }
  const icon = {bad: '✖', warn: '⚠', info: 'ℹ'};
  const tips = RP.tips.map(t => `<div class="tipr ${t[0]}"><span class="i">${icon[t[0]]}</span><span>${t[1]}</span></div>`).join('') +
    RP.good.map(g => `<div class="tipr good"><span class="i">✔</span><span>${g}</span></div>`).join('');
  h += '<div class="sec">Bulgular ve öneriler</div>' + (tips || '<div class="tipr good"><span class="i">✔</span><span>Belirgin bir sorun yok.</span></div>');
  const extra = [];
  if (RP.landing != null) extra.push(`İniş: ${RP.landName || 'isimsiz bölge'} · ${fmt(RP.landing)}${RP.enemiesNear ? ` · 150 m içinde ${RP.enemiesNear} düşman` : ''}`);
  if (RP.firstFight != null) extra.push(`İlk çatışma: ${fmt(RP.firstFight)} · toplam ${RP.fights.length} çatışma`);
  extra.push(`Atılan mermi ~${RP.fired} · isabet ${RP.hits} · düşürme ${RP.knocks} · iyileşme ${RP.heals}`);
  extra.push(`Alınan hasar ${RP.dmgTaken}${RP.blueDmg ? ` (mavi bölge ${RP.blueDmg})` : ''}`);
  h += '<div class="sec">Maç özeti</div>' + extra.map(x => `<div class="tipr"><span class="i" style="color:var(--sub)">•</span><span>${x}</span></div>`).join('');
  if (RP.weapons.length) h += '<div class="sec">Silahlar</div><table class="wt"><tr><th>Silah</th><th>İsabet</th><th>Hasar</th><th>Kafa</th></tr>' +
    RP.weapons.map(w => `<tr><td>${w.w}</td><td>${w.hits}</td><td>${Math.round(w.dmg)}</td><td>${w.hs}</td></tr>`).join('') + '</table>';
  const P2 = RP.perf;
  h += '<div class="sec">Bilgisayar performansı (bu maç)</div>';
  if (P2) {
    h += '<div class="rgrid">' + card(P2.avg, 'Ort. FPS') + card(P2.fightFps == null ? '—' : P2.fightFps, 'Çatışmada FPS') + card(P2.st, 'Takılma') +
      card(P2.pingAvg + ' ms', 'Ort. ping') + card(P2.cpuMax ? P2.cpuMax + '°' : '—', 'En sıcak CPU') + card(P2.gpuMax ? P2.gpuMax + '°' : '—', 'En sıcak GPU') + '</div>' +
      '<canvas id="chart"></canvas><div class="legend"><i style="background:#4cc2ff"></i>FPS<i style="background:rgba(255,200,69,.6);height:8px"></i>çatışma<i style="background:#ff5c5c"></i>takılma / ölüm · tıkla: o ana git</div>';
    if (P2.beforeDeath) { const b = P2.beforeDeath;
      h += `<div class="tipr ${b.st >= 2 || b.lossMax >= 5 ? 'bad' : 'info'}" style="margin-top:6px"><span class="i">◷</span><span>Ölümünden önceki 15 sn: en düşük FPS ${b.minFps}, ${b.st} takılma, en yüksek ping ${Math.round(b.pingMax)} ms${b.lossMax ? ', kayıp %' + Math.round(b.lossMax) : ''}</span></div>`; }
  } else h += '<div class="tipr info"><span class="i">ℹ</span><span>Bu maçta program çalışmıyordu ya da eski sürümdü; performans kaydı yok. Sonraki maçlarda FPS, takılma ve ping çatışma ve ölüm anlarıyla eşleştirilecek.</span></div>';
  el.innerHTML = h;
  if (P2) drawChart();
}
function drawChart() {
  const c = $('chart'); if (!c || !c.clientWidth) return;
  const d = devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight; c.width = w * d; c.height = h * d;
  const g = c.getContext('2d'); g.setTransform(d, 0, 0, d, 0, 0);
  const S = RP.perf.series; if (!S.length) return;
  const max = Math.max(...S.map(s => s[1])) * 1.1 || 1, X = t => t / D.dur * w, Y = f => h - 6 - f / max * (h - 16);
  g.fillStyle = 'rgba(255,200,69,.18)'; for (const f of RP.fights) g.fillRect(X(f[0] - 2), 0, Math.max(3, X(f[1] + 2) - X(f[0] - 2)), h);
  g.beginPath(); S.forEach((s, i) => i ? g.lineTo(X(s[0]), Y(s[1])) : g.moveTo(X(s[0]), Y(s[1])));
  g.strokeStyle = '#4cc2ff'; g.lineWidth = 1.5; g.stroke();
  g.fillStyle = '#ff5c5c'; for (const s of S) if (s[2]) g.fillRect(X(s[0]) - 1, h - 10, 2, 8);
  if (RP.death) { g.fillStyle = '#ff5c5c'; g.fillRect(X(RP.death.t) - 1, 0, 2, h); }
  g.fillStyle = 'rgba(255,255,255,.75)'; g.fillRect(X(T) - .5, 0, 1, h);
  g.fillStyle = '#8b93a1'; g.font = '10px Segoe UI'; g.fillText(Math.round(max / 1.1) + ' FPS', 4, 11);
  c.onclick = e => { const r = c.getBoundingClientRect(); seek((e.clientX - r.left) / w * D.dur); };
}
function goTo(t, focusMe) { seek(t); if (focusMe && P[D.me]) { const q = pos(P[D.me], Math.max(t, 0)); if (q) map.setView(ll(q[1], q[2]), Math.max(map.getZoom(), 4)); } }
addEventListener('resize', () => { if (RP && RP.perf) drawChart(); });
// oynatma
const seekEl = $('seek');
function seek(t) { T = Math.max(0, Math.min(D.dur, t)); ui(); draw(); side(); }
let lastChart = 0;
function ui() { const f = T / D.dur; if (RP && RP.perf && performance.now() - lastChart > 300) { lastChart = performance.now(); drawChart(); } seekEl.value = Math.round(f * 1000); $('fill').style.width = f * 100 + '%'; $('knob').style.left = f * 100 + '%'; $('time').textContent = fmt(T) + ' / ' + fmt(D.dur); }
seekEl.oninput = () => seek(seekEl.value / 1000 * D.dur);
$('play').onclick = () => { playing = !playing; if (playing && T >= D.dur) T = 0; $('play').textContent = playing ? '❚❚' : '▶'; };
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (playing) { T += dt * +$('speed').value; if (T >= D.dur) { T = D.dur; playing = false; $('play').textContent = '▶'; } ui(); side(); }
  if (followId) { const q = pos(P[followId], T); if (q) map.panTo(ll(q[1], q[2]), {animate: false}); }
  draw(); requestAnimationFrame(frame);
}
map.on('move zoom', draw);
$('zin').onclick = () => map.zoomIn(); $('zout').onclick = () => map.zoomOut(); $('zfit').onclick = () => { setFollow(null); map.fitBounds(B); };
$('zme').onclick = () => { if (P[D.me]) { setFollow(D.me); map.setZoom(Math.max(map.getZoom(), 4)); } };
for (const id of ['oNames', 'oTracer', 'oPath', 'oDeaths', 'oDrops', 'oBots']) $(id).onchange = draw;
addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  else if (e.key === 'ArrowRight') seek(T + 10); else if (e.key === 'ArrowLeft') seek(T - 10);
  else if (e.key === '+' || e.key === '-') { const s = $('speed'), i = s.selectedIndex + (e.key === '+' ? 1 : -1); s.selectedIndex = Math.max(0, Math.min(s.options.length - 1, i)); }
});
// başlangıç: iniş anına git, benim takımı göster
seek(D.start || 0); side(); renderReport(); requestAnimationFrame(frame);
</script>
</body>
</html>
'''
