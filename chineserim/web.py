"""瀏覽器介面（世界地圖探索）：python -m chineserim.web  → http://127.0.0.1:8765"""
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from . import treasures
from .character import Character
from .data import GameData
from .explore import WorldMap, visit
from .realms import RealmSystem

data = GameData()
rng = random.Random()
rs = RealmSystem(data, rng)
world = WorldMap(data)
hero = Character("韓立", elements=["金", "木", "水", "火"], root_type="quad")
rs.set_realm(hero, "mortal")
hero.add("lingshi", 500)
state = {"day": 0, "region": "tiannan", "log": ["你站在天南。點地圖上的區域旅行，點區域內的地點探索。"]}
rs.on("CR_OnRealmChanged", lambda actor, order, sub, old: state["log"].append(f"★ 境界變更 → {data.realms[order]['name']}"))


def advance(days):
    d0 = state["day"]
    state["day"] += days
    for d in range(d0 + 1, state["day"] + 1):
        if d % treasures.MOON_CYCLE_DAYS == 0:
            n = hero.count("lingye")
            treasures.tick_zhangtianping(rs, hero, d, 22)
            if hero.count("lingye") > n:
                state["log"].append(f"第 {d} 日月圓，掌天瓶凝出一滴靈液")


def snapshot():
    r = rs.realm(hero)
    reg = world.regions[state["region"]]
    return {
        "name": hero.name, "realm": r["name"], "sub": r["sub"][hero.sub], "level": hero.level, "cap": r["levelRange"][1],
        "hp": round(hero.hp), "max_hp": hero.max_hp, "mp": hero.mp, "elements": hero.elements,
        "lingshi": hero.count("lingshi"), "lingye": hero.count("lingye"), "pills": hero.count("pill"),
        "day": state["day"], "treasures": hero.treasures, "sects": {data.sects[k]["name"]: v for k, v in hero.sects.items()},
        "bottleneck": rs.at_bottleneck(hero), "log": state["log"][-14:], "realm_index": hero.realm,
        "realms": [x["name"] for x in data.realms[:6]],
        "region": state["region"], "region_name": reg["name"],
        "world": [{"id": g["id"], "name": g["name"], "x": g["coords"][0], "y": g["coords"][1], "world": g["world_name"],
                   "locked": not world.can_enter(hero, g["id"]), "days": world.travel_days(hero, state["region"], g["id"])}
                  for g in world.regions.values()],
        "locations": [{"id": l["id"], "name": l["name"], "type": l["type"], "note": l.get("note", ""), "x": x, "y": y}
                      for l, x, y in world.location_layout(state["region"])],
    }


def act(path, q):
    log = state["log"]
    if path == "/travel":
        ok, days, msg = world.travel(hero, state["region"], q["to"])
        log.append(msg + (f"（耗時 {days} 日）" if ok else ""))
        if ok:
            state["region"] = q["to"]
            advance(days)
    elif path == "/visit":
        msgs, days = visit(world, rs, hero, state["region"], q["loc"], rng)
        log.extend(msgs)
        advance(days)
    elif path == "/act":
        c = q["c"]
        if c == "break":
            ok = rs.attempt_breakthrough(hero, "pill" if hero.count("pill") else None)
            log.append("突破成功！" if ok else "突破失敗或尚未到瓶頸（失敗損失一半 HP）")
        elif c == "refine":
            log.append("青竹蜂雲劍祭煉成功" if treasures.refine(rs, hero, "qingzhu_fengyunjian") else "祭煉條件不足（築基以上＋靈石）")
        elif c == "rest":
            hero.hp = hero.max_hp
            advance(7)
            log.append("閉關 7 日，傷勢痊癒")


PAGE = """<!doctype html><meta charset=utf-8><title>凡人修仙傳</title>
<style>
body{font-family:sans-serif;background:#14181d;color:#e6e2d3;margin:0;padding:12px}
.wrap{display:flex;flex-wrap:wrap;gap:14px}.col{flex:1 1 380px;min-width:300px}
svg{background:#0c1a22;border:1px solid #444;border-radius:8px;width:100%;aspect-ratio:1}
.node{cursor:pointer}.node:hover circle{stroke:#fff}.node text{fill:#e6e2d3;font-size:3.2px;pointer-events:none}
.lock circle{fill:#333!important}.bar{background:#333;height:10px;border-radius:5px;overflow:hidden;margin:3px 0 8px}.bar i{display:block;height:100%}
button{margin:3px;padding:7px 12px}#log{background:#0c0f12;padding:8px;min-height:120px;border-radius:6px;font-size:14px}
.realms span{padding:1px 7px;margin:1px;border:1px solid #555;border-radius:10px;display:inline-block;font-size:13px}.realms .on{background:#b8893a;color:#000}
h3{margin:8px 0 4px}small{color:#9a9686}
</style>
<h2 style="margin:0 0 8px">凡人修仙傳</h2>
<div class=wrap>
<div class=col><h3>世界地圖 <small>點區域旅行</small></h3><svg id=wm viewBox="0 0 100 100"></svg>
<h3 id=rt></h3><svg id=rm viewBox="0 0 100 100"></svg></div>
<div class=col><div id=s></div>
<button onclick="a('/act?c=break')">突破</button><button onclick="a('/act?c=refine')">祭煉青竹蜂雲劍</button><button onclick="a('/act?c=rest')">閉關 7 日</button>
<h3>紀錄</h3><div id=log></div></div></div>
<script>
const COL={"人界":"#4a8","靈界":"#a6d"};
const TC={"村鎮":"#6c6","城市":"#6c6","都城":"#6c6","府城":"#6c6","坊市":"#6c6","巨城":"#6c6","門派":"#e94","門派/山":"#e94","秘境":"#d4d","聖地":"#d4d"};
async function a(u){await fetch(u,{method:'POST'});r()}
async function r(){const d=await (await fetch('/state')).json();
const bar=(v,m,c)=>`<div class=bar><i style="width:${Math.min(100,100*v/m)}%;background:${c}"></i></div>`;
s.innerHTML=`<div class=realms>${d.realms.map((n,i)=>`<span class="${i==d.realm_index?'on':''}">${n}</span>`).join('')}</div>
<p><b>${d.name}</b> ${d.realm}·${d.sub}　靈根 ${d.elements.join('')}　第 ${d.day} 日　所在：${d.region_name}</p>
等級 ${d.level}/${d.cap}${d.bottleneck?' <b style=color:#e6a>【瓶頸】</b>':''}${bar(d.level,d.cap,'#b8893a')}
HP ${d.hp}/${d.max_hp}${bar(d.hp,d.max_hp,'#c44')}
<p>靈石 ${d.lingshi}　突破丹 ${d.pills}　靈液 ${d.lingye}　法寶 ${JSON.stringify(d.treasures)}<br>門派聲望 ${JSON.stringify(d.sects)}</p>`;
log.innerHTML=d.log.map(x=>'<div>'+x+'</div>').join('');log.scrollTop=1e6;
wm.innerHTML=d.world.map(g=>`<g class="node ${g.locked?'lock':''}" onclick="a('/travel?to=${g.id}')"><circle cx=${g.x} cy=${100-g.y} r=${g.id==d.region?4.5:3.2} fill="${COL[g.world]}" stroke="${g.id==d.region?'#fc6':'#000'}" stroke-width=.8></circle>
<text x=${g.x} y=${100-g.y+7} text-anchor=middle>${g.name}${g.id==d.region?'':' ('+g.days+'日)'}${g.locked?'🔒':''}</text></g>`).join('');
rt.innerHTML=d.region_name+' <small>點地點探索</small>';
rm.innerHTML=`<circle cx=50 cy=50 r=46 fill="#10261c" stroke="#264"/>`+d.locations.map(l=>`<g class=node onclick="a('/visit?loc=${l.id}')"><title>${l.type}：${l.note}</title><circle cx=${l.x} cy=${l.y} r=3 fill="${TC[l.type]||'#c55'}" stroke=#000 stroke-width=.6></circle>
<text x=${l.x} y=${l.y+6} text-anchor=middle>${l.name.replace(/（.*/,'')}</text></g>`).join('')}
r()</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/state":
            self._send(json.dumps(snapshot(), ensure_ascii=False), "application/json")
        else:
            self._send(PAGE, "text/html")

    def do_POST(self):
        u = urlparse(self.path)
        act(u.path, {k: v[0] for k, v in parse_qs(u.query).items()})
        self._send("{}", "application/json")

    def log_message(self, *a):
        pass


def main():
    print("開啟瀏覽器：http://127.0.0.1:8765  （Ctrl+C 結束）")
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()


if __name__ == "__main__":
    main()
