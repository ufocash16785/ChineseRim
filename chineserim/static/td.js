/* 俯視地圖前端：大地圖行走、地點地圖、NPC 互動、遭遇戰與仙劍式回合制戰鬥。伺服器（Session）負責所有規則。 */
const TD = (() => {
  const TS = 32, VW = 960, VH = 540;
  const $ = id => document.getElementById(id), cv = $('c'), g = cv.getContext('2d');
  const ECOL = {"金": "#e0e0e0", "木": "#6c6", "水": "#48c", "火": "#e64", "土": "#ca6", "雷": "#dd4", "冰": "#8ef", "風": "#9d9"};
  const EL = ["金", "木", "水", "火", "土", "雷", "冰", "風"];
  let S = null, MAP = null, mapId = null;
  const maps = {};
  const hero = {x: 0, y: 0, dir: 'd', moving: false, inv: 0};
  const keys = {};
  let trail = [], ents = [], solid = [], shoreMask = null, busy = false, now = 0, last = performance.now();
  let askOpen = false, cool = {}, exitCool = 0, regionPending = false, syncT = 0, dist = 0, lastPos = null;
  let codexOpen = false, codexTab = 'beast', compOpen = false, bagOpen = false, walk = null, lastCam = {x: 0, y: 0}, stuckT = 0;
  let lastTp = null, toastT = 0, lastLog = '', bannerT = 0, lastRegion = null, minimapBase = null, uiKey = '';
  let bt = {target: 0, anim: [], hero: null, prev: null, fx: [], shake: {}, heroAnim: null, over: false};
  const rnd = (a, b = 0) => { let h = (a * 73856093) ^ (b * 19349663); h = (h ^ (h >>> 13)) >>> 0; return (h % 1000) / 1000; };
  const hs = (x, y) => (((x * 73856093) ^ (y * 19349663)) >>> 0);
  const toast = (t, ms = 3200) => { $('toast').textContent = t; toastT = ms; };
  const err = t => { $('err').style.display = 'block'; $('err').textContent = t; };

  // ------------------------------------------------ 伺服器溝通
  async function load() {
    try { S = await (await fetch('/state')).json(); $('err').style.display = 'none'; } catch (e) { err('連不上伺服器：' + e); return; }
    if (S.map_id !== mapId) await setMap(S.map_id);
    if (!S.battle) bt = null; else if (!bt) bt = {target: 0, fx: [], shake: {}, heroAnim: null, prev: null, over: false, ids: [], t0: now};
    if (S.tp !== lastTp) { walk = null; lastTp = S.tp; hero.x = S.pos[0] * TS; hero.y = S.pos[1] * TS; hero.dir = 'd'; lastPos = null; exitCool = 1.2; ents.forEach(e => { if (e.k === 'dock') e.asked = true; }); }
    const l = S.log[S.log.length - 1] || '';
    if (l !== lastLog) { lastLog = l; toast(l); }
    if (S.region !== lastRegion) { if (lastRegion !== null && MAP.kind === 'world') banner(S.region_name); lastRegion = S.region; }
    ui();
  }
  async function post(path, params = {}) {
    busy = true;
    try { await fetch('/' + path + '?' + new URLSearchParams(params), {method: 'POST'}); await load(); } finally { busy = false; }
  }
  const act = c => post('act', {c});
  async function setMap(id) {
    if (!maps[id]) maps[id] = await (await fetch('/mapdata?id=' + encodeURIComponent(id))).json();
    MAP = maps[id]; mapId = id;
    solid = MAP.solid;
    ents = MAP.entities.map(e => Object.assign({}, e, {hx: (e.x + .5) * TS, hy: (e.y + .9) * TS, px: (e.x + .5) * TS, py: (e.y + .9) * TS, dir: 1, t: Math.random() * 3, asked: false}));
    shoreMask = null;
    if (MAP.kind === 'world') buildWorldCaches();
    cool = {}; regionPending = false; trail = [];
    if (MAP.kind === 'loc') banner(MAP.name);
  }
  function banner(t) { $('banner').textContent = t; $('banner').style.opacity = 1; bannerT = 2200; }

  // ------------------------------------------------ 地圖查詢
  const isSolidTile = (tx, ty) => tx < 0 || ty < 0 || tx >= MAP.w || ty >= MAP.h || solid[ty][tx] === '1';
  const blockedPx = (x, y) => isSolidTile(Math.floor(x / TS), Math.floor(y / TS));
  function npcBlocks(x, y) {
    for (const e of ents) if ((e.k === 'npc' || e.k === 'dummy') && Math.hypot(e.px - x, e.py - y) < 15) return true;
    if (MAP.kind === 'loc' && S.shady) { const sx = (S.shady.x + .5) * TS - cam.x, sy = (S.shady.y + .9) * TS - cam.y; list.push({y: sy + cam.y, f: () => { drawNPC('shady', sx, sy, hero.x < sx + cam.x ? 'l' : 'r', false); label('神秘商人', sx, sy + 14, '#e8c060', 11); label('?', sx, sy - 62 + Math.sin(now / 260) * 3, '#e8c060', 22); }}); }
    if (S.partner && trail.length) { const t = trail[Math.max(0, trail.length - 7)], px = t.x - cam.x, py = t.y - cam.y, mv = hero.moving; list.push({y: t.y - 1, f: () => drawNPC(S.partner.sprite, px, py, t.dir, mv)}); }
    if (MAP.kind === 'loc' && S.questNpc) { const q = questPos(); if (Math.hypot(q[0] - x, q[1] - y) < 15) return true; }
    return false;
  }
  function free(x, y) {
    const hw = 8;
    return !(blockedPx(x - hw, y) || blockedPx(x + hw, y) || blockedPx(x - hw, y - 9) || blockedPx(x + hw, y - 9)) && !npcBlocks(x, y);
  }
  const questPos = () => [(MAP.npcSpot[0] + .5) * TS, (MAP.npcSpot[1] + .9) * TS];
  function zoneAt(x, y) {
    const tx = Math.floor(x / TS), ty = Math.floor(y / TS);
    if (tx < 0 || ty < 0 || tx >= MAP.w || ty >= MAP.h) return null;
    const c = MAP.zones[ty][tx]; return c === '.' ? null : MAP.zoneIds[+c];
  }
  function buildWorldCaches() {
    shoreMask = MAP.ground.map((row, y) => Array.from(row).map((c, x) => {
      if (!'gsdrtm'.includes(c)) return 0;
      const w = (xx, yy) => { const k = MAP.ground[yy] && MAP.ground[yy][xx]; return k === '~' || k === ','; };
      return (w(x, y - 1) ? 1 : 0) | (w(x + 1, y) ? 2 : 0) | (w(x, y + 1) ? 4 : 0) | (w(x - 1, y) ? 8 : 0);
    }));
    const W = MAP.w, H = MAP.h, cvs = document.createElement('canvas'); cvs.width = W; cvs.height = H;
    const c2 = cvs.getContext('2d'), COL = {'~': '#1e4682', ',': '#3c78be', g: '#6ebe5a', t: '#28783c', m: '#827d87', s: '#e2d096', r: '#a07850', R: '#4682c8', b: '#8c5a32', B: '#8c5a32', d: '#96784f'};
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { c2.fillStyle = COL[MAP.ground[y][x]] || '#000'; c2.fillRect(x, y, 1, 1); }
    minimapBase = cvs;
  }

  // ------------------------------------------------ 繪製：地磚
  const tileXY = (b, n) => Art.man.tiles[b][n];
  function drawTile(b, n, dx, dy) { const t = tileXY(b, n); g.drawImage(Art.img['tiles_' + b], t[0], t[1], TS, TS, dx, dy, TS, TS); }
  function groundTile(tx, ty, cam) {
    const c = MAP.ground[ty][tx], h = hs(tx, ty), f = Math.floor(now / 380 + tx + ty) % 4, dx = tx * TS - cam.x, dy = ty * TS - cam.y;
    let b = MAP.biome;
    if (MAP.kind === 'world') { const z = MAP.zones[ty][tx]; b = z === '.' ? 'tiannan' : MAP.zoneIds[+z]; }
    let n;
    if (MAP.kind === 'world') {
      n = {'~': 'sea' + f, ',': 'water' + f, R: 'water' + f, g: 'grass' + [0, 0, 1, 1, 2, 2, 0, 3][h % 8], t: 'forest' + (h % 3), m: 'mountain' + (h % 3), s: 'sand' + (h % 2), r: 'path' + (h % 2), b: 'bridgeH', B: 'bridgeV', d: 'dirt' + (h % 2)}[c] || 'grass0';
    } else {
      n = {g: 'grass' + [0, 0, 1, 1, 2, 2, 0, 3][h % 8], d: 'dirt' + (h % 2), p: 'path' + (h % 2), c: 'court0', o: 'wood0', w: 'water' + f, k: 'cave0', W: 'cavewall0', h: 'hedge0', s: 'sand' + (h % 2), e: 'path0'}[c] || 'grass0';
    }
    drawTile(b, n, dx, dy);
    if (MAP.kind === 'world' && shoreMask[ty][tx]) drawTile(b, 'shore' + shoreMask[ty][tx], dx, dy);
    if (c === 'e') { g.fillStyle = 'rgba(255,230,140,.6)'; g.font = 'bold 18px sans-serif'; g.textAlign = 'center'; g.fillText('▼', dx + 16, dy + 22); }
  }

  // ------------------------------------------------ 繪製：物件與角色
  function objRect(b, n) { return Art.man.objects[b][n]; }
  function drawObj(b, n, ax, ay, scale) {           // ax,ay：底部中心
    const r = objRect(b, n); if (!r) return;
    const w = r[2] * scale, h = r[3] * scale;
    g.drawImage(Art.img['objects_' + b], r[0], r[1], r[2], r[3], Math.round(ax - w / 2), Math.round(ay - h), w, h);
  }
  function shadow(x, y, w) { g.fillStyle = 'rgba(0,0,0,.28)'; g.beginPath(); g.ellipse(x, y, w, w * .3, 0, 0, 7); g.fill(); }
  function human(sheet, baseRow, animRows, dir, moving, x, y, sc = 1, frameOverride = null) {
    const fw = Art.man.human.frameW, fh = Art.man.human.frameH;
    let anim = dir === 'u' ? (moving ? 'walk_u' : 'idle_u') : dir === 'd' ? (moving ? 'walk_d' : 'idle_d') : (moving ? 'walk' : 'idle');
    if (frameOverride && frameOverride.anim) anim = frameOverride.anim;
    const f = frameOverride && frameOverride.f !== undefined ? frameOverride.f : (moving ? Math.floor(now / 130) % 4 : [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 330) % 8]);
    const row = baseRow + animRows[anim].row, flip = dir === 'l' || (frameOverride && frameOverride.flip);
    const dx = x - fw * sc / 2, dy = y - 50 * sc;
    if (flip) { g.save(); g.translate(x, 0); g.scale(-1, 1); g.drawImage(Art.img[sheet], f * fw, row * fh, fw, fh, -fw * sc / 2, dy, fw * sc, fh * sc); g.restore(); }
    else g.drawImage(Art.img[sheet], f * fw, row * fh, fw, fh, dx, dy, fw * sc, fh * sc);
  }
  const heroBase = () => Art.man.heroes.outfitRows[Math.min(5, S.realm_index)];
  function drawHero(cam) { shadow(hero.x - cam.x, hero.y - cam.y + 1, 12); if (hero.inv <= 0 || Math.floor(now / 90) % 2) human('heroes', heroBase(), Art.man.heroes.anims, hero.dir, hero.moving, hero.x - cam.x, hero.y - cam.y); }
  function drawNPC(id, x, y, dir, moving) { const m = Art.man.npcs[id]; if (!m) return; shadow(x, y + 1, 12); human('npcs', m.row, Art.man.npcAnims, dir, moving, x, y); }
  function drawBeast(e, x, y, sc = 1, flip = false, frame = null) {
    const B = Art.man.beasts, k = B.kinds[e.kind], row = k.row + B.elements.indexOf(e.el), fw = B.frameW, fh = B.frameH, f = frame === null ? Math.floor(now / 180) % 4 : frame;
    if (frame === null) shadow(x, y + 2, 20);
    const lift = e.kind === 'bat' ? 26 : 0;
    if (flip) { g.save(); g.translate(x, 0); g.scale(-1, 1); g.drawImage(Art.img.beasts, f * fw, row * fh, fw, fh, -fw * sc / 2, y - lift - 41 * sc, fw * sc, fh * sc); g.restore(); }
    else g.drawImage(Art.img.beasts, f * fw, row * fh, fw, fh, x - fw * sc / 2, y - lift - 41 * sc, fw * sc, fh * sc);
  }
  const speakerSprite = n => Art.man.speakers[n];
  function label(t, x, y, col = '#fff', size = 12) { g.font = `bold ${size}px sans-serif`; g.textAlign = 'center'; g.lineWidth = 3; g.strokeStyle = '#000c'; g.strokeText(t, x, y); g.fillStyle = col; g.fillText(t, x, y); }

  // ------------------------------------------------ 更新
  const down = (...k) => k.some(x => keys[x] || keys[x.toUpperCase()]);
  function update(dt) {
    now = performance.now();
    if (toastT > 0) { toastT -= dt * 1000; if (toastT <= 0) $('toast').textContent = ''; }
    if (bannerT > 0) { bannerT -= dt * 1000; if (bannerT <= 0) $('banner').style.opacity = 0; }
    hero.inv -= dt; exitCool -= dt;
    if (!S || !MAP) return;
    const frozen = busy || S.dialogue || S.battle || askOpen || S.shop || S.board || S.cand || bagOpen || compOpen || S.alch || S.war || codexOpen;
    if (frozen) walk = null;
    if (!frozen) {
      let dx = (down('d', 'arrowright') ? 1 : 0) - (down('a', 'arrowleft') ? 1 : 0), dy = (down('s', 'arrowdown') ? 1 : 0) - (down('w', 'arrowup') ? 1 : 0);
      hero.moving = false;
      if (dx || dy) {
        const len = Math.hypot(dx, dy), sp = (MAP.kind === 'world' ? 150 : 125) * (keys.Shift ? 1.6 : 1) * dt;
        const nx = hero.x + dx / len * sp, ny = hero.y + dy / len * sp;
        let moved = false;
        if (dx && free(nx, hero.y)) { dist += Math.abs(nx - hero.x); hero.x = nx; moved = true; }
        if (dy && free(hero.x, ny)) { dist += Math.abs(ny - hero.y); hero.y = ny; moved = true; }
        hero.moving = moved;
        if (moved) { const l = trail[trail.length - 1]; if (!l || Math.hypot(l.x - hero.x, l.y - hero.y) > 6) { trail.push({x: hero.x, y: hero.y, dir: hero.dir}); if (trail.length > 60) trail.shift(); } }
        hero.dir = Math.abs(dx) >= Math.abs(dy) && dx ? (dx > 0 ? 'r' : 'l') : (dy > 0 ? 'd' : 'u');
        if (!dx) hero.dir = dy > 0 ? 'd' : 'u';
        walk = null;
      } else if (walk) followWalk(dt);
      triggers(dt);
      syncT += dt; if (syncT > 2) { syncT = 0; syncPos(); }
    } else hero.moving = false;
    if (MAP.kind === 'loc') actors(dt);
    hud();
  }
  function syncPos() {
    const steps = Math.floor(dist / 16); dist -= steps * 16;
    const k = hero.x.toFixed(0) + ',' + hero.y.toFixed(0);
    if (k === lastPos && !steps) return;
    lastPos = k;
    fetch('/pos?' + new URLSearchParams({x: (hero.x / TS).toFixed(2), y: (hero.y / TS).toFixed(2), steps}), {method: 'POST'});
  }
  function triggers(dt) {
    if (MAP.kind === 'world') {
      for (const e of ents) {
        const cx = (e.x + .5) * TS, cy = (e.y + .6) * TS, d = Math.hypot(hero.x - cx, hero.y - cy);
        if (e.k === 'enter' && d < 20 && !cool.enter) { cool.enter = true; post('enter', {loc: e.loc}).then(() => { cool.enter = false; }); return; }
        if (e.k === 'dock') {
          if (d < 30 && !e.asked && !askOpen) { e.asked = true; askFerry(e); return; }
          if (d > 60) e.asked = false;
        }
      }
      const z = zoneAt(hero.x, hero.y);
      if (z && z !== S.region && !regionPending) { regionPending = true; post('region', {to: z}).then(() => { regionPending = false; }); }
    } else {
      const tx = Math.floor(hero.x / TS), ty = Math.floor(hero.y / TS);
      if (exitCool <= 0 && MAP.exit.some(c => c[0] === tx && c[1] === ty) && !askOpen) askLeave();
      for (const e of ents) {
        if (e.k !== 'enemy' || S.defeated.includes(e.id) || (cool['f' + e.id] || 0) > now) continue;
        if (Math.hypot(e.px - hero.x, e.py - hero.y) < 26 && !busy) { startBattle(e); return; }
      }
    }
  }
  function actors(dt) {
    for (const e of ents) {
      if (e.k === 'enemy' && !S.defeated.includes(e.id)) {
        const d = Math.hypot(hero.x - e.px, hero.y - e.py), chase = d < 150 && !(S.battle) && !askOpen && !S.dialogue;
        let sp = chase ? 62 : 26, tx, ty;
        if (chase && (cool['f' + e.id] || 0) < now) { tx = hero.x; ty = hero.y; }
        else { e.t -= dt; if (e.t <= 0) { e.t = 1 + Math.random() * 2; e.gx = e.hx + (Math.random() - .5) * e.r * TS * 2; e.gy = e.hy + (Math.random() - .5) * e.r * TS * 2; } tx = e.gx ?? e.px; ty = e.gy ?? e.py; }
        stepTo(e, tx, ty, sp * dt, 8);
      } else if (e.k === 'npc' && e.wander && !S.dialogue && !askOpen && !S.battle) {
        e.t -= dt; if (e.t <= 0) { e.t = 1.5 + Math.random() * 3; e.gx = e.hx + (Math.random() - .5) * 4 * TS; e.gy = e.hy + (Math.random() - .5) * 3 * TS; }
        e.moving = false;
        if (e.gx !== undefined) stepTo(e, e.gx, e.gy, 22 * dt, 8, true);
      }
    }
  }
  function stepTo(e, tx, ty, sp, hw, isNpc) {
    const dx = tx - e.px, dy = ty - e.py, d = Math.hypot(dx, dy);
    e.moving = false;
    if (d < 3) return;
    const sx = dx / d * sp, sy = dy / d * sp, ok = (x, y) => !(blockedPx(x - hw, y) || blockedPx(x + hw, y) || blockedPx(x - hw, y - 6) || blockedPx(x + hw, y - 6)) && Math.hypot(hero.x - x, hero.y - y) > 14;
    if (ok(e.px + sx, e.py)) { e.px += sx; e.moving = true; }
    if (ok(e.px, e.py + sy)) { e.py += sy; e.moving = true; }
    if (Math.abs(sx) > .01) e.dir = sx > 0 ? 1 : -1;
    e.face = Math.abs(sx) > Math.abs(sy) ? (sx > 0 ? 'r' : 'l') : (sy > 0 ? 'd' : 'u');
  }

  // ------------------------------------------------ 互動
  function interactables() {
    const out = [];
    if (MAP.kind !== 'loc') return out;
    for (const e of ents) {
      if (e.k === 'npc') out.push({id: e.id, x: e.px, y: e.py, text: e.role === 'beggar' ? '施捨乞丐（積善緣）' : e.role === 'pharmacy' || e.role === 'shop' ? `到${e.name}的鋪子看看` : `與${e.name}交談`});
      else if (e.k === 'candidate') out.push({id: e.id, x: e.px, y: e.py, text: `與${e.name}交談` + ((S.affinity[e.cid] || 0) > 0 ? ` ♥${S.affinity[e.cid]}` : '')});
      else if (e.k === 'board') out.push({id: e.id, x: (e.x + 1) * TS, y: (e.y + 1.4) * TS, text: '查看布告欄'});
      else if (e.k === 'chest' && !S.opened.includes(e.id)) out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + .9) * TS, text: '打開寶箱'});
      else if (e.k === 'dummy') out.push({id: e.id, x: e.px, y: e.py, text: '練習劍法（木人樁）'});
      else if (e.k === 'altar') out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + 1.2) * TS, text: '在祭壇前調息'});
      else if (e.k === 'well') out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + 1.2) * TS, text: '在井邊存檔（死亡時回到這裡）'});
      else if (e.k === 'guardian' && !(S.guardians || []).includes(S.cur_loc)) out.push({id: e.id, kind: 'guardian', x: (e.x + .5) * TS, y: (e.y + 1.2) * TS, text: `挑戰${e.name}（主要對手）`});
      else if (e.k === 'portal') out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + 1.2) * TS, text: '觸碰空間節點'});
      else if (e.k === 'sign') out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + 1.2) * TS, text: '查看告示牌'});
      else if (e.k === 'plot') { const st = S.plots[e.id] || {stage: 0}; out.push({id: e.id, kind: 'plot', x: (e.x + .5) * TS, y: (e.y + 1) * TS, text: ['空地：播種', '幼苗：查看', '生長中：查看', '已成熟：收成'][st.stage]}); }
      else if (e.k === 'bed') out.push({id: e.id, x: (e.x + .5) * TS, y: (e.y + .9) * TS, text: '在此歇息（恢復氣血靈力）'});
      else if (e.k === 'furnace') out.push({id: e.id, kind: 'furnace', x: (e.x + .5) * TS, y: (e.y + 1.4) * TS, text: '使用煉丹爐'});
    }
    if (S.karma_ev) out.push({id: 'karma', x: (S.karma_ev.x + .5) * TS, y: (S.karma_ev.y + .9) * TS, text: S.karma_ev.kind === 'avenger' ? `面對仇家「${S.karma_ev.name}」` : `與故人「${S.karma_ev.name}」相見`});
    if (S.wev_ent) { const w = S.wev_ent; out.push({id: 'wev', x: (w.x + .5) * TS, y: (w.y + .9) * TS, text: ({raid: '迎戰', refugee: '資助', fall: '查看墜落的異寶', war: '商議戰局'}[w.type] || '互動') + (w.type === 'fall' ? '' : `「${w.name}」`)}); }
    if (S.shady) out.push({id: 'shady', x: (S.shady.x + .5) * TS, y: (S.shady.y + .9) * TS, text: '與神秘商人交易'});
    if (S.questNpc) { const q = questPos(); out.push({id: 'quest', x: q[0], y: q[1], text: `與${S.questNpc}交談`}); }
    return out;
  }
  function nearest() {
    let b = null, bd = 52;
    for (const i of interactables()) { const d = Math.hypot(i.x - hero.x, i.y - hero.y); if (d < bd) { bd = d; b = i; } }
    return b;
  }
  function interact() {
    if (busy || S.dialogue || S.battle || askOpen || S.shop || S.board || S.cand || bagOpen || compOpen || codexOpen) return;
    const n = nearest(); if (!n) return;
    useIt(n);
  }
  function useIt(n) {
    if (n.kind === 'plot') plotMenu(n.id); else if (n.kind === 'furnace') furnaceMenu();
    else if (n.kind === 'guardian') askBox(`${n.text.replace('挑戰', '')}攔在前方。要戰鬥嗎？（可使用陣法、符錄、法寶；敗北會回到上次儲存點）`, [{label: '戰鬥！', fn: () => post('talk', {ent: n.id})}, {label: '先不要', fn: () => {}}]);
    else post('talk', {ent: n.id});
  }
  // ---- 滑鼠點擊移動（A* 尋路）----
  function findPath(sx, sy, gx, gy) {
    const W = MAP.w, H = MAP.h, idx = (x, y) => y * W + x, N = W * H;
    if (isSolidTile(gx, gy)) {          // 目標是實心格：找最近的可走格
      let best = null, bd = 1e9;
      for (let r = 1; r <= 4 && !best; r++) for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) { const x = gx + dx, y = gy + dy; if (!isSolidTile(x, y) && dx * dx + dy * dy < bd) { bd = dx * dx + dy * dy; best = [x, y]; } }
      if (!best) return null; gx = best[0]; gy = best[1];
    }
    if (sx === gx && sy === gy) return [[gx, gy]];
    const gs = new Float32Array(N).fill(1e9), from = new Int32Array(N).fill(-1), closed = new Uint8Array(N), open = [[0, idx(sx, sy)]];
    gs[idx(sx, sy)] = 0;
    const hh = (x, y) => Math.max(Math.abs(x - gx), Math.abs(y - gy)) + .41 * Math.min(Math.abs(x - gx), Math.abs(y - gy));
    let guard = 0;
    while (open.length && guard++ < 60000) {
      let bi = 0; for (let i = 1; i < open.length; i++) if (open[i][0] < open[bi][0]) bi = i;
      const cur = open.splice(bi, 1)[0][1], cx = cur % W, cy = (cur / W) | 0;
      if (closed[cur]) continue; closed[cur] = 1;
      if (cx === gx && cy === gy) { const path = []; let c = cur; while (c !== -1) { path.push([c % W, (c / W) | 0]); c = from[c]; } return path.reverse(); }
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dy) continue;
        const nx = cx + dx, ny = cy + dy;
        if (isSolidTile(nx, ny) || (dx && dy && (isSolidTile(cx + dx, cy) || isSolidTile(cx, cy + dy)))) continue;
        const ni = idx(nx, ny), ng = gs[cur] + (dx && dy ? 1.414 : 1);
        if (ng < gs[ni]) { gs[ni] = ng; from[ni] = cur; open.push([ng + hh(nx, ny), ni]); }
      }
    }
    return null;
  }
  function walkTo(px, py, ent) {
    if (!S || !MAP || busy || S.dialogue || S.battle || askOpen || S.shop || S.board || S.cand || bagOpen || compOpen || codexOpen) return;
    const path = findPath(Math.floor(hero.x / TS), Math.floor(hero.y / TS), Math.max(0, Math.min(MAP.w - 1, Math.floor(px / TS))), Math.max(0, Math.min(MAP.h - 1, Math.floor(py / TS))));
    if (!path) { toast('走不到那裡。'); return; }
    const pts = path.slice(1).map(c => ({x: (c[0] + .5) * TS, y: (c[1] + .75) * TS}));
    const last = path[path.length - 1];
    walk = {pts, gx: (last[0] + .5) * TS, gy: (last[1] + .75) * TS, ent: ent || null, tries: 0};
    stuckT = 0;
  }
  function followWalk(dt) {
    const w = walk;
    if (!w.pts.length) { const ent = w.ent; walk = null; if (ent) { const n = interactables().find(i => i.id === ent.id); if (n && Math.hypot(n.x - hero.x, n.y - hero.y) < 60) useIt(n); } return; }
    const t = w.pts[0], dx = t.x - hero.x, dy = t.y - hero.y, d = Math.hypot(dx, dy), sp = (MAP.kind === 'world' ? 150 : 125) * dt;
    if (d < Math.max(3, sp)) { hero.x = t.x; hero.y = t.y; w.pts.shift(); hero.moving = true; return; }
    const nx = hero.x + dx / d * sp, ny = hero.y + dy / d * sp;
    let moved = false;
    if (free(nx, ny)) { dist += sp; hero.x = nx; hero.y = ny; moved = true; }
    else if (Math.abs(dx) > 1 && free(nx, hero.y)) { dist += Math.abs(nx - hero.x); hero.x = nx; moved = true; }
    else if (Math.abs(dy) > 1 && free(hero.x, ny)) { dist += Math.abs(ny - hero.y); hero.y = ny; moved = true; }
    hero.moving = moved;
    if (moved) { stuckT = 0; const l = trail[trail.length - 1]; if (!l || Math.hypot(l.x - hero.x, l.y - hero.y) > 6) { trail.push({x: hero.x, y: hero.y, dir: hero.dir}); if (trail.length > 60) trail.shift(); } }
    else { stuckT += dt; if (stuckT > .5) { const e = w.ent; walk = null; if (w.tries < 2) { walkTo(w.gx, w.gy, e); if (walk) walk.tries = w.tries + 1; } } }
    hero.dir = Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? 'r' : 'l') : (dy > 0 ? 'd' : 'u');
  }
  function clickWalk(ev) {
    if (!S || S.battle || !MAP) return;
    const r = cv.getBoundingClientRect(), x = (ev.clientX - r.left) * VW / r.width + lastCam.x, y = (ev.clientY - r.top) * VH / r.height + lastCam.y;
    if (MAP.kind === 'loc') {
      let best = null, bd = 34;
      for (const i of interactables()) { const d = Math.hypot(i.x - x, i.y - (y + 10)); if (d < bd) { bd = d; best = i; } }
      if (best) { walkTo(best.x, best.y, best); return; }
    } else {
      for (const e of ents) if (e.k === 'enter' && Math.hypot((e.x + .5) * TS - x, (e.y + .5) * TS - y) < 34) { walkTo((e.x + .5) * TS, (e.y + 1.6) * TS, null); return; }
    }
    walkTo(x, y, null);
  }
  cv.addEventListener('mousedown', ev => { if (ev.button === 0 && !(S && S.battle)) clickWalk(ev); });
  $('mini').addEventListener('mousedown', ev => {
    if (!S || !MAP || MAP.kind !== 'world') return;
    const r = $('mini').getBoundingClientRect(), k = 150 / Math.max(MAP.w, MAP.h);
    walkTo((ev.clientX - r.left) * 150 / r.width / k * TS, (ev.clientY - r.top) * 150 / r.height / k * TS, null); ev.stopPropagation();
  });
  function askBox(title, opts) {
    askOpen = true; const a = $('ask'); a.style.display = 'block';
    a.innerHTML = `<div style="font-size:18px;margin-bottom:8px">${title}</div>` + opts.map((o, i) => `<button data-i="${i}">${i + 1}. ${o.label}</button>`).join('');
    a._opts = opts;
    a.querySelectorAll('button').forEach(b => b.onclick = () => closeAsk(+b.dataset.i));
  }
  function closeAsk(i) { const a = $('ask'); const o = a._opts[i]; a.style.display = 'none'; askOpen = false; if (o && o.fn) o.fn(); }
  function plotMenu(id) {
    const st = S.plots[id] || {stage: 0};
    if (st.stage === 3) { post('harvest', {ent: id}); return; }
    if (st.stage === 0) {
      askBox(`播種（靈石 ${S.lingshi}）`, Object.entries(S.seeds).map(([k, v]) => ({label: `${v.name}　${v.cost} 靈石・${v.days} 日・收 ${v.yield[0]}~${v.yield[1]} 株${v.lingye ? '（可能掉靈液）' : ''}`, fn: () => post('plant', {ent: id, seed: k})})).concat([{label: '不種了', fn: () => {}}]));
      return;
    }
    const sd = S.seeds[st.seed] || {name: '藥草'};
    const opts = [];
    if (S.lingye > 0 && !st.boost) opts.push({label: `滴一滴靈液催熟（剩 ${S.lingye} 滴）`, fn: () => post('boost', {ent: id})});
    opts.push({label: '先離開', fn: () => {}});
    askBox(`${sd.name}：${st.stage === 1 ? '剛冒芽' : '長勢良好'}，還要約 ${st.left} 日成熟${st.boost ? '（已催熟）' : ''}`, opts);
  }
  function furnaceMenu() {
    const need = (r) => Object.entries(r.needs).map(([k, v]) => ({herb: '靈草', lingye: '靈液', lingshi: '靈石'}[k] + '×' + v)).join(' ');
    askBox(`煉丹爐（靈草 ${S.herbs}・靈液 ${S.lingye}・靈石 ${S.lingshi}・熟練 ${S.alch_n}）`, Object.entries(S.recipes).flatMap(([k, v]) => [{label: `🔥 火候煉製 ${v.name}　需 ${need(v)}（品質決定產量；熟練度越高越好控制）`, fn: () => post('alch_start', {recipe: k})}, {label: `快速煉製 ${v.name}${v.chance < 1 ? '（成功率約 ' + Math.round(v.chance * 100) + '%）' : ''}`, fn: () => post('craft', {recipe: k})}]).concat([{label: '不煉了', fn: () => {}}]));
  }
  function askLeave() {
    askBox(`離開「${MAP.name}」？`, [{label: '離開，回到大地圖', fn: () => post('leave')}, {label: '留下', fn: () => { hero.y -= 46; exitCool = 1.5; }}]);
  }
  function askFerry(d) {
    const to = S.region === 'luanxinghai' ? 'tiannan' : 'luanxinghai';
    const nm = S.world.find(w => w.id === to).name;
    askBox(`搭船前往「${nm}」？（約 8 日航程）`, [{label: '出發', fn: () => post('ferry', {to})}, {label: '再等等', fn: () => {}}]);
  }
  function toggleBag() { bagOpen = !bagOpen; if (bagOpen) { compOpen = false; codexOpen = false; } walk = null; panels(); }
  function toggleComp() { compOpen = !compOpen; if (compOpen) { bagOpen = false; codexOpen = false; } walk = null; panels(); }
  function toggleCodex(tab) { if (tab) { codexTab = tab; codexOpen = true; } else codexOpen = !codexOpen; if (codexOpen) { bagOpen = false; compOpen = false; } walk = null; panels(); }
  const key = k => {
    if (askOpen) { const a = $('ask'); if (k === '1' || k === 'enter') closeAsk(0); else if (k === '2') closeAsk(1); else if (k === 'escape') closeAsk(a._opts.length - 1); return; }
    if (k === 'b' && S && !S.battle) { toggleBag(); return; }
    if (k === 'p' && S && !S.battle) { toggleComp(); return; }
    if (k === 'g' && S && !S.battle) { toggleCodex(); return; }
    if (k === 'escape' && codexOpen) { toggleCodex(); return; }
    if (k === 'escape' && compOpen) { toggleComp(); return; }
    if (k === 'escape' && bagOpen) { toggleBag(); return; }
    if (S && S.battle) return;
    if (k === 'e' || k === ' ' || k === 'enter') interact();
  };
  addEventListener('keydown', e => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' '].includes(e.key)) e.preventDefault(); if (!keys[e.key]) { keys[e.key] = 1; key(e.key.toLowerCase()); } });
  addEventListener('keyup', e => keys[e.key] = 0);
  addEventListener('blur', () => { for (const k in keys) keys[k] = 0; });
  addEventListener('error', e => err('頁面錯誤：' + e.message));

  // ------------------------------------------------ 戰鬥
  function startBattle(e) {
    const near = ents.filter(o => o.k === 'enemy' && !S.defeated.includes(o.id) && Math.hypot(o.px - e.px, o.py - e.py) < TS * 6)
      .sort((a, b) => Math.hypot(a.px - e.px, a.py - e.py) - Math.hypot(b.px - e.px, b.py - e.py)).slice(0, MAP.cat === 'deep' ? 2 : 3);
    bt = {target: 0, fx: [], shake: {}, heroAnim: null, prev: null, over: false, ids: near.map(o => o.id), t0: now};
    post('battle_start', {ids: near.map(o => o.id).join(',')});
  }
  function btCmd(cmd, arg) {
    if (busy || !S.battle || S.battle.over) return;
    const prevE = S.battle.enemies.map(e => e.hp), prevHp = S.hp, t = S.battle.enemies[bt.target] && !S.battle.enemies[bt.target].dead ? bt.target : S.battle.enemies.findIndex(e => !e.dead);
    bt.menu = null; bt.heroAnim = {kind: ['attack', 'spell', 'talisman', 'treasure'].includes(cmd) ? 'attack' : 'idle', t: now, target: t, el: cmd === 'spell' ? S.elements[arg % S.elements.length] : null};
    const hp0 = S.hp;
    post('battle', {cmd, arg: arg ?? '', target: t}).then(() => {
      if (S.battle.pact) bt.pAnim = Object.assign({t: now + 380}, S.battle.pact);
      S.battle.enemies.forEach((e, i) => { const d = prevE[i] - e.hp; if (d > 0.5) { bt.fx.push({x: 0, i, t: now + 320, txt: Math.round(d), c: '#ffec99'}); bt.shake[i] = now + 500; } });
      if (S.hp < prevHp - .5) { bt.fx.push({hero: true, t: now + 500, txt: Math.round(prevHp - S.hp), c: '#ff8080'}); bt.heroHit = now + 500; }
      else if (S.hp > prevHp + .5) bt.fx.push({hero: true, t: now, txt: '+' + Math.round(S.hp - prevHp), c: '#8f8'});
    });
  }
  function btEnd() {
    const ids = (bt && bt.ids) || [];
    if (S.battle && S.battle.over === 'flee') ids.forEach(id => cool['f' + id] = now + 3500);
    post('battle_end');
  }
  function drawBattle() {
    const b = S.battle, B = MAP.biome || 'tiannan', bio = MAP.kind === 'world' ? 'tiannan' : B;
    const sk = Art.man.biomes[bio] ? Art.man.biomes[bio].sky : ['#274b6e', '#8fc1d8'];
    const gr = g.createLinearGradient(0, 0, 0, 330); gr.addColorStop(0, sk[0]); gr.addColorStop(1, sk[1]); g.fillStyle = gr; g.fillRect(0, 0, VW, VH);
    g.fillStyle = 'rgba(0,0,0,.25)';
    for (let x = 0; x < VW; x += 4) { const h = Math.floor(90 * (.45 + .55 * Math.abs(Math.sin(x * .008) * Math.sin(x * .019 + 1))) / 4) * 4; g.fillRect(x, 330 - h, 4, h); }
    const cave = MAP.cat === 'deep';
    for (let cx = 0; cx * 64 < VW; cx++) for (let cy = 0; 330 + cy * 64 < VH; cy++) { const t = cave ? tileXY(bio, 'cave0') : tileXY(bio, 'grass' + ((cx + cy) % 3)); g.drawImage(Art.img['tiles_' + bio], t[0], t[1], 32, 32, cx * 64, 330 + cy * 64, 64, 64); }
    if (cave) { g.fillStyle = 'rgba(30,10,50,.55)'; g.fillRect(0, 0, VW, 330); }
    // 主角
    let hx = 230, hy = 400, frame = null;
    const ha = bt.heroAnim;
    if (ha && now - ha.t < 520) {
      const p = (now - ha.t) / 520;
      if (ha.kind === 'attack') { hx += Math.sin(Math.min(1, p * 1.6) * Math.PI) * (ha.el ? 20 : 150); frame = {anim: 'attack', f: Math.min(2, Math.floor(p * 3)), flip: false}; }
    }
    if (bt.heroHit && now < bt.heroHit) frame = {anim: 'hurt', f: 0};
    if (b.over === 'lose') frame = {anim: 'hurt', f: 0};
    if (b.partner) {
      let px = 110, py = 412;
      const pa = bt.pAnim;
      if (pa && now - pa.t < 520 && now > pa.t) { const p = (now - pa.t) / 520; if (pa.kind !== 'heal') px += Math.sin(Math.min(1, p * 1.6) * Math.PI) * (pa.kind === 'spell' ? 14 : 110); }
      shadow(px, py + 2, 36);
      human('npcs', Art.man.npcs[b.partner.sprite].row, Art.man.npcAnims, 'r', false, px, py, 3, {anim: 'idle', f: [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 330) % 8]});
      label('♥ ' + b.partner.name, px, py + 22, '#ffc0d8', 12);
    }
    (b.allies || []).forEach((a, i) => {
      if (a.type === 'pet') { const px = 165, py = 382; shadow(px, py + 2, 30); drawBeast({kind: a.kind, el: a.el}, px, py, 1.7, false, Math.floor(now / 250) % 4); label(a.name + ' Lv' + a.level, px, py + 20, '#cfe', 11); if (a.skill) label('✦' + a.skill + (a.cd ? '（' + a.cd + '）' : '（就緒）'), px, py + 34, a.cd ? '#8aa' : '#ffd24a', 11); }
      else if (Art.man.npcs[a.sprite]) { const px = 58, py = 398; g.globalAlpha = a.hp <= 0 ? .4 : 1; shadow(px, py + 2, 34); human('npcs', Art.man.npcs[a.sprite].row, Art.man.npcAnims, 'r', false, px, py, 3, {anim: 'idle', f: [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 330) % 8]}); g.globalAlpha = 1; label(a.name + (a.hp <= 0 ? '（破損）' : ` ${Math.round(a.hp)}/${a.maxhp}`), px, py + 20, '#fda', 11); if (a.skill) label('✦' + a.skill + (a.cd ? '（' + a.cd + '）' : '（就緒）'), px, py + 34, a.cd ? '#8aa' : '#ffd24a', 11); }
    });
    shadow(hx, hy + 2, 42);
    human('heroes', heroBase(), Art.man.heroes.anims, 'r', false, hx, hy, 3, frame || {anim: 'idle', f: [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 330) % 8]});
    // 敵人
    b.enemies.forEach((e, i) => {
      if (e.dead && !(bt.shake[i] && now < bt.shake[i] + 400)) return;
      const ex = 660 + i * 95, ey = 360 + i * 46, sh = bt.shake[i] && now < bt.shake[i] ? Math.sin(now / 25) * 6 : 0;
      g.globalAlpha = e.dead ? Math.max(0, 1 - (now - bt.shake[i]) / 400 + .4) : 1;
      const off = e.sprite ? 62 : 0;
      shadow(ex, ey + 2, e.sprite ? 54 : 46);
      if (e.sprite && Art.man.npcs[e.sprite]) human('npcs', Art.man.npcs[e.sprite].row, Art.man.npcAnims, 'l', false, ex + sh, ey, 4, {anim: 'idle', f: [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 330) % 8]});
      else drawBeast(e, ex + sh, ey, e.boss ? 3.6 : 3, true, Math.floor(now / 250) % 4);
      g.globalAlpha = 1;
      if (!e.dead) {
        g.fillStyle = '#222'; g.fillRect(ex - 44, ey - 150 - off, 88, 8); g.fillStyle = e.boss ? '#e8a020' : '#e44'; g.fillRect(ex - 44, ey - 150 - off, 88 * Math.max(0, e.hp / e.maxhp), 8);
        label((e.boss ? '★ ' : '') + (b.codex ? e.el : '？') + ' ' + e.name + (e.stun ? ' 💫' : ''), ex, ey - 158 - off, b.codex ? ECOL[e.el] : '#ccc', 13);
        if (b.codex && e.weak && e.weak.length) label('弱點：' + e.weak.join(''), ex, ey - 172 - off, '#9fe', 11);
        else if (!b.codex) label('（沒有《妖獸圖錄》，看不出屬性）', ex, ey - 172 - off, '#777', 10);
        if (b.codex && e.boss && e.skills && e.skills.length) label('招式：' + e.skills.join('、'), ex, ey - 8 - off + 24 + off, '#e8a', 10);
        if (e.charging) { g.globalAlpha = .5 + .5 * Math.sin(now / 90); label('⚠ 蓄力絕招！', ex, ey - 184 - off, '#ff5a5a', 16); g.globalAlpha = 1; }
        if (i === bt.target && !b.over) label('▼', ex, ey - 168 - off + Math.sin(now / 150) * 4, '#ffd24a', 24);
      }
    });
    // 夥伴特效
    const pa2 = bt.pAnim;
    if (pa2 && b.partner && now - pa2.t < 700 && now > pa2.t) {
      const dt2 = now - pa2.t;
      if (pa2.kind === 'heal') { for (let k = 0; k < 5; k++) label('+', hx - 30 + k * 16, hy - 120 - dt2 / 8 - (k % 2) * 12, '#7dff9a', 22); }
      else if (pa2.kind === 'spell' && dt2 > 120 && dt2 < 480) {
        const p = Math.min(1, (dt2 - 120) / 320), ti = pa2.target, tx = 660 + ti * 95, ty = 300 + ti * 46, rr = Art.man.fx.rects[`orb_${pa2.el}_${Math.floor(now / 100) % 2}`];
        const x = 150 + (tx - 150) * p, y = 380 + (ty - 380) * p; g.drawImage(Art.img.fx, rr[0], rr[1], rr[2], rr[3], x - rr[2] * 1.5, y - rr[3] * 1.5, rr[2] * 3, rr[3] * 3);
      } else if (pa2.kind === 'attack' && dt2 > 160 && dt2 < 420) {
        const ti = pa2.target, tx = 660 + ti * 95, ty = 330 + ti * 46, r = Art.man.fx.rects['slash' + Math.min(2, Math.floor((dt2 - 160) / 90))];
        g.save(); g.translate(tx, ty - 40); g.scale(-2, 2); g.drawImage(Art.img.fx, r[0], r[1], r[2], r[3], -26, -36, r[2], r[3]); g.restore();
      }
    }
    // 特效：法術光球
    if (ha && ha.el && now - ha.t < 520 && now - ha.t > 120) {
      const p = Math.min(1, (now - ha.t - 120) / 300), ti = ha.target, tx = 660 + ti * 95, ty = 300 + ti * 46, rr = Art.man.fx.rects[`orb_${ha.el}_${Math.floor(now / 100) % 2}`];
      const x = hx + 60 + (tx - hx - 60) * p, y = hy - 90 + (ty - hy + 90) * p;
      g.drawImage(Art.img.fx, rr[0], rr[1], rr[2], rr[3], x - rr[2] * 1.5, y - rr[3] * 1.5, rr[2] * 3, rr[3] * 3);
    }
    if (ha && !ha.el && ha.kind === 'attack' && now - ha.t > 160 && now - ha.t < 420) {
      const ti = ha.target, tx = 660 + ti * 95, ty = 330 + ti * 46, r = Art.man.fx.rects['slash' + Math.min(2, Math.floor((now - ha.t - 160) / 90))];
      g.save(); g.translate(tx, ty - 40); g.scale(-2, 2); g.drawImage(Art.img.fx, r[0], r[1], r[2], r[3], -26, -36, r[2], r[3]); g.restore();
    }
    // 飄字
    bt.fx = bt.fx.filter(f => now < f.t + 900);
    for (const f of bt.fx) {
      if (now < f.t) continue;
      const p = (now - f.t) / 900, x = f.hero ? hx : 660 + f.i * 95, y = (f.hero ? hy - 150 : 290 + f.i * 46) - p * 60;
      label(String(f.txt), x, y, f.c, 26);
    }
    // 主角狀態
    g.fillStyle = '#000a'; g.fillRect(16, 16, 250, 62);
    label(S.name + '  Lv' + S.level, 141, 34, '#ffe9a6', 15);
    g.fillStyle = '#222'; g.fillRect(24, 42, 234, 10); g.fillStyle = '#e44'; g.fillRect(24, 42, 234 * Math.max(0, S.hp / S.max_hp), 10);
    g.fillStyle = '#222'; g.fillRect(24, 58, 234, 8); g.fillStyle = '#48c'; g.fillRect(24, 58, 234 * Math.max(0, S.mp / S.max_mp), 8);
    label(`氣血 ${S.hp}/${S.max_hp}`, 141, 51, '#fff', 10); label(`靈力 ${S.mp}/${S.max_mp}`, 141, 66, '#fff', 9);
    const st = [];
    if (b.shield) st.push('🛡護盾 ' + b.shield);
    if (b.formation) st.push('☯' + ({ju: '聚靈陣', kun: '困敵陣', sha: '殺陣', hu: '護體陣'}[b.formation.id]) + ' ' + b.formation.turns + '回合');
    if (b.mirror) st.push('🪞照妖鏡');
    if (st.length) { g.fillStyle = '#000a'; g.fillRect(16, 82, 250, 22); label(st.join('　'), 141, 98, '#9fe', 12); }
    if (b.exhausted && !b.down) label('靈力耗盡！只能逃跑或服丹', 141, 122, '#ff8a8a', 14);
    if (b.down) label('氣血耗盡……只有元嬰出竅能保命', 141, 122, '#ff5a5a', 15);
  }
  cv.addEventListener('click', ev => {
    if (!S || !S.battle) return;
    const r = cv.getBoundingClientRect(), x = (ev.clientX - r.left) * VW / r.width, y = (ev.clientY - r.top) * VH / r.height;
    S.battle.enemies.forEach((e, i) => { if (!e.dead && Math.abs(x - (660 + i * 95)) < 70 && y > 190 + i * 46 && y < 420 + i * 46) bt.target = i; });
  });
  function btUI() {
    const b = S.battle, p = $('bt');
    if (!b) { p.style.display = 'none'; return; }
    const k = JSON.stringify([b.stance, b.stanceLocked, b.over, b.turn, S.hp, S.mp, S.heal, S.mpills, b.log.length, bt.menu, b.down, b.shield, b.cd, b.formation, (S.bag || []).map(x => x.n).join()]);
    if (p._k === k) return; p._k = k;
    p.style.display = 'block';
    let h = `<div id=btlog>${b.log.map(x => '<div>' + x + '</div>').join('')}</div>`;
    const bag = cat => (S.bag || []).filter(x => x.cat === cat);
    const back = '<button onclick="TD.menu(null)">返回</button>';
    if (b.over) {
      const t = {win: '🏆 戰鬥勝利', lose: '💀 你敗下陣來', flee: '💨 逃脫成功', soul: '🌀 元嬰出竅，遁走保命'}[b.over];
      h += `<div class=row><b style="font-size:18px">${t}</b><button onclick="TD.btEnd()">確定</button></div>`;
    } else if (b.down) {
      h += '<div class=row><b style="color:#ff8a8a">氣血耗盡，動彈不得！</b><button style="font-size:17px;background:#3a2a5a" onclick="TD.cmd(\'soul\')">🌀 元嬰出竅（保住性命，靈力歸零、略損靈石）</button></div>';
    } else if (bt.menu === 'spell') {
      h += '<div class=row><b>選擇五行法術：</b>' + S.elements.map((e, i) => `<button ${S.mp < b.spellCost ? 'disabled' : ''} style="color:${ECOL[e]}" onclick="TD.cmd('spell',${i})">${e}（-${b.spellCost}靈力）</button>`).join('') + back + '</div>';
    } else if (bt.menu === 'talisman' || bt.menu === 'formation') {
      const cat = bt.menu === 'talisman' ? '符錄' : '陣法', l = bag(cat);
      h += `<div class=row><b>${cat}：</b>` + (l.length ? l.map(x => `<button title="${x.desc}" onclick="TD.cmd('${bt.menu}','${x.id}')">${x.name} ×${x.n}</button>`).join('') : '<span style="color:#aaa">（儲物袋裡沒有，可到丹藥鋪購買或從強敵身上奪取）</span>') + back + '</div>';
    } else if (bt.menu === 'treasure') {
      const l = bag('法寶');
      h += '<div class=row><b>法寶：</b>' + (l.length ? l.map(x => { const cd = (b.cd || {})[x.id] || 0; return `<button title="${x.desc}" ${cd ? 'disabled' : ''} onclick="TD.cmd('treasure','${x.id}')">${x.name}${cd ? '（冷卻 ' + cd + '）' : ''}</button>`; }).join('') : '<span style="color:#aaa">（還沒有法寶）</span>') + back + '</div>';
    } else {
      const ex = b.exhausted, dis = ex ? 'disabled' : '', gear = b.boss ? `<button ${dis} onclick="TD.menu('formation')">☯ 陣法</button><button ${dis} onclick="TD.menu('talisman')">📜 符錄</button><button ${dis} onclick="TD.menu('treasure')">🗡 法寶</button>` : '';
      h += `<div class=row><button ${dis} onclick="TD.cmd('attack')">⚔ 劍擊(-${b.attackCost})</button><button ${dis} onclick="TD.menu('spell')">✦ 法術</button>${gear}<button ${S.heal ? '' : 'disabled'} onclick="TD.cmd('item')">💊 回春丹 ×${S.heal}</button><button ${S.mpills ? '' : 'disabled'} onclick="TD.cmd('mpill')">🔮 聚氣丹 ×${S.mpills}</button><button ${dis} onclick="TD.cmd('guard')">🛡 防禦</button><button onclick="TD.cmd('flee')">💨 逃跑</button>${b.boss ? '<small style="margin-left:10px;color:#e8a020">主要對手戰：可用陣法、符錄、法寶</small>' : '<small style="margin-left:10px">點擊敵人可選目標</small>'}</div>`;
    }
    if (!b.over && !b.down && b.allies && b.allies.length && !bt.menu) h += `<div class=row style="margin-top:4px;font-size:13px"><b>夥伴戰術：</b>${Object.entries(b.stances).map(([k, v]) => `<button ${b.stance === k ? 'disabled' : ''} title="${v.desc}${b.stanceLocked ? '（本回合已調整過）' : ''}" onclick="TD.stance('${k}')">${v.name}</button>`).join('')}<small style="color:#aaa">${b.stances[b.stance].desc}　（切換不耗回合，每回合限一次）</small></div>`;
    p.innerHTML = h;
    const l = $('btlog'); l.scrollTop = 1e6;
  }

  // ------------------------------------------------ HUD
  function ui() {
    const q = S.quest.quests.find(x => x.state === 'active');
    $('quest').innerHTML = q ? `<b>▶ ${q.name}</b>` + q.objectives.filter(o => o.state !== 'locked').map(o => `<div>${o.state === 'done' ? '☑' : '☐'} ${o.text}${o.progress && o.state === 'active' ? ' <small>(' + o.progress + ')</small>' : ''}</div>`).join('') : (S.quest.done ? '全部任務完成' : '');
    const nl = (S.news || []).filter(n => !n.resolved);
    $('quest').innerHTML += nl.length ? '<div style="margin-top:6px;border-top:1px solid #654;padding-top:4px"><b style="color:#ffd24a">📰 傳聞</b>' + nl.map(n => `<div style="font-size:12px;color:#ddd">${n.text}<small style="color:#999">（剩 ${n.left} 日）</small></div>`).join('') + '</div>' : '';
    $('quest').style.display = S.battle ? 'none' : 'block';
    $('top').innerHTML = `<b>${S.name}</b><span>${S.realm}·${S.sub}</span><span>Lv ${S.level}/${S.cap}${S.bottleneck ? ' <b style=color:#e6a>【瓶頸→按突破】</b>' : ''}</span>
      <span>氣血 <span class=bar><i style="width:${100 * S.hp / S.max_hp}%;background:#c44"></i></span> ${S.hp}/${S.max_hp}</span>
      <span>靈力 <span class=bar><i style="width:${100 * S.mp / S.max_mp}%;background:#48c"></i></span> ${S.mp}/${S.max_mp}</span>
      <span>靈石 ${S.lingshi}　突破丹 ${S.pills}　回春丹 ${S.heal}　聚氣丹 ${S.mpills}　靈草 ${S.herbs}　靈液 ${S.lingye}</span><span>功法：${S.gongfa.length ? S.gongfa.map(x => x.name).join('、') : '無'}</span><span>第 ${S.day} 日・${S.region_name}</span><span style="color:#aaa">難度：${S.difficultyName}</span><span title="殺業高會引來仇家；善緣高會有故人相助；破境前的心魔由道心決定">道心：<b style="color:${S.karma.state === 'sha' ? '#ff7a7a' : S.karma.state === 'ren' ? '#7dff9a' : '#ddd'}">${S.karma.dao}</b>（殺 ${S.karma.sha}／善 ${S.karma.ren}）</span>${S.members.length ? '<span title="' + S.members.map(m => m.name + '：' + m.desc).join('\n') + '">門派：' + S.members.map(m => m.name).join('、') + '</span>' : ''}${S.partner ? '<span style="color:#ffb0cc">♥ 道侶：' + S.partner.name + '</span>' : ''}`;
    const d = S.dialogue, dl = $('dlg');
    const dk = JSON.stringify(d);
    if (dk !== dl._k) {
      dl._k = dk; dl.style.display = d ? 'block' : 'none';
      if (d) { dl.innerHTML = `<canvas id=pt class=pt width=40 height=52></canvas><div class=sp>${d.speaker}</div><div class=tx>${d.text}</div>` + (d.cont ? `<button onclick="TD.post('choose')">▶ 繼續</button>` : d.choices.map(c => `<button onclick="TD.post('choose',{i:${c.i}})">${c.text}</button>`).join('')); Art.portrait($('pt'), d.speaker, S); }
    }
    panels();
    $('logp').innerHTML = S.log.slice(-4).map(x => '<div>' + x + '</div>').join('');
    btUI();
  }
  const lst = (id, html) => { const p = $(id); if (p._h !== html) { p._h = html; p.innerHTML = html; } p.style.display = html ? 'block' : 'none'; };
  function panels() {
    const sh = S.shop;
    lst('shop', sh ? `<b>${sh.name}</b>${sh.greeting ? `<div style="font-size:13px;color:#e8c060;margin:4px 0">「${sh.greeting}」</div>` : ''}<div style="font-size:13px;margin:4px 0">靈石 ${sh.lingshi}</div>` +
      sh.items.map(i => `<div class=row2><span>${i.name}　<b>${i.price}</b> 靈石${i.left !== null ? '（今日剩 ' + i.left + '）' : ''}</span><button ${i.left === 0 ? 'disabled' : ''} onclick="TD.post('buy',{item:'${i.id}'})">買</button></div>`).join('') +
      (sh.sells.length ? '<div style="margin-top:6px;font-size:13px;color:#aaa">— 收購 —</div>' + sh.sells.map(i => `<div class=row2><span>${i.name}×${i.have}　${i.price} 靈石</span><button onclick="TD.post('sell',{item:'${i.id}'})">賣一個</button></div>`).join('') : '') +
      (sh.kind === 'shady' ? `<div style="margin-top:6px">${sh.appraised ? `<div style="color:#ffd97a;font-size:13px">🔍 ${sh.appraised}</div>` : `<button onclick="TD.post('appraise')">🔍 請人鑑定這批貨（${sh.appraise_cost} 靈石）</button>`}</div>` : '') +
      '<button style="margin-top:6px" onclick="TD.post(\'shop_close\')">離開</button>' : '');
    const cx = S.codex;
    const cxLock = '<div style="color:#aaa;font-size:13px;margin:8px 0">你還沒有這本圖錄。可到丹藥鋪購買，或在洞窟守護者、強敵身上、天降異寶與寶箱裡找到。</div>';
    const cxTabs = `<button ${codexTab === 'beast' ? 'disabled' : ''} onclick="TD.codex('beast')">妖獸圖錄${cx && cx.beast.owned ? ' ' + cx.beast.found + '/' + cx.beast.total : '（未取得）'}</button><button ${codexTab === 'pet' ? 'disabled' : ''} onclick="TD.codex('pet')" style="margin-left:6px">靈寵圖鑑${cx && cx.pet.owned ? ' ' + cx.pet.found + '/' + cx.pet.total : '（未取得）'}</button>`;
    const kn = {wolf: '青狼', spider: '毒蛛', bear: '鐵背熊', snake: '赤焰蛇', python: '碧水蟒', ape: '山魈', bat: '血翼蝠'};
    let cxBody = '';
    if (cx && codexOpen) {
      if (codexTab === 'beast') {
        const b = cx.beast;
        cxBody = !b.owned ? cxLock : '<div style="margin-top:6px;color:#e6b45a;font-size:13px">— 妖獸 —</div>' + b.entries.map(e => e.known ? `<div style="margin:6px 0;font-size:13px"><b>${e.name}</b> <small style="color:#999">遇過 ${e.seen} 次</small><br>${e.desc}<br><small style="color:#aaa">棲地：${e.habitat}</small><br><small style="color:#9fe">要領：${e.tip}</small>${e.elements.length ? '<br><small>已見屬性：' + e.elements.map(x => `<span style="color:${ECOL[x.el]}">${x.el}</span>（弱點 ${x.weak.join('')}）`).join('　') + '</small>' : ''}</div>` : '').join('') + (b.entries.some(e => !e.known) ? `<div style="margin:6px 0;color:#666;font-size:13px">？？？ ×${b.entries.filter(e => !e.known).length}　<small>（尚未遇過的妖獸）</small></div>` : '') +
          '<div style="margin-top:8px;color:#e6b45a;font-size:13px">— 強敵 —</div>' + b.bosses.map(e => e.known ? `<div style="margin:6px 0;font-size:13px"><b style="color:#ff9a6a">★ ${e.name}</b> <small style="color:#999">交手 ${e.seen} 次　屬性 <span style="color:${ECOL[e.el] || '#ccc'}">${e.el}</span>${e.weak.length ? '（弱點 ' + e.weak.join('') + '）' : ''}</small><br>${e.lore}<br><small style="color:#e8a">招式：${e.skills.join('、')}</small><br><small style="color:#9fe">要領：${e.tip}</small></div>` : '').join('') + (b.bosses.some(e => !e.known) ? `<div style="margin:6px 0;color:#666;font-size:13px">？？？ ×${b.bosses.filter(e => !e.known).length}　<small>（尚未交手的強敵）</small></div>` : '');
      } else {
        const p = cx.pet;
        cxBody = !p.owned ? cxLock : p.entries.map(e => e.known ? `<div style="margin:6px 0;font-size:13px"><b>${kn[e.id] ? e.stages[0] + '系' : e.id}</b>：${e.stages.join(' → ')}<br><small style="color:#ffd24a">✦ ${e.skill.name}（${e.skill.unlock} 級進化後習得，冷卻 ${e.skill.cd.join('→')} 回合）</small><br><small style="color:#ccc">${e.skill.desc}${e.skill.strong !== e.skill.desc ? '<br>強化後：' + e.skill.strong : ''}</small><br><small style="color:#9fe">${e.tip}</small></div>` : `<div style="margin:6px 0;color:#666;font-size:13px">？？？　<small>（尚未養過這種靈寵）</small></div>`).join('');
      }
    }
    lst('codex', codexOpen && cx ? '<b>📖 圖錄</b> <small style="color:#999">（G 開關）</small><div style="margin:6px 0">' + cxTabs + '</div>' + cxBody + '<button style="margin-top:8px" onclick="TD.codex()">關閉（G）</button>' : '');
    const wr = S.war;
    lst('war', wr ? `<b style="color:#ff8a6a">⚔ ${wr.title}</b><div style="font-size:14px;margin:6px 0">${wr.text}</div><div style="font-size:12px;color:#aaa;margin-bottom:6px">${wr.member ? '你是「' + wr.sect + '」的弟子。' : ''}選擇你的立場：</div>` +
      wr.options.map(o => `<div style="margin:6px 0"><button ${o.ok ? '' : 'disabled'} onclick="TD.post('war_side',{side:'${o.k}'})"><b>${o.title}</b></button><div style="font-size:12px;color:#bbb">${o.desc}</div></div>`).join('') : '');
    const cp = S.comp;
    const pupCard = (x, i, act) => {                       // act: 出戰中(active) / 留守(bench)
      const q = act ? '' : `,i:${i}`;
      return `<div style="border:1px solid #4a4030;border-radius:6px;padding:6px 8px;margin:6px 0"><div class=row2 style="flex-wrap:wrap"><span><b>${x.name}</b> ${x.level} 階${x.broken ? ' <b style="color:#f88">破損</b>' : ''}<br><small style="color:#999">耐久 ${x.hp}/${x.maxhp}　攻擊 ×${x.atk}　擋招 ${Math.round(x.absorb * 100)}%</small>${x.skill ? `<br><small style="color:${x.skill.unlocked ? '#9fe' : '#777'}">✦ 「${x.skill.name}」${x.skill.unlocked ? '：' + x.skill.desc + '　冷卻 ' + x.skill.cd + ' 回合' : '（' + x.skill.unlock_level + ' 階習得）'}</small>` : ''}</span><span>` +
        (act ? '<button onclick="TD.post(\'puppet_stow\')">留守</button>' : `<button onclick="TD.post('puppet_equip',{i:${i}})">換上出戰</button>`) +
        `${x.repair ? `<button onclick="TD.post('puppet_repair',{${q.slice(1)}})">修理（${x.repair}）</button>` : ''}${x.upgrade ? `<button onclick="TD.post('puppet_upgrade',{${q.slice(1)}})">升階（${x.upgrade}）</button>` : ''}<button onclick="TD.post('puppet_scrap',{${q.slice(1) || 'i:-1'}})">拆解</button></span></div>` +
        `<div style="font-size:12px;color:#e6b45a;margin-top:4px">改造（${x.mods.length}/${x.slots} 槽）</div>` + (x.mods.length ? x.mods.map((m, k) => `<div class=row2><span><b>${m.name}</b><small style="color:#999"> ${m.desc}</small></span><button onclick="TD.post('puppet_unmod',{slot:${k}${q}})">拆下</button></div>`).join('') : '<div style="font-size:12px;color:#777">尚未裝上任何改造。</div>') +
        (act ? Object.entries(x.mod_shop).filter(([k, v]) => !v.installed).map(([k, v]) => `<div class=row2><span>${v.name}<small style="color:#999"> ${v.desc}${v.ok ? '' : '（需 ' + v.level + ' 階）'}</small></span><button ${v.ok ? '' : 'disabled'} onclick="TD.post('puppet_mod',{mod:'${k}'${x.mods.length >= x.slots ? ',slot:0' : ''}})">${x.mods.length >= x.slots ? '替換槽1 ' : '裝上 '}${v.cost}</button></div>`).join('') : '<div style="font-size:11px;color:#777">（換上出戰後可加裝改造）</div>') + '</div>';
    };
    const petCard = (x, i, act) => `<div style="border:1px solid #4a4030;border-radius:6px;padding:6px 8px;margin:6px 0"><div class=row2><span><b>${x.name}</b>（${x.el}）Lv${x.level}/${x.max}　${x.stage >= 2 ? '★完全體' : x.stage === 1 ? '進化型' : '幼體'}<br><small style="color:#999">經驗 ${x.exp}/${x.need}</small><br><small style="color:${x.skill.unlocked ? '#9fe' : '#777'}">✦ 「${x.skill.name}」${x.skill.unlocked ? (x.skill.upgraded ? '（強化）' : '') + '：' + x.skill.desc + ` 冷卻 ${x.skill.cd} 回合` : x.skill.hidden ? '' : `（${x.skill.unlock_level} 級進化後習得）`}</small></span><span>` +
      (act ? '<button onclick="TD.post(\'pet_stow\')">留守</button>' : `<button onclick="TD.post('pet_equip',{i:${i}})">換上出戰</button>`) +
      `<button ${cp.herbs && x.level < x.max ? '' : 'disabled'} onclick="TD.post('pet_feed'${act ? '' : ',{i:' + i + '}'})">餵靈草 (${cp.herbs})</button><button onclick="TD.post('pet_release'${act ? '' : ',{i:' + i + '}'})">放生</button></span></div></div>`;
    lst('comp', compOpen && cp ? '<b>🐾 夥伴・出戰配置</b>' +
      `<div style="margin:6px 0;font-size:13px"><b>出戰戰術：</b>${Object.entries(cp.stances).map(([k, v]) => `<button ${cp.stance === k ? 'disabled' : ''} title="${v.desc}" onclick="TD.post('stance',{mode:'${k}'})">${v.name}</button>`).join('')}<div style="font-size:12px;color:#aaa">${cp.stances[cp.stance].desc}</div></div>` +
      `<div style="font-size:12px;color:#9d9;margin:4px 0">本次出戰：${cp.pet ? cp.pet.name : '（無靈寵）'} ＋ ${cp.puppet ? cp.puppet.name : '（無傀儡）'}</div>` +
      `<div style="margin-top:8px;color:#e6b45a;font-size:13px">— 出戰靈寵 —</div>` + (cp.pet ? petCard(cp.pet, -1, true) : '<div style="font-size:13px;color:#aaa">出戰位空著。從下方留守的靈寵中挑一隻，或孵化靈獸蛋。</div>') +
      `<div style="font-size:12px;color:#e6b45a;margin-top:6px">留守靈寵（${cp.pet_bench.length}/${cp.pet_cap}；每 2 場勝利也會成長）</div>` + cp.pet_bench.map((x, i) => petCard(x, i, false)).join('') +
      (cp.eggs ? `<button onclick="TD.post('use',{item:'pet_egg'})">孵化靈獸蛋 ×${cp.eggs}</button>` : '') +
      `<div style="margin-top:10px;color:#e6b45a;font-size:13px">— 出戰傀儡 —</div>` + (cp.puppet ? pupCard(cp.puppet, -1, true) : '<div style="font-size:13px;color:#aaa">出戰位空著。</div>') +
      `<div style="font-size:12px;color:#e6b45a;margin-top:6px">傀儡庫（${cp.puppet_bench.length}/${cp.puppet_cap}）</div>` + cp.puppet_bench.map((x, i) => pupCard(x, i, false)).join('') +
      `<div style="font-size:12px;color:#aaa;margin-top:6px">煉製新傀儡（先進出戰位，出戰位有人時進傀儡庫）：</div>` + Object.entries(cp.build).map(([k, v]) => `<div class=row2><span>${v.name}<small style="color:#999"> ${v.desc}${v.ok ? '' : '（需 ' + S.realms[v.realm] + '）'}</small></span><button ${v.ok ? '' : 'disabled'} onclick="TD.post('puppet_build',{ptype:'${k}'})">${v.cost} 靈石</button></div>`).join('') +
      '<button style="margin-top:6px" onclick="TD.comp()">關閉（P）</button>' : '');
    const al = S.alch;
    lst('alch', al ? `<b>🔥 煉製${al.name}</b> <small>第 ${Math.min(al.round + 1, al.rounds)}/${al.rounds} 回合　得分 ${al.score}/${al.maxScore}</small>` +
      `<div style="position:relative;height:26px;background:#222;border-radius:6px;margin:10px 0;overflow:hidden"><div style="position:absolute;left:32%;width:36%;top:0;bottom:0;background:#5a4a10"></div><div style="position:absolute;left:42%;width:16%;top:0;bottom:0;background:#3a7a2a"></div><div style="position:absolute;left:${al.heat}%;top:-2px;bottom:-2px;width:5px;margin-left:-2px;background:#ff5a2a;box-shadow:0 0 8px #f80"></div></div>` +
      `<div style="font-size:13px;color:#ccc">爐溫 ${al.heat}（綠區＝完美、黃區＝尚可；0 或 100 會炸爐）</div>` +
      (al.over ? `<div style="margin:10px 0;font-size:16px;color:${al.tier ? '#9fe' : '#f88'}">${al.result}</div><button onclick="TD.post('alch_close')">收爐</button>`
        : `<div style="margin:8px 0;color:#ffd97a">火勢變化：${al.trend.dir > 0 ? '漸旺 ↑' : al.trend.dir < 0 ? '漸弱 ↓' : '平穩'}（${al.trend.size}）</div>` +
          [['cool2', '❄❄ 大減火'], ['cool', '❄ 減火'], ['hold', '＝ 維持'], ['heat', '🔥 添火'], ['heat2', '🔥🔥 大添火']].map(([k, t]) => `<button onclick="TD.post('alch_act',{a:'${k}'})">${t}</button>`).join('') +
          (al.hist.length ? '<div style="margin-top:8px;font-size:12px;color:#999">' + al.hist.map((h, i) => `第${i + 1}回 → ${h.heat}（+${h.score}）`).join('　') + '</div>' : '')) : '');
    const bgs = S.bag || [];
    lst('bag', bagOpen ? '<b>🎒 儲物袋</b> <small style="color:#9d9">容量：無限</small>' + ['錢財', '丹藥', '材料', '圖錄', '符錄', '陣法', '法寶'].map(c => { const l = bgs.filter(x => x.cat === c); return l.length ? `<div style="margin-top:8px;color:#e6b45a;font-size:13px">— ${c} —</div>` + l.map(x => x.cat === '法寶' ? `<div class=row2 style="flex-wrap:wrap"><span title="${x.desc}"><b>${x.name}</b> ${x.level}階${x.bonded ? ' <b style="color:#ffd24a">★本命</b>' : ''}<small style="color:#999"> ${x.desc}</small>${x.awaken ? `<br><small style="color:${x.level >= 3 ? '#9fe' : '#777'}">${x.awaken}${x.level >= 3 ? '（已覺醒）' : '（3 階覺醒）'}</small>` : ''}</span><span>${x.refine ? `<button onclick="TD.post('fb_refine',{item:'${x.id}'})">祭煉（${x.refine.lingshi} 靈石${x.refine.lingye ? '＋靈液' : ''}）</button>` : '<small>已達上限</small>'}${x.bonded ? '' : `<button onclick="TD.post('fb_bond',{item:'${x.id}'})">設為本命</button>`}</span></div>` : `<div class=row2><span title="${x.desc}">${x.name} <b>×${x.n}</b><small style="color:#999"> ${x.desc}</small></span>${x.use === 'codex' ? `<button onclick="TD.codex('${x.id === 'codex_pet' ? 'pet' : 'beast'}')">翻閱</button>` : x.use ? `<button onclick="TD.post('use',{item:'${x.id}'})">使用</button>` : ''}</div>`).join('') : ''; }).join('') + `<div style="margin-top:8px;font-size:12px;color:#aaa">符錄、陣法、法寶只能在主要對手戰中使用。儲存點：${S.checkpoint || '無'}</div><button style="margin-top:6px" onclick="TD.bag()">關閉（B）</button>` : '');
    const bd = S.board;
    lst('board', bd ? `<b>📜 布告欄</b><div style="font-size:15px;margin:6px 0;color:#ffe9a6">${bd.title}</div>` +
      bd.offers.map(o => `<div class=offer><span>${o.give_txt} ⇒ <b>${o.get_txt}</b>${o.done ? '（已完成）' : ''}</span><button ${o.ok ? '' : 'disabled'} onclick="TD.post('barter',{idx:${o.id}})">交換</button></div>`).join('') +
      (bd.recruit ? `<div style="margin-top:10px;border-top:1px solid #654;padding-top:6px"><b>📯 宗門招募</b><div style="font-size:14px;margin:4px 0">「${bd.recruit.name}」（${bd.recruit.align}）廣招弟子！<br>福利：<b>${bd.recruit.perk}</b> — ${bd.recruit.desc}</div><button onclick="TD.post('join',{sect:'${bd.recruit.sect}'})">加入（入門費 ${bd.recruit.fee} 靈石）</button></div>` : '<div style="margin-top:8px;font-size:13px;color:#aaa">（目前沒有適合你的宗門招募）</div>') +
      (bd.members.length ? `<div style="margin-top:8px;font-size:13px;color:#bbb">你的宗門：${bd.members.map(m => m.name).join('、')}</div>` : '') +
      '<button style="margin-top:8px" onclick="TD.post(\'board_close\')">關上</button>' : '');
    const cd = S.cand;
    lst('cand', cd ? `<b style="color:#ffb0cc">♥ ${cd.name}</b><div class=aff><i style="width:${Math.min(100, cd.affinity)}%"></i></div><div style="font-size:13px">好感 ${cd.affinity}／100${cd.affinity >= 100 ? (S.realm_index >= cd.need_realm ? '　（她似乎有話想對你說……明天再來）' : '　（需要更高的境界才能求緣）') : ''}</div>` +
      '<div style="margin:8px 0 2px;font-size:13px;color:#aaa">' + (cd.gifted ? '今天已經送過禮物了' : '送她一份禮物：') + '</div>' +
      cd.gifts.map(g => `<div class=row2><span>${g.name}×${g.have}${g.like ? ' <b style="color:#ff9ab8">♥她喜歡</b>' : ''}　好感+${g.gain}</span><button ${cd.gifted || !g.have ? 'disabled' : ''} onclick="TD.post('gift',{item:'${g.id}'})">送出</button></div>`).join('') +
      `<button style="margin-top:6px" ${cd.chatted ? 'disabled' : ''} onclick="TD.post('chat')">💬 閒聊（好感+3）</button><button onclick="TD.post('cand_close')">離開</button>` : '');
    $('mini').style.display = MAP.kind === 'world' && !S.battle ? 'block' : 'none';
  }
  const tgtEnt = () => {
    if (!S.target || MAP.kind !== 'world') return null;
    if (S.target.loc) { const e = ents.find(e => e.k === 'enter' && e.loc === S.target.loc); if (e) return {x: (e.x + .5) * TS, y: (e.y + .5) * TS}; }
    if (S.target.region && S.target.region !== S.region && MAP.centers[S.target.region]) { const c = MAP.centers[S.target.region]; return {x: c[0] * TS, y: c[1] * TS, region: true}; }
    return null;
  };
  function hud() {
    let p = '';
    if (MAP.kind === 'loc') { const n = nearest(); if (n) p = 'E：' + n.text; }
    $('prompt').textContent = S.battle || S.dialogue ? '' : p;
    if (MAP.kind === 'world' && minimapBase) {
      const m = $('mini').getContext('2d'), k = 150 / Math.max(MAP.w, MAP.h); m.imageSmoothingEnabled = false; m.clearRect(0, 0, 150, 150); m.drawImage(minimapBase, 0, 0, MAP.w * k, MAP.h * k);
      for (const e of ents) if (e.k === 'enter') { m.fillStyle = e.icon === 'icon_cave' ? '#c6f' : e.icon === 'icon_garden' ? '#4f4' : '#f33'; m.fillRect(e.x * k - 1, e.y * k - 1, 3, 3); }
      const t = tgtEnt(); if (t && Math.floor(now / 300) % 2) { m.fillStyle = '#ff0'; m.fillRect(t.x / TS * k - 3, t.y / TS * k - 3, 6, 6); }
      m.fillStyle = '#fff'; m.fillRect(hero.x / TS * k - 2, hero.y / TS * k - 2, 4, 4);
    }
  }

  // ------------------------------------------------ 主繪製
  function draw() {
    if (!S || !MAP || !Art.td) return;
    g.imageSmoothingEnabled = false;
    if (S.battle) { drawBattle(); return; }
    const camX = MAP.w * TS <= VW ? -(VW - MAP.w * TS) / 2 : Math.max(0, Math.min(MAP.w * TS - VW, hero.x - VW / 2));
    const camY = MAP.h * TS <= VH ? -(VH - MAP.h * TS) / 2 : Math.max(0, Math.min(MAP.h * TS - VH, hero.y - VH / 2));
    const cam = {x: Math.round(camX), y: Math.round(camY)};
    lastCam = cam;
    g.fillStyle = '#000'; g.fillRect(0, 0, VW, VH);
    const x0 = Math.max(0, Math.floor(cam.x / TS)), y0 = Math.max(0, Math.floor(cam.y / TS)), x1 = Math.min(MAP.w - 1, x0 + Math.ceil(VW / TS) + 1), y1 = Math.min(MAP.h - 1, y0 + Math.ceil(VH / TS) + 1);
    for (let ty = y0; ty <= y1; ty++) for (let tx = x0; tx <= x1; tx++) groundTile(tx, ty, cam);
    const list = [];
    const bio = MAP.biome;
    for (const o of MAP.objects) {
      const s = MAP.objScale[o.t] || 1, ax = (o.x + .5) * TS - cam.x, ay = (o.y + 1) * TS - cam.y;
      if (ax < -200 || ax > VW + 200 || ay < -40 || ay > VH + 240) continue;
      list.push({y: (o.y + 1) * TS, f: () => { let n = o.t; if (n === 'campfire0') n = 'campfire' + (Math.floor(now / 200) % 2); if (n === 'chest_c') { const c = ents.find(e => e.k === 'chest' && e.x === o.x && e.y === o.y); if (c && S.opened.includes(c.id)) n = 'chest_o'; } drawObj(bio, n, ax, ay, s); }});
    }
    for (const e of ents) {
      const ax = e.px - cam.x, ay = e.py - cam.y;
      if (ax < -100 || ax > VW + 100 || ay < -100 || ay > VH + 100) continue;
      if (e.k === 'enter') list.push({y: (e.y + 1) * TS, f: () => { const zb = e.region || 'tiannan', ix = (e.x + .5) * TS - cam.x, iy = (e.y + 1) * TS - cam.y; drawObj(zb, e.icon, ix, iy, 1); label(e.name, ix, iy + 13, '#fff', 12); const nw = (S.news || []).find(n => n.loc === e.loc && !n.resolved); if (nw) label(nw.kind === 'entity' ? '❗' : '✦', ix, iy - 44 + Math.sin(now / 250) * 4, '#ffd24a', 22); }});
      else if (e.k === 'dock') list.push({y: (e.y + 1) * TS, f: () => { drawObj(e.region === 'luanxinghai' ? 'luanxinghai' : 'tiannan', 'dock', (e.x + .5) * TS - cam.x, (e.y + 1) * TS - cam.y, 1); label('渡口', (e.x + .5) * TS - cam.x, (e.y + 1) * TS - cam.y + 12, '#9df', 12); }});
      else if (e.k === 'plot') list.push({y: e.y * TS + 10, f: () => { const st = S.plots[e.id] || {stage: 0}, ix = (e.x + .5) * TS - cam.x, iy = (e.y + 1) * TS - cam.y - 2; drawObj(bio, 'plot' + st.stage, ix, iy, 1); if (st.stage === 3) label('可收成', ix, iy - 28 + Math.sin(now / 250) * 2, '#ffe36a', 11); else if (st.stage > 0) label(st.left + '日', ix, iy - 26, '#cfe', 10); }});
      else if (e.k === 'npc') list.push({y: e.py, f: () => drawNPC(e.npc, ax, ay, e.face || 'd', e.moving)});
      else if (e.k === 'candidate') list.push({y: e.py, f: () => { drawNPC(e.npc, ax, ay, hero.x < e.px ? 'l' : 'r', false); label(e.name, ax, ay + 14, '#ffc0d8', 12); const a = S.affinity[e.cid] || 0; label(S.partner && S.partner.id === e.cid ? '♥ 道侶' : (a > 0 ? '♥' + a : '♡'), ax, ay - 62 + Math.sin(now / 300) * 2, '#ff7aa8', 14); }});
      else if (e.k === 'guardian' && !(S.guardians || []).includes(S.cur_loc)) list.push({y: (e.y + 1) * TS, f: () => { const gx = (e.x + .5) * TS - cam.x, gy = (e.y + 1) * TS - cam.y; shadow(gx, gy + 2, 40); drawBeast(e, gx, gy, 2.2, false, Math.floor(now / 250) % 4); label('★ ' + e.name, gx, gy - 100, '#ff9a5a', 14); label(S.codex && S.codex.beast.owned ? e.el : '？', gx, gy - 116, S.codex && S.codex.beast.owned ? ECOL[e.el] : '#ccc', 14); }});
      else if (e.k === 'well') list.push({y: (e.y + 1) * TS + 1, f: () => label('💾', (e.x + .5) * TS - cam.x, e.y * TS - cam.y - 22 + Math.sin(now / 400) * 2, '#9df', 16)});
      else if (e.k === 'enemy' && !S.defeated.includes(e.id)) list.push({y: e.py, f: () => { const B = Art.man.beasts; drawBeast(e, ax, ay, 1, (e.dir || 1) < 0); label(S.codex && S.codex.beast.owned ? e.el : '？', ax, ay - 46 - (e.kind === 'bat' ? 26 : 0), S.codex && S.codex.beast.owned ? ECOL[e.el] : '#ccc', 13); if ((cool['f' + e.id] || 0) > now) { g.globalAlpha = .6; label('…', ax, ay - 60, '#fff', 14); g.globalAlpha = 1; } }});
    }
    if (MAP.kind === 'loc' && S.wev_ent) { const w = S.wev_ent, ax = (w.x + .5) * TS - cam.x, ay = (w.y + .9) * TS - cam.y; list.push({y: (w.y + .9) * TS, f: () => { if (w.sprite) { drawNPC(w.sprite, ax, ay, hero.x < (w.x + .5) * TS ? 'r' : 'l', false); label(w.name, ax, ay + 14, '#ffe08a', 12); } else { g.globalAlpha = .6 + .3 * Math.sin(now / 200); g.fillStyle = '#ffe08a'; g.beginPath(); g.ellipse(ax, ay - 6, 16, 8, 0, 0, 7); g.fill(); g.globalAlpha = 1; } label(w.label, ax, ay - 62 + Math.sin(now / 230) * 3, '#ffd24a', 26); }}); }
    if (MAP.kind === 'loc' && S.karma_ev) { const k = S.karma_ev, ax = (k.x + .5) * TS - cam.x, ay = (k.y + .9) * TS - cam.y, av = k.kind === 'avenger'; list.push({y: (k.y + .9) * TS, f: () => { drawNPC(k.sprite, ax, ay, hero.x < (k.x + .5) * TS ? 'r' : 'l', false); label(av ? '仇' : '恩', ax, ay - 62 + Math.sin(now / 240) * 3, av ? '#ff5a5a' : '#7dff9a', 26); label(k.name, ax, ay + 14, av ? '#ff9a9a' : '#b8ffc8', 12); }}); }
    if (MAP.kind === 'loc' && S.questNpc) { const q = questPos(), ax = q[0] - cam.x, ay = q[1] - cam.y, id = speakerSprite(S.questNpc); if (id) list.push({y: q[1], f: () => { drawNPC(id, ax, ay, hero.x < q[0] ? 'l' : 'r', false); label('!', ax, ay - 62 + Math.sin(now / 220) * 4, '#ffd24a', 30); label(S.questNpc, ax, ay + 14, '#ffe9a6', 12); }}); }
    if (S.comp && S.comp.pet && trail.length) { const t = trail[Math.max(0, trail.length - 4)], px = t.x - cam.x + 12, py = t.y - cam.y + 2, pt = S.comp.pet; list.push({y: t.y, f: () => { shadow(px, py + 1, 10); drawBeast({kind: pt.kind, el: pt.el}, px, py, .8, t.dir === 'l', hero.moving ? Math.floor(now / 160) % 4 : 0); }}); }
    list.push({y: hero.y, f: () => drawHero(cam)});
    list.sort((a, b) => a.y - b.y);
    for (const it of list) it.f();
    if (walk) { const mx = walk.gx - cam.x, my = walk.gy - cam.y, pr = 6 + (now / 120 % 6); g.strokeStyle = '#ffd24a'; g.lineWidth = 2; g.beginPath(); g.ellipse(mx, my + 4, pr + 6, (pr + 6) * .45, 0, 0, 7); g.stroke(); g.fillStyle = '#ffd24a'; g.beginPath(); g.ellipse(mx, my + 4, 4, 2, 0, 0, 7); g.fill(); }
    // 目標標記
    const bob = Math.sin(now / 250) * 5;
    if (MAP.kind === 'world') {
      const t = tgtEnt();
      if (t) {
        const sx = t.x - cam.x, sy = t.y - cam.y;
        if (sx > 24 && sx < VW - 24 && sy > 40 && sy < VH - 24) { if (!t.region) label('▼', sx, sy - 34 + bob, '#ffd24a', 28); else label('▼ ' + S.region_name, sx, sy, '#ffd24a', 20); }
        else { const a = Math.atan2(sy - VH / 2, sx - VW / 2), ex = VW / 2 + Math.cos(a) * 400, ey = VH / 2 + Math.sin(a) * 220, ex2 = Math.max(30, Math.min(VW - 30, ex)), ey2 = Math.max(60, Math.min(VH - 50, ey)); g.save(); g.translate(ex2, ey2); g.rotate(a); label('➤', 0, 8, '#ffd24a', 34); g.restore(); label(Math.round(Math.hypot(t.x - hero.x, t.y - hero.y) / TS) + ' 格', ex2, ey2 + 30, '#ffd24a', 13); }
      } else if (S.target && S.target.region && S.target.region !== S.region && S.target.region !== 'tianyuan') label('目標在「' + (S.world.find(w => w.id === S.target.region) || {name: ''}).name + '」，可到渡口搭船', VW / 2, 84, '#ffd24a', 15);
    } else if (S.target && S.target.loc && S.target.loc !== S.cur_loc) label('（目標不在這裡）', VW / 2, 84, '#ffd24a', 14);
  }
  function loop(t) { const dt = Math.min(.05, (t - last) / 1000); last = t; try { update(dt); draw(); } catch (e) { err('執行錯誤：' + e.message + ' ' + (e.stack || '').split('\n')[1]); } requestAnimationFrame(loop); }

  function openNew(first) {
    const a = $('ask'); askOpen = true; a.style.display = 'block'; a._opts = [{}];
    const diffs = Object.entries(S.difficulties);
    a.innerHTML = `<b style="font-size:18px">${first ? '歡迎來到凡人修仙傳' : '新遊戲（會覆蓋存檔）'}</b>
    <div style="margin:10px 0 4px;text-align:left"><b>難度</b></div>
    <div id=nd style="text-align:left">${diffs.map(([k, v]) => `<label style="display:block;margin:3px 0"><input type=radio name=dd value="${k}" ${k === (S.configured ? S.difficulty : 'normal') ? 'checked' : ''}> <b>${v.name}</b>　<small style="color:#bbb">${v.desc}</small></label>`).join('')}</div>
    <div style="margin:10px 0;text-align:left">名字：<input id=nn value="韓立" maxlength=8 style="font-size:15px"></div>
    <div style="margin:6px 0;text-align:left">靈根：<select id=nr style="font-size:15px">${S.roots.map(r => `<option value="${r.id}" ${r.id === 'quad' ? 'selected' : ''}>${r.name}（${r.count}屬性・速度 ×${r.speed}）</option>`).join('')}</select></div>
    <div id=ne style="margin:6px 0;text-align:left"></div><button id=nb1>開始遊戲</button><button id=nb2>原作模式（韓立・四靈根）</button>${first ? '' : '<button id=nb3>取消</button>'}`;
    const rootUI = () => { const r = S.roots.find(x => x.id === $('nr').value), list = r.elements || S.root_elements; $('ne').innerHTML = `屬性（選 ${r.count} 個）：` + list.map((e, i) => `<label style="margin-right:10px"><input type=checkbox class=ck value="${e}" ${i < r.count ? 'checked' : ''}> ${e}</label>`).join(''); };
    $('nr').onchange = rootUI; rootUI();
    const close = () => { a.style.display = 'none'; askOpen = false; };
    const diff = () => document.querySelector('input[name=dd]:checked').value;
    if ($('nb3')) $('nb3').onclick = close;
    $('nb2').onclick = () => { const d = diff(); close(); post('act', {c: 'new', diff: d}); };
    $('nb1').onclick = () => { const r = S.roots.find(x => x.id === $('nr').value), el = [...document.querySelectorAll('.ck:checked')].map(x => x.value); if (el.length !== r.count) { alert('請選擇剛好 ' + r.count + ' 個屬性'); return; } const nm = $('nn').value, d = diff(); close(); post('act', {c: 'new', name: nm, root: r.id, elems: el.join(''), diff: d}); };
  }

  async function boot() {
    await Art.init();
    if (!Art.ok) { err('美術素材載入失敗（/art/）'); return; }
    await Art.loadTD();
    await load();
    requestAnimationFrame(loop);
    if (S && !S.configured) openNew(true);
  }
  boot();
  window.__td = {get S() { return S; }, get MAP() { return MAP; }, hero, get ents() { return ents; }, post, load, get bt() { return bt; }};
  return {post, act, openNew, cmd: btCmd, btEnd, bag: toggleBag, comp: toggleComp, stance: mode => { if (!busy && S.battle && !S.battle.over) post('battle', {cmd: 'stance', arg: mode}); }, codex: toggleCodex, menu: v => { bt.menu = v; $('bt')._k = ''; btUI(); }, spellMenu: v => { bt.menu = v ? 'spell' : null; $('bt')._k = ''; btUI(); }};
})();
