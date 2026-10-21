# İniş ve ölüm ısı haritası (son maçlar, resmî PUBG API)
import json
import os
from ..config import DATA
from ..pubg.replay import MAP_INFO, REPLAYS, _ts, http_bytes, map_low, map_tiles, match_summary, recent_matches, weapon_names

HEATDIR = os.path.join(DATA, 'isi')


def heat_point(m, events):
    """Bir maçtan ısı haritası için gereken küçük özet: iniş yeri, ölüm yeri, sonuç. Koordinatlar 0-1."""
    aid = m['aid']
    size = MAP_INFO.get(m['map'], ('', '', 816000))[2]
    t0 = _ts(next(e['_D'] for e in events if e['_T'] == 'LogMatchStart'))
    land = death = None
    fights = []
    for e in events:
        typ = e['_T']
        if typ == 'LogParachuteLanding' and land is None and e['character'].get('accountId') == aid:
            loc = e['character']['location']
            land = [round(loc['x'] / size, 5), round(loc['y'] / size, 5), round(_ts(e['_D']) - t0)]
        elif typ == 'LogPlayerKillV2' and (e.get('victim') or {}).get('accountId') == aid:
            loc = e['victim']['location']
            k = e.get('finisher') or e.get('killer') or {}
            info = e.get('finishDamageInfo') or e.get('killerDamageInfo') or {}
            death = [round(loc['x'] / size, 5), round(loc['y'] / size, 5), round(_ts(e['_D']) - t0),
                     k.get('name') or '', 'Mavi bölge' if info.get('damageTypeCategory') == 'Damage_BlueZone' else
                     weapon_names().get(info.get('damageCauserName'), info.get('damageCauserName') or '')]
        elif typ == 'LogPlayerTakeDamage' and e.get('damageTypeCategory') == 'Damage_Gun':
            a, v = e.get('attacker') or {}, e.get('victim') or {}
            me_ = a if a.get('accountId') == aid else (v if v.get('accountId') == aid else None)
            if me_ and me_.get('location'):
                fights.append([round(me_['location']['x'] / size, 4), round(me_['location']['y'] / size, 4)])
    return {'id': m['id'], 'map': m['map'], 'mode': m['mode'], 'type': m['type'], 'date': m['date'], 'rank': m.get('rank'),
            'kills': m.get('kills', 0), 'dmg': round(m.get('dmg') or 0), 'dur': m.get('dur', 0), 'land': land, 'death': death,
            'fights': fights[::3][:60]}


def heat_collect(key, name='', limit=50, progress=None):
    """Son maçların özetleri. Her maç bir kez indirilip önbelleğe alınır; sonraki açılışta sadece yeni maçlar indirilir."""
    pr = progress or (lambda txt, f=None: None)
    os.makedirs(HEATDIR, exist_ok=True)
    aid, nm, ids = recent_matches(key, name, limit)
    out = []
    for i, mid in enumerate(ids):
        pth = os.path.join(HEATDIR, mid + '.json')
        try:
            with open(pth, encoding='utf-8') as f:
                hp = json.load(f)
        except Exception:
            hp = None
        if hp is None:
            pr(f'Maç {i + 1}/{len(ids)} indiriliyor…', i / max(1, len(ids)))
            try:
                m = match_summary(mid, key, aid)
                if not m.get('tel') or m['map'] not in MAP_INFO or m['map'] == 'Range_Main' or m['mode'] == 'tdm':
                    hp = {'id': mid, 'skip': True}
                else:
                    hp = heat_point(m, json.loads(http_bytes(m['tel'], 120)))
                with open(pth, 'w', encoding='utf-8') as f:
                    json.dump(hp, f)
            except Exception:
                continue
        if not hp.get('skip'):
            out.append(hp)
    return nm, out


def heat_areas(points, cell=0.06):
    """İniş yerlerini ızgara hücrelerine (8 km haritada ~500 m) toplar; her bölge için ortalama sıra, hayatta kalma,
    erken ölüm oranı. Önerilerde en az 2 iniş olan bölgeler kullanılır."""
    cells = {}
    for p in points:
        if not p.get('land'):
            continue
        x, y = p['land'][0], p['land'][1]
        key = (int(x / cell), int(y / cell))
        c = cells.setdefault(key, {'n': 0, 'rank': 0, 'alive': 0, 'early': 0, 'kills': 0, 'top10': 0, 'xs': 0, 'ys': 0})
        alive = (p['death'][2] - p['land'][2]) if p.get('death') else max(0, p['dur'] - p['land'][2])
        c['n'] += 1; c['rank'] += p['rank'] or 50; c['alive'] += alive; c['kills'] += p['kills']
        c['early'] += 1 if p.get('death') and alive < 180 else 0
        c['top10'] += 1 if p['rank'] and p['rank'] <= 10 else 0
        c['xs'] += x; c['ys'] += y
    out = []
    for c in cells.values():
        n = c['n']
        out.append({'x': round(c['xs'] / n, 4), 'y': round(c['ys'] / n, 4), 'n': n, 'rank': round(c['rank'] / n, 1),
                    'alive': round(c['alive'] / n), 'early': round(100 * c['early'] / n), 'kills': round(c['kills'] / n, 1),
                    'top10': round(100 * c['top10'] / n)})
    return out


def build_heatmap(key, name='', progress=None):
    pr = progress or (lambda txt, f=None: None)
    nm, pts = heat_collect(key, name, 50, pr)
    if not pts:
        raise ValueError('Son 14 günde ısı haritası için uygun maç yok.')
    maps = {}
    for p in pts:
        maps.setdefault(p['map'], []).append(p)
    pr('Haritalar hazırlanıyor…', 0.95)
    data = {'name': nm, 'maps': []}
    from pathlib import Path
    for raw, lst in sorted(maps.items(), key=lambda kv: -len(kv[1])):
        mname, img, size = MAP_INFO[raw]
        low = map_low(img)
        tiles, maxz = map_tiles(img)
        ranks = [p['rank'] for p in lst if p['rank']]
        data['maps'].append({'raw': raw, 'name': mname, 'n': len(lst), 'low': Path(low).as_uri(),
                             'tiles': (Path(tiles).as_uri() + '/{z}/{x}/{y}.jpg') if tiles else None, 'maxz': maxz,
                             'km': size / 100000, 'avgRank': round(sum(ranks) / len(ranks), 1) if ranks else None,
                             'top10': round(100 * sum(1 for r in ranks if r <= 10) / len(ranks)) if ranks else 0,
                             'kills': round(sum(p['kills'] for p in lst) / len(lst), 1), 'points': lst,
                             'areas': heat_areas(lst)})
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = os.path.join(REPLAYS, 'isi_haritasi.html')
    os.makedirs(REPLAYS, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(HEAT_HTML.replace('__DATA__', js))
    pr('Hazır', 1)
    return out


# Isı haritası sayfası: Leaflet + tek tuval katmanı
HEAT_HTML = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>İniş ve Ölüm Haritası · PUBG İzleyici</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#0e1014;--card:#161a21;--card2:#1d222b;--line:#262b36;--txt:#e8eaed;--sub:#8b93a1;--acc:#4cc2ff;--ok:#3ddc84;--warn:#ffc845;--bad:#ff5c5c}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px/1.4 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 340px;grid-template-rows:60px 1fr;height:100%}
header{grid-column:1/3;display:flex;align-items:center;gap:16px;padding:0 18px;border-bottom:1px solid var(--line);background:#0b0d11}
header .logo{font:700 18px "Bahnschrift","Segoe UI";color:var(--acc)}
header .t{font-weight:600;font-size:15px;white-space:nowrap}
#maps{display:flex;gap:6px;margin-left:auto;overflow-x:auto}
#maps button{background:var(--card2);border:1px solid var(--line);color:var(--sub);border-radius:999px;padding:6px 12px;cursor:pointer;font:600 12px "Segoe UI";white-space:nowrap}
#maps button.on{background:var(--acc);border-color:var(--acc);color:#0e1014}
#mapwrap{position:relative;background:#0a0c0f}
#map{position:absolute;inset:0;background:#0a0c0f}
#fx{position:absolute;inset:0;pointer-events:none;z-index:450}
#tip{position:absolute;z-index:500;pointer-events:none;background:rgba(14,16,20,.94);border:1px solid var(--line);border-radius:8px;padding:7px 10px;display:none;max-width:280px}
#tip b{color:var(--txt)}#tip .s{color:var(--sub);font-size:12px}
.layers{position:absolute;left:12px;top:12px;z-index:600;display:flex;gap:6px;flex-wrap:wrap}
.layers label{background:rgba(22,26,33,.92);border:1px solid var(--line);border-radius:8px;padding:5px 10px;display:flex;gap:6px;align-items:center;cursor:pointer;user-select:none;font-size:12px}
.layers input{accent-color:var(--acc);margin:0}
.legend{position:absolute;left:12px;bottom:12px;z-index:600;background:rgba(22,26,33,.92);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:12px;color:var(--sub)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 10px;vertical-align:-1px}
aside{border-left:1px solid var(--line);background:var(--card);overflow:auto;padding:12px}
aside::-webkit-scrollbar{width:8px}aside::-webkit-scrollbar-thumb{background:#2c3240;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:12px}
.rc{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.rc .v{font:700 20px "Bahnschrift","Segoe UI"}.rc .l{color:var(--sub);font-size:11px}
.sec{font-weight:700;margin:14px 2px 6px}
.area{display:grid;grid-template-columns:30px 1fr;gap:2px 8px;background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin-bottom:6px;cursor:pointer}
.area:hover{border-color:var(--acc)}
.area .no{grid-row:1/3;font:700 18px "Bahnschrift";align-self:center;text-align:center}
.area.good .no{color:var(--ok)}.area.bad .no{color:var(--bad)}
.area .d{color:var(--sub);font-size:12px}
.mt{display:grid;grid-template-columns:44px 1fr auto;gap:8px;padding:6px 8px;border-bottom:1px solid #20252e;cursor:pointer;border-radius:6px}
.mt:hover{background:#232a35}.mt .r{font:700 14px "Bahnschrift"}.mt .s{color:var(--sub);font-size:12px}
.note{color:var(--sub);font-size:12px;background:var(--card2);border-radius:8px;padding:8px 10px}
.leaflet-container{background:#0a0c0f;outline:0}
</style>
</head>
<body>
<div id="app">
  <header><div class="logo">PUBG</div><div class="t" id="title"></div><div id="maps"></div></header>
  <div id="mapwrap">
    <div id="map"></div><canvas id="fx"></canvas><div id="tip"></div>
    <div class="layers">
      <label><input type="checkbox" id="lHeat" checked>Isı</label>
      <label><input type="checkbox" id="lLand" checked>İnişler</label>
      <label><input type="checkbox" id="lDeath" checked>Ölümler</label>
      <label><input type="checkbox" id="lFight">Çatışmalar</label>
      <label><input type="checkbox" id="lLine">İniş → ölüm</label>
      <label><input type="checkbox" id="lArea" checked>Bölgeler</label>
    </div>
    <div class="legend">İniş sonucu:<i style="background:#3ddc84"></i>ilk 10<i style="background:#ffc845"></i>orta<i style="background:#ff8a3d"></i>erken elendin<i style="background:#ff5c5c"></i>ilk 3 dk'da öldün · ✕ ölüm yeri</div>
  </div>
  <aside id="side"></aside>
</div>
<script>
const D = __DATA__;
const W = 256, B = [[-W, 0], [0, W]], ll = (x, y) => L.latLng(-y * W, x * W);
const $ = id => document.getElementById(id);
const when = d => { const t = new Date(d); return isNaN(t) ? d.slice(5, 16) : t.toLocaleString('tr-TR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}); };
const fmt = s => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const map = L.map('map', {crs: L.CRS.Simple, minZoom: 0, maxZoom: 7, zoomSnap: 1, attributionControl: false, zoomControl: false, zoomAnimation: false, fadeAnimation: false});
L.control.zoom({position: 'topright'}).addTo(map);
let base = null, M = null, hover = null, shown = [];
$('title').textContent = `İniş ve ölüm haritası · ${D.name}`;
$('maps').innerHTML = D.maps.map((m, i) => `<button data-i="${i}">${m.name} · ${m.n}</button>`).join('');
$('maps').onclick = e => { const b = e.target.closest('button'); if (b) pick(+b.dataset.i); };
const alive = p => p.land ? ((p.death ? p.death[2] : p.dur) - p.land[2]) : 0;
const outcome = p => p.rank && p.rank <= 10 ? '#3ddc84' : (p.death && alive(p) < 180 ? '#ff5c5c' : (p.rank && p.rank > 40 ? '#ff8a3d' : '#ffc845'));
function pick(i) {
  M = D.maps[i];
  document.querySelectorAll('#maps button').forEach((b, j) => b.classList.toggle('on', j === i));
  if (base) map.removeLayer(base);
  base = M.tiles ? L.tileLayer(M.tiles, {minZoom: 0, maxNativeZoom: M.maxz, maxZoom: 7, noWrap: true, bounds: B}) : L.imageOverlay(M.low, B);
  base.addTo(map); map.fitBounds(B); side(); draw();
}
function side() {
  const card = (v, l) => `<div class="rc"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  let h = '<div class="grid">' + card(M.n, 'Maç') + card(M.avgRank ?? '—', 'Ortalama sıra') + card('%' + M.top10, 'İlk 10 oranı') + card(M.kills, 'Maç başı öldürme') + '</div>';
  const ok = M.areas.filter(a => a.n >= 2);
  const best = ok.slice().sort((a, b) => b.top10 - a.top10 || a.rank - b.rank).slice(0, 4);
  const worst = ok.slice().sort((a, b) => b.early - a.early || b.rank - a.rank).filter(a => a.early >= 50 || a.rank > 40).slice(0, 4);
  const area = (a, cls, i) => `<div class="area ${cls}" data-x="${a.x}" data-y="${a.y}"><span class="no">${i + 1}</span>` +
    `<span>${a.n} iniş · ortalama sıra <b>#${a.rank}</b> · ilk 10 %${a.top10}</span>` +
    `<span class="d">hayatta kalma ort. ${fmt(a.alive)} · erken ölüm %${a.early} · ${a.kills} öldürme</span></div>`;
  h += '<div class="sec">En iyi iniş bölgelerin</div>' + (best.length ? best.map((a, i) => area(a, 'good', i)).join('') :
    '<div class="note">Öneri için aynı bölgeye en az 2 kez inmiş olman gerekiyor. Bu haritada daha fazla oynadıkça dolacak.</div>');
  if (worst.length) h += '<div class="sec">Kaçınman gereken bölgeler</div>' + worst.map((a, i) => area(a, 'bad', i)).join('');
  const early = M.points.filter(p => p.death && p.land && alive(p) < 180).length;
  if (early) h += `<div class="note" style="margin-top:8px">${M.n} maçın ${early} tanesinde inişten sonraki 3 dakikada öldün. Bu haritada daha sakin inişler sıralamanı yükseltebilir.</div>`;
  h += '<div class="sec">Maçlar</div>' + M.points.slice().sort((a, b) => b.date.localeCompare(a.date)).map(p =>
    `<div class="mt" data-id="${p.id}"><span class="r" style="color:${outcome(p)}">#${p.rank || '?'}</span><span>${when(p.date)}<br>` +
    `<span class="s">${p.kills} öldürme · ${p.dmg} hasar${p.death ? ' · ' + (p.death[3] || '—') + ' (' + p.death[4] + ')' : ''}</span></span>` +
    `<span class="s">${p.land ? fmt(alive(p)) : ''}</span></div>`).join('');
  $('side').innerHTML = h;
}
$('side').onclick = e => {
  const a = e.target.closest('.area'); if (a) { map.setView(ll(+a.dataset.x, +a.dataset.y), 4); return; }
  const m = e.target.closest('.mt'); if (m) { const p = M.points.find(q => q.id === m.dataset.id); if (p && p.land) map.setView(ll(p.land[0], p.land[1]), 4); hover = p; draw(); }
};
const cv = $('fx'), cx = cv.getContext('2d');
function size() { const r = $('mapwrap').getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d; cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px'; cx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', () => { size(); draw(); }); size();
const pt = (x, y) => map.latLngToContainerPoint(ll(x, y));
const pxR = r => pt(r, 0).x - pt(0, 0).x;
const O = id => $(id).checked;
function heat(points, color) {
  const r = Math.max(14, pxR(0.025));
  for (const q of points) { const c = pt(q[0], q[1]); const g = cx.createRadialGradient(c.x, c.y, 0, c.x, c.y, r);
    g.addColorStop(0, color.replace('A', '.45')); g.addColorStop(1, color.replace('A', '0')); cx.fillStyle = g; cx.beginPath(); cx.arc(c.x, c.y, r, 0, 7); cx.fill(); }
}
function draw() {
  if (!M) return;
  const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
  cx.clearRect(0, 0, w, h); shown = [];
  if (O('lHeat')) {
    cx.globalCompositeOperation = 'lighter';
    if (O('lLand')) heat(M.points.filter(p => p.land).map(p => p.land), 'rgba(76,194,255,A)');
    if (O('lDeath')) heat(M.points.filter(p => p.death).map(p => p.death), 'rgba(255,92,92,A)');
    cx.globalCompositeOperation = 'source-over';
  }
  if (O('lFight')) { cx.fillStyle = 'rgba(255,200,69,.55)'; for (const p of M.points) for (const f of p.fights || []) { const c = pt(f[0], f[1]); cx.fillRect(c.x - 1.5, c.y - 1.5, 3, 3); } }
  if (O('lArea')) for (const a of M.areas) if (a.n >= 2) { const c = pt(a.x, a.y), R = Math.max(18, pxR(0.03));
    cx.beginPath(); cx.arc(c.x, c.y, R, 0, 7); cx.setLineDash([4, 4]); cx.strokeStyle = a.top10 >= 50 ? 'rgba(61,220,132,.9)' : (a.early >= 50 ? 'rgba(255,92,92,.9)' : 'rgba(255,255,255,.5)'); cx.lineWidth = 1.5; cx.stroke(); cx.setLineDash([]);
    cx.font = '600 11px "Segoe UI"'; cx.textAlign = 'center'; cx.lineWidth = 3; cx.strokeStyle = 'rgba(0,0,0,.85)'; const t = `${a.n} iniş · #${a.rank}`; cx.strokeText(t, c.x, c.y - R - 4); cx.fillStyle = '#fff'; cx.fillText(t, c.x, c.y - R - 4); }
  for (const p of M.points) {
    if (O('lLine') && p.land && p.death) { const a = pt(p.land[0], p.land[1]), b = pt(p.death[0], p.death[1]); cx.strokeStyle = 'rgba(255,255,255,.35)'; cx.lineWidth = 1; cx.beginPath(); cx.moveTo(a.x, a.y); cx.lineTo(b.x, b.y); cx.stroke(); }
    if (O('lDeath') && p.death) { const c = pt(p.death[0], p.death[1]), s = p === hover ? 7 : 5; cx.strokeStyle = '#ff5c5c'; cx.lineWidth = 2.2;
      cx.beginPath(); cx.moveTo(c.x - s, c.y - s); cx.lineTo(c.x + s, c.y + s); cx.moveTo(c.x + s, c.y - s); cx.lineTo(c.x - s, c.y + s); cx.stroke(); shown.push([p, c.x, c.y, 'death']); }
    if (O('lLand') && p.land) { const c = pt(p.land[0], p.land[1]), r = p === hover ? 8 : 6; cx.beginPath(); cx.arc(c.x, c.y, r, 0, 7); cx.fillStyle = outcome(p); cx.fill();
      cx.lineWidth = p === hover ? 2.5 : 1.5; cx.strokeStyle = p === hover ? '#fff' : 'rgba(0,0,0,.8)'; cx.stroke(); shown.push([p, c.x, c.y, 'land']); }
  }
}
map.on('move zoom', draw);
for (const id of ['lHeat', 'lLand', 'lDeath', 'lFight', 'lLine', 'lArea']) $(id).onchange = draw;
$('mapwrap').addEventListener('mousemove', e => {
  const r = $('mapwrap').getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 10; for (const s of shown) { const d = Math.hypot(s[1] - mx, s[2] - my); if (d < bd) { bd = d; best = s; } }
  const tip = $('tip');
  if (!best) { tip.style.display = 'none'; if (hover) { hover = null; draw(); } return; }
  const p = best[0]; hover = p;
  tip.innerHTML = `<b>${best[3] === 'land' ? 'İniş' : 'Ölüm'}</b> · ${when(p.date)}<div class="s">Sıra #${p.rank || '?'} · ${p.kills} öldürme · ${p.dmg} hasar · hayatta ${fmt(alive(p))}` +
    (p.death ? `<br>Seni öldüren: ${p.death[3] || '—'} (${p.death[4]})` : '<br>Ölmedin') + '</div>';
  tip.style.display = 'block'; tip.style.left = (mx + 14) + 'px'; tip.style.top = (my + 10) + 'px'; draw();
});
pick(0);
</script>
</body>
</html>
'''
