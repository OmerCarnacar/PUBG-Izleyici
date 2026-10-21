# Saniyelik performans kaydı + maç sonu koç raporu
import datetime
import glob
import os
import time
from ..config import DATA
from ..hardware import LIM, num
from ..pubg.replay import MAP_INFO, _ts, weapon_names

PERF = os.path.join(DATA, 'performans')


class PerfLog:
    """Oyun sırasında her saniyenin performansı, zaman damgasıyla (gün başına bir dosya, 15 gün saklanır).
    Maç raporu bu kaydı maçın telemetrisindeki anlarla (çatışma, ölüm) eşleştirir."""
    def __init__(self):
        self.f, self.day = None, None
        try:
            os.makedirs(PERF, exist_ok=True)
            cut = time.time() - 15 * 86400
            for fn in glob.glob(os.path.join(PERF, '*.csv')):
                if os.path.getmtime(fn) < cut:
                    os.remove(fn)
        except OSError:
            pass

    def write(self, row):
        try:
            day = time.strftime('%Y%m%d')
            if day != self.day:
                if self.f:
                    self.f.close()
                self.f = open(os.path.join(PERF, day + '.csv'), 'a', encoding='utf-8', buffering=1)
                self.day = day
            self.f.write(','.join('' if x is None else str(x) for x in row) + '\n')
        except OSError:
            pass

    def close(self):
        try:
            if self.f:
                self.f.close()
        except OSError:
            pass


PERF_COLS = ('ts', 'fps', 'low1', 'st', 'ftmax', 'cpu_t', 'cpu', 'core', 'gpu_t', 'gpu', 'ping', 'loss', 'bound')


def perf_rows(t_from, t_to):
    """[t_from, t_to] (epoch sn) arasındaki saniyelik kayıtlar."""
    out, d = [], datetime.date.fromtimestamp(t_from)
    while d <= datetime.date.fromtimestamp(t_to):
        try:
            with open(os.path.join(PERF, d.strftime('%Y%m%d') + '.csv'), encoding='utf-8') as f:
                for ln in f:
                    p = ln.rstrip('\n').split(',')
                    if len(p) < len(PERF_COLS):
                        continue
                    try:
                        ts = float(p[0])
                    except ValueError:
                        continue
                    if t_from <= ts <= t_to:
                        r = {k: (num(v) if k != 'bound' else v) for k, v in zip(PERF_COLS, p)}
                        out.append(r)
        except OSError:
            pass
        d += datetime.timedelta(days=1)
    return out


def coach_report(events, m, data):
    """Maç sonu raporu: maçın olayları + o anki bilgisayar performansı. Bulgular ve öneriler (seviye, metin)."""
    aid = m['aid']
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    me = data['players'].get(aid) or {}
    myteam = data.get('myTeam')
    wn = weapon_names()
    T = lambda e: _ts(e['_D']) - t0
    shots, hits, hs, dmg, dmg_taken, blue_dmg, knocks, heals = {}, 0, 0, 0.0, 0.0, 0.0, 0, 0
    by_w = {}
    fights = []  # benim silahla hasar verdiğim/aldığım anlar
    landing = land_name = None
    death = None
    knocked_by = None
    for e in events:
        typ = e['_T']
        if landing is not None and land_name is None:  # iniş yerinin adı: inişten sonra bende görülen ilk bölge adı
            for f in ('character', 'attacker', 'victim'):
                c = e.get(f)
                if isinstance(c, dict) and c.get('accountId') == aid and c.get('zone'):
                    land_name = c['zone'][0].replace('_', ' ').title()
                    break
        if typ == 'LogWeaponFireCount' and e['character'].get('accountId') == aid:
            shots[e['weaponId']] = max(shots.get(e['weaponId'], 0), e.get('fireCount', 0))
        elif typ == 'LogPlayerTakeDamage':
            a, v = e.get('attacker') or {}, e.get('victim') or {}
            cat, d = e.get('damageTypeCategory', ''), e.get('damage') or 0
            if a.get('accountId') == aid and v.get('teamId') != myteam and cat == 'Damage_Gun':
                hits += 1; dmg += d; fights.append(T(e))
                hs += e.get('damageReason') == 'HeadShot'
                w = wn.get(e.get('damageCauserName'), e.get('damageCauserName', '?'))
                b = by_w.setdefault(w, {'w': w, 'hits': 0, 'dmg': 0.0, 'hs': 0})
                b['hits'] += 1; b['dmg'] += d; b['hs'] += e.get('damageReason') == 'HeadShot'
            elif v.get('accountId') == aid:
                dmg_taken += d
                if cat == 'Damage_BlueZone':
                    blue_dmg += d
                elif cat == 'Damage_Gun':
                    fights.append(T(e))
        elif typ == 'LogPlayerMakeGroggy':
            if (e.get('attacker') or {}).get('accountId') == aid:
                knocks += 1
            if (e.get('victim') or {}).get('accountId') == aid and knocked_by is None:
                knocked_by = (e.get('attacker') or {}).get('name')
        elif typ == 'LogItemUse' and e['character'].get('accountId') == aid and \
                any(x in e['item'].get('itemId', '') for x in ('Heal', 'Boost', 'FirstAid', 'MedKit', 'Bandage')):
            heals += 1
        elif typ == 'LogParachuteLanding' and e['character'].get('accountId') == aid:
            landing = T(e)
        elif typ == 'LogPlayerKillV2' and (e.get('victim') or {}).get('accountId') == aid:
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            cat = info.get('damageTypeCategory', '')
            death = {'t': T(e), 'by': k.get('name') or '', 'w': 'Mavi bölge' if cat == 'Damage_BlueZone' else
                     wn.get(info.get('damageCauserName'), info.get('damageCauserName', '?')),
                     'd': round((info.get('distance') or 0) / 100), 'hs': info.get('damageReason') == 'HeadShot',
                     'veh': bool((e.get('victim') or {}).get('isInVehicle')), 'knocked_by': knocked_by}
    fired = sum(shots.values())
    acc = round(100 * hits / max(fired, hits), 1) if fired or hits else None
    # çatışmaları birleştir (10 sn içindeki vuruşlar aynı çatışma)
    fights.sort()
    fw = []
    for t in fights:
        if fw and t - fw[-1][1] <= 10:
            fw[-1][1] = t
        else:
            fw.append([t, t])
    alive = (death['t'] if death else data['dur'])
    enemies_near = 0
    if landing is not None and me.get('pos'):
        lp = next((a for a in me['pos'] if a[0] >= landing), None)
        if lp:  # iniş anında 150 m içinde düşman sayısı
            size = MAP_INFO.get(m['map'], ('', '', 816000))[2]
            r = 15000 / size
            for i, p in data['players'].items():
                if p['team'] == myteam:
                    continue
                q = next((a for a in p['pos'] if a[0] >= landing), None)
                if q and abs(q[0] - landing) < 20 and (q[1] - lp[1]) ** 2 + (q[2] - lp[2]) ** 2 <= r * r:
                    enemies_near += 1
    rep = {'landing': landing, 'landName': land_name or '', 'enemiesNear': enemies_near, 'firstFight': fw[0][0] if fw else None,
           'fights': fw, 'fired': fired, 'hits': hits, 'acc': acc, 'hs': hs, 'hsPct': round(100 * hs / hits) if hits else 0,
           'dmg': round(m.get('dmg') or dmg), 'gunDmg': round(dmg), 'dmgTaken': round(dmg_taken), 'blueDmg': round(blue_dmg), 'knocks': knocks, 'heals': heals,
           'kills': m.get('kills', 0), 'rank': m.get('rank'), 'alive': round(alive), 'death': death,
           'weapons': sorted(by_w.values(), key=lambda b: -b['dmg'])[:5], 'perf': None, 'tips': [], 'good': []}

    # performans kaydıyla eşleştir
    rows = perf_rows(t0 - 5, t0 + data['dur'] + 5)
    if len(rows) >= 30:
        for r in rows:
            r['t'] = r['ts'] - t0
        fps = [r['fps'] for r in rows if r['fps']]
        avg = sum(fps) / len(fps) if fps else 0

        def win(a, b):
            return [r for r in rows if a <= r['t'] <= b]
        infight = [r for w in fw for r in win(w[0] - 2, w[1] + 2)]
        ff = [r['fps'] for r in infight if r['fps']]
        pd = {'avg': round(avg), 'low1': round(min(r['low1'] or avg for r in rows)), 'st': int(sum(r['st'] or 0 for r in rows)),
              'fightFps': round(sum(ff) / len(ff)) if ff else None, 'fightSt': int(sum(r['st'] or 0 for r in infight)),
              'cpuMax': max((r['cpu_t'] or 0) for r in rows), 'gpuMax': max((r['gpu_t'] or 0) for r in rows),
              'pingAvg': round(sum(r['ping'] or 0 for r in rows) / len(rows)), 'pingMax': max((r['ping'] or 0) for r in rows),
              'lossMax': max((r['loss'] or 0) for r in rows),
              'series': [[round(r['t']), round(r['fps'] or 0), int(r['st'] or 0), round(r['ping'] or 0)] for r in rows[::2]]}
        if death:
            bd = win(death['t'] - 15, death['t'])
            if bd:
                pd['beforeDeath'] = {'minFps': round(min(r['fps'] or 0 for r in bd)), 'st': int(sum(r['st'] or 0 for r in bd)),
                                     'pingMax': max(r['ping'] or 0 for r in bd), 'lossMax': max(r['loss'] or 0 for r in bd),
                                     'cpuT': max(r['cpu_t'] or 0 for r in bd)}
        rep['perf'] = pd

    # öneriler (önce sorunlar, sonra iyi gidenler)
    tip, good = rep['tips'].append, rep['good'].append
    pdd = rep['perf']
    if pdd and death and pdd.get('beforeDeath'):
        b = pdd['beforeDeath']
        if b['st'] >= 2 or (avg and b['minFps'] < avg * 0.6):
            tip(('bad', f"Ölümünden önceki 15 saniyede {b['st']} takılma oldu, en düşük FPS {b['minFps']}. "
                        + ('Sebep işlemci ısınması olabilir ({}°C).'.format(b['cpuT']) if b['cpuT'] >= LIM['hot'] else
                           'Analiz sekmesindeki takılma kaydına bak.')))
        if b['lossMax'] >= 5 or b['pingMax'] >= max(80, pdd['pingAvg'] * 2):
            tip(('bad', f"Ölümünden önce ağ bozuldu: ping {b['pingMax']:.0f} ms" + (f", paket kaybı %{b['lossMax']:.0f}" if b['lossMax'] else '') + ". "
                        'Oyunda geri ışınlanma ve gecikmeli vuruş yapar.'))
    if pdd and pdd['fightFps'] and pdd['avg'] and pdd['fightFps'] < pdd['avg'] * 0.75:
        tip(('warn', f"Çatışmalarda FPS ortalaması {pdd['fightFps']}, maç ortalaması {pdd['avg']}. Duman ve patlamalar FPS'yi "
                     "düşürüyor: Efektler'i Çok Düşük tut."))
    if pdd and pdd['fightSt'] >= 3:
        tip(('warn', f"Çatışma anlarında toplam {pdd['fightSt']} takılma oldu."))
    if rep['blueDmg'] >= 15:
        tip(('warn', f"Mavi bölgeden {rep['blueDmg']} hasar aldın. Bir sonraki çemberin yerini erken düşün, araç bul."))
    if death and landing is not None and death['t'] - landing < 180:
        tip(('warn', f"İnişten {death['t'] - landing:.0f} saniye sonra öldün" +
             (f" ({rep['enemiesNear']} düşman 150 m içine indi)" if rep['enemiesNear'] else '') +
             '. Kalabalık inişlerde önce silah bulmaya odaklan ya da daha sakin bir yere in.'))
    elif rep['enemiesNear'] >= 4:
        tip(('info', f"İnişte 150 m içinde {rep['enemiesNear']} düşman vardı (sıcak iniş)."))
    if death and death['d'] >= 150 and death['w'] != 'Mavi bölge':
        tip(('info', f"{death['d']} m'den vuruldun ({death['w']}). Açık alanda koşarken siper ya da duman kullan."))
    if death and death['veh']:
        tip(('info', 'Araçtayken öldün: araçlar uzaktan kolay hedef olur, çatışma bölgesine yaklaşınca in.'))
    if rep['acc'] is not None and rep['fired'] >= 40 and rep['acc'] < 15:
        tip(('warn', f"İsabet oranın yaklaşık %{rep['acc']:.0f} ({rep['fired']} mermi). Uzun mesafede tek atış ya da kısa "
                     "seri atış dene; Eğitim Modu'nda sekme kontrolü çalış."))
    if not fw and death:
        tip(('warn', 'Ölmeden önce hiç hasar veremedin: düşmanı ilk sen gör. Ses ayarların için Takım Sesi ve Ayar Kontrolü\'ne bak.'))
    if rep['kills'] >= 3:
        good(f"{rep['kills']} öldürme, {rep['dmg']} hasar.")
    if rep['acc'] is not None and rep['fired'] >= 40 and rep['acc'] >= 30:
        good(f"İsabet oranın yüksek: yaklaşık %{rep['acc']:.0f}.")
    if rep['hits'] >= 10 and rep['hsPct'] >= 20:
        good(f"Kafa vuruşu oranın %{rep['hsPct']}.")
    if rep['rank'] and rep['rank'] <= 10:
        good(f"İlk 10'a girdin (#{rep['rank']}).")
    if pdd and pdd['st'] == 0:
        good(f"Maç boyunca hiç takılma olmadı (ortalama {pdd['avg']} FPS).")
    if not pdd:
        tip(('info', 'Bu maçın performans kaydı yok (program kapalıydı ya da eski sürümdü). '
                     'Sonraki maçlarda FPS, takılma ve ping çatışma/ölüm anlarıyla eşleştirilecek.'))
    return rep
