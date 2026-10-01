// 瀏覽器冒煙測試：載入遊戲，把主角放到 NPC 身上，確認沒有執行錯誤，而且能走開。
// 用法：node tests/browser_smoke.js <url> <playwright 路徑> <chromium 路徑>
const [url, pwPath, exe] = process.argv.slice(2);
const {chromium} = require(pwPath);
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch({executablePath: exe});
  const pg = await b.newPage({viewport: {width: 1000, height: 700}});
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await pg.goto(url); await sleep(2500);
  const out = {errs, moved: null, partner: await pg.evaluate('!!__td.S.partner')};
  const npc = await pg.evaluate("(() => { const e = __td.ents.find(e => e.k === 'npc'); return e ? [e.px, e.py] : null; })()");
  if (npc) {
    await pg.evaluate(`__td.hero.x = ${npc[0]}; __td.hero.y = ${npc[1]};`);
    await sleep(200);
    const before = await pg.evaluate('[__td.hero.x, __td.hero.y]');
    await pg.keyboard.down('ArrowRight'); await sleep(700); await pg.keyboard.up('ArrowRight');
    await pg.keyboard.down('ArrowDown'); await sleep(500); await pg.keyboard.up('ArrowDown');
    const after = await pg.evaluate('[__td.hero.x, __td.hero.y]');
    out.moved = Math.hypot(after[0] - before[0], after[1] - before[1]);
  }
  out.errs = errs;
  console.log(JSON.stringify(out));
  await b.close();
})();
