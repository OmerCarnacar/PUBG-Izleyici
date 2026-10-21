# PUBG resmi API (hesap istatistikleri)
import json
import os
import re
import urllib.request, urllib.parse, urllib.error
from ..config import DATA
from ..winutil import INI, read_ini
from ..hardware import num

PUBG_API = 'https://api.pubg.com/shards/steam'
HIST = os.path.join(DATA, 'gecmis.json')
MAPS = {'Baltic_Main': 'Erangel', 'Erangel_Main': 'Erangel', 'Desert_Main': 'Miramar', 'Savage_Main': 'Sanhok',
        'DihorOtok_Main': 'Vikendi', 'Summerland_Main': 'Karakin', 'Tiger_Main': 'Taego', 'Kiki_Main': 'Deston',
        'Chimera_Main': 'Paramo', 'Heaven_Main': 'Haven', 'Neon_Main': 'Rondo', 'Range_Main': 'Camp Jackal'}
MODES = [('squad-fpp', 'Squad FPP'), ('squad', 'Squad TPP'), ('duo-fpp', 'Duo FPP'), ('duo', 'Duo TPP'),
         ('solo-fpp', 'Solo FPP'), ('solo', 'Solo TPP')]


def pubg_get(path, key):
    req = urllib.request.Request(PUBG_API + path, headers={'Authorization': 'Bearer ' + key,
                                                           'Accept': 'application/vnd.api+json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def account_id_from_ini():
    try:
        with open(INI, encoding='utf-8', errors='ignore') as f:
            m = re.search(r'account\.[0-9a-f]{32}', f.read())
        return m.group(0) if m else None
    except OSError:
        return None


def fetch_account(key, name=''):
    if name:
        pl = pubg_get('/players?filter[playerNames]=' + urllib.parse.quote(name), key)['data'][0]
    else:
        aid = account_id_from_ini()
        if not aid:
            raise ValueError('Hesap kimliği bulunamadı, oyuncu adını yaz.')
        pl = pubg_get('/players/' + aid, key)['data']
    aid, nm = pl['id'], pl['attributes']['name']
    cur = next((x['id'] for x in pubg_get('/seasons', key)['data'] if x['attributes'].get('isCurrentSeason')), None)
    life = pubg_get(f'/players/{aid}/seasons/lifetime', key)['data']['attributes']['gameModeStats']
    seas = pubg_get(f'/players/{aid}/seasons/{cur}', key)['data']['attributes']['gameModeStats'] if cur else {}
    try:
        ranked = pubg_get(f'/players/{aid}/seasons/{cur}/ranked', key)['data']['attributes']['rankedGameModeStats'] if cur else {}
    except Exception:
        ranked = {}
    matches = []
    for m in [x['id'] for x in pl.get('relationships', {}).get('matches', {}).get('data', [])][:10]:
        try:
            d = pubg_get('/matches/' + m, key)
        except Exception:
            continue
        a = d['data']['attributes']
        me = next((x['attributes']['stats'] for x in d.get('included', [])
                   if x.get('type') == 'participant' and x['attributes']['stats'].get('playerId') == aid), None)
        if me:
            matches.append({'map': MAPS.get(a.get('mapName'), a.get('mapName')), 'mode': a.get('gameMode'),
                            'date': a.get('createdAt', '')[:16].replace('T', ' '), 'place': me.get('winPlace'),
                            'kills': me.get('kills', 0), 'dmg': me.get('damageDealt', 0), 'hs': me.get('headshotKills', 0),
                            'time': me.get('timeSurvived', 0), 'type': a.get('matchType', '')})
    return {'name': nm, 'id': aid, 'season': cur, 'life': life, 'seas': seas, 'ranked': ranked, 'matches': matches}


def load_hist():
    try:
        with open(HIST, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_hist(h):
    try:
        with open(HIST, 'w', encoding='utf-8') as f:
            json.dump(h[-200:], f, ensure_ascii=False)
    except OSError:
        pass


def gfx_snapshot():
    d = read_ini() or {}
    short = {'sg.ViewDistanceQuality': 'Görüş', 'sg.ShadowQuality': 'Gölge', 'sg.PostProcessQuality': 'İşlem',
             'sg.EffectsQuality': 'Efekt', 'sg.FoliageQuality': 'Yeşil', 'sg.TextureQuality': 'Doku',
             'sg.AntiAliasingQuality': 'AA'}
    ab = {0: 'ÇD', 1: 'D', 2: 'O', 3: 'Y', 4: 'U'}
    parts = [f"{v} {ab.get(int(num(d.get(k), -1)), '?')}" for k, v in short.items() if k in d]
    api = d.get('GraphicsAPI', 'DX11')
    return ' '.join(parts) + f' · {api}'
