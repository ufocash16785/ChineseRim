/* 像素美術繪製：載入 /art/ 下的素材；載入失敗時 Art.ok=false，遊戲退回向量圖形。 */
const Art = (() => {
  const A = {ok: false, img: {}, man: null, S: 2, biomes: {}};
  const load = src => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('載入失敗 ' + src)); i.src = src; });
  A.init = async () => {
    try {
      A.man = await (await fetch('/art/manifest.json')).json();
      for (const n of ['heroes', 'npcs', 'beasts', 'fx']) A.img[n] = await load('/art/' + n + '.png');
      A.ok = true;
    } catch (e) { A.ok = false; console.warn(e); }
  };
  A.ensureBiome = async b => {
    if (!A.ok || A.img['scene_' + b] || !A.man.biomes[b]) return;
    try { A.img['scene_' + b] = await load('/art/scene_' + b + '.png'); } catch (e) { A.ok = false; }
  };
  A.hasBiome = b => A.ok && !!A.img['scene_' + b];
  const rgb = h => [1, 3, 5].map(i => parseInt(h.substr(i, 2), 16));
  const mixc = (a, b, t) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(',')})`;
  const spr = (g, im, r, dx, dy, sc, flip, cx) => {
    if (flip) { g.save(); g.translate(cx, 0); g.scale(-1, 1); g.drawImage(im, r[0], r[1], r[2], r[3], cx - dx - r[2] * sc, dy, r[2] * sc, r[3] * sc); g.restore(); }
    else g.drawImage(im, r[0], r[1], r[2], r[3], dx, dy, r[2] * sc, r[3] * sc);
  };
  const hash = s => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
  const noise = x => { const a = Math.sin(x * 127.1) * 43758.5453; return a - Math.floor(a); };

  A.shadow = (g, x, y, w) => { g.fillStyle = 'rgba(0,0,0,.28)'; g.beginPath(); g.ellipse(x, y, w, w * .28, 0, 0, 7); g.fill(); };

  A.backdrop = (g, S, cam, W, H, GY, now) => {
    const b = A.man.biomes[S.region] || A.man.biomes.tiannan, sk = b.sky.map(rgb);
    const gr = g.createLinearGradient(0, 0, 0, GY); gr.addColorStop(0, mixc(sk[0], sk[0], 0)); gr.addColorStop(1, mixc(sk[1], sk[1], 0));
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
    g.fillStyle = 'rgba(255,255,255,.85)'; const sx = 780 - cam * .02; g.fillRect(sx - 14, 70, 28, 28); g.fillRect(sx - 18, 76, 36, 16); g.fillRect(sx - 10, 66, 20, 36);
    g.fillStyle = 'rgba(255,255,255,.55)';
    for (let i = 0; i < 6; i++) { const x = ((i * 260 + 40 - cam * .1 + now * .006 * (1 + i % 3)) % (W + 300) + W + 300) % (W + 300) - 150, y = 50 + (i * 47) % 110;
      g.fillRect(x, y, 80, 10); g.fillRect(x + 12, y - 8, 46, 10); g.fillRect(x + 20, y + 8, 60, 8); }
    for (const [f, k, a, hh] of [[.12, .35, .004, 170], [.32, .55, .007, 110]]) {
      g.fillStyle = mixc(sk[1], [30, 30, 60], k);
      for (let x = 0; x < W; x += 4) { const wx = x + cam * f; const h = Math.floor(hh * (.45 + .55 * Math.abs(Math.sin(wx * a) * Math.sin(wx * a * 2.3 + 1))) / 4) * 4; g.fillRect(x, GY - h, 4, h); }
    }
    // 近景：樹林剪影
    g.fillStyle = mixc(sk[1], [10, 20, 30], .6);
    for (let x = 0; x < W; x += 4) { const wx = x + cam * .6; const h = 28 + Math.floor(20 * noise(Math.floor(wx / 24))) ; g.fillRect(x, GY - h, 4, h); }
    // 地面
    const P = A.img['scene_' + S.region], r0 = b.rects.ground0, r1 = b.rects.ground1, T = 32 * A.S, top = GY - 6;
    const x0 = Math.floor(cam / T) * T;
    for (let x = x0; x < cam + W + T; x += T) {
      const rr = (Math.floor(x / T) % 3 == 0) ? r1 : r0;
      g.drawImage(P, rr[0], rr[1], rr[2], rr[3], x - cam, top, T, T);
      for (let y = top + T; y < H; y += 16 * A.S) g.drawImage(P, rr[0], rr[1] + 16, rr[2], 16, x - cam, y, T, 16 * A.S);
    }
  };
  // 以下皆在 translate(-cam) 的世界座標中繪製
  A.platform = (g, S, p) => {
    const b = A.man.biomes[S.region], r = b.rects.platform, P = A.img['scene_' + S.region], W = r[2] * A.S;
    for (let x = 0; x < p.w; x += W) {
      const w = Math.min(W, p.w - x); g.drawImage(P, r[0], r[1], w / A.S, r[3], p.x + x, p.y - 6, w, r[3] * A.S);
    }
  };
  A.portal = (g, S, x, GY, now) => {
    const b = A.man.biomes[S.region], r = b.rects['portal' + (Math.floor(now / 140) % 4)];
    A.shadow(g, x, GY + 2, 50);
    g.drawImage(A.img['scene_' + S.region], r[0], r[1], r[2], r[3], x - r[2], GY - 50, r[2] * A.S, r[3] * A.S);
  };
  A.location = (g, S, l, unlocked, now) => {
    const b = A.man.biomes[S.region], P = A.img['scene_' + S.region], R = b.rects, x = l.wx, GY = A.GY, sc = A.S, h = hash(l.id);
    const put = (n, dx, dy = 0, s = sc) => { const r = R[n]; g.drawImage(P, r[0], r[1], r[2], r[3], x + dx - r[2] * s / 2, GY - r[3] * s + dy, r[2] * s, r[3] * s); };
    if (l.wild) {
      const kinds = ['tree', 'pine', 'bamboo', 'tree', 'rock', 'pine'];
      for (let i = -3; i <= 3; i++) {
        const k = kinds[(h + i * 5 + 100) % kinds.length], jit = (noise(h + i) - .5) * 30;
        put(k, i * 78 + jit, k === 'rock' ? 4 : 2);
      }
    } else if (l.deep) {
      put('cave', 0, 0, 2.6);
      const a = .25 + .2 * Math.sin(now / 300) + (unlocked ? .25 : 0);
      g.fillStyle = `rgba(190,120,255,${a})`; g.beginPath(); g.ellipse(x, GY - 60, 40, 62, 0, 0, 7); g.fill();
    } else if (/門派/.test(l.type)) {
      put('pagoda', 70); put('gate', -80); put('lantern', -170); put('lantern', 190);
    } else {
      put('house' + (h % 2), -130); put('house' + ((h >> 1) % 2 ? 1 : 0), 0); put('house' + (h % 2 ? 0 : 1), 130); put('lantern', -210); put('lantern', 210);
    }
  };
  A.npc = (g, speaker, x, GY, now, face) => {
    const id = A.man.speakers[speaker]; if (!id) return false;
    const m = A.man.npcs[id], fh = A.man.human.frameH, fw = A.man.human.frameW, sc = A.S, f = Math.floor(now / 380) % 4;
    A.shadow(g, x, GY + 1, 22);
    spr(g, A.img.npcs, [f * fw, m.row * fh, fw, fh], x - fw * sc / 2, GY - 50 * sc, sc, face < 0, x);
    return true;
  };
  A.beast = (g, b, now) => {
    const k = A.man.beasts, kind = k.kinds[b.kind], row = kind.row + k.elements.indexOf(b.el), fw = k.frameW, fh = k.frameH;
    const sc = b.deep ? 2.1 : 1.6, moving = b.moving, f = Math.floor(now / (moving ? 110 : 240)) % 4;
    const lift = b.kind === 'bat' ? 44 + Math.sin(now / 200 + b.k) * 6 : 0;
    A.shadow(g, b.x, b.y + 2, 26 * sc / 1.6);
    if (b.hit > 0 && 'filter' in g) g.filter = 'brightness(2.6)';
    spr(g, A.img.beasts, [f * fw, row * fh, fw, fh], b.x - fw * sc / 2, b.y - lift - 41 * sc, sc, b.dir < 0, b.x);
    if ('filter' in g) g.filter = 'none';
  };
  A.hero = (g, hero, S, now) => {
    const m = A.man.heroes, fw = A.man.human.frameW, fh = A.man.human.frameH, sc = A.S;
    const outfit = Math.min(5, S.realm_index), base = m.outfitRows[outfit];
    let anim = 'idle', f = 0;
    if (hero.inv > .75) anim = 'hurt';
    else if (hero.atk > 0) { anim = 'attack'; f = Math.min(2, Math.floor((1 - hero.atk / .35) * 3)); }
    else if (hero.fly) { anim = 'fly'; f = Math.floor(now / 250) % 2; }
    else if (!hero.ground) anim = 'jump';
    else if (Math.abs(hero.vx) > 1) { anim = 'walk'; f = Math.floor(now / 120) % 4; }
    else f = [0, 1, 0, 1, 0, 1, 2, 1][Math.floor(now / 320) % 8];
    A.shadow(g, hero.x, A.GY + 1, 20);
    spr(g, A.img.heroes, [f * fw, (base + m.anims[anim].row) * fh, fw, fh], hero.x - fw * sc / 2, hero.y - 50 * sc, sc, hero.face < 0, hero.x);
  };
  A.slash = (g, hero) => {
    const r = A.man.fx.rects['slash' + Math.min(2, Math.floor((1 - hero.slash / .18) * 3))], sc = A.S;
    spr(g, A.img.fx, r, hero.x - 26 * sc, hero.y - 128, sc, hero.face < 0, hero.x);
  };
  A.orb = (g, s, now) => {
    const r = A.man.fx.rects[`orb_${s.el}_${Math.floor(now / 120) % 2}`], sc = A.S;
    g.drawImage(A.img.fx, r[0], r[1], r[2], r[3], s.x - r[2] * sc / 2, s.y - r[3] * sc / 2, r[2] * sc, r[3] * sc);
  };
  A.spark = (g, x, y, p) => {
    const r = A.man.fx.rects['spark' + Math.min(2, Math.floor(p * 3))], sc = A.S * 1.5;
    g.drawImage(A.img.fx, r[0], r[1], r[2], r[3], x - r[2] * sc / 2, y - r[3] * sc / 2, r[2] * sc, r[3] * sc);
  };
  A.portrait = (cv, speaker, S) => {
    const ctx = cv.getContext('2d'); ctx.clearRect(0, 0, cv.width, cv.height); ctx.imageSmoothingEnabled = false;
    const fw = A.man.human.frameW, fh = A.man.human.frameH, id = A.man.speakers[speaker];
    if (id) ctx.drawImage(A.img.npcs, 0, A.man.npcs[id].row * fh, fw, fh, 0, 0, fw, fh);
    else { const m = A.man.heroes, base = m.outfitRows[Math.min(5, S.realm_index)]; ctx.drawImage(A.img.heroes, 0, base * fh, fw, fh, 0, 0, fw, fh); }
  };
  return A;
})();
