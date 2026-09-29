"""瀏覽器介面：python -m chineserim.web  → http://127.0.0.1:8765"""
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import treasures
from .character import Character
from .data import GameData
from .realms import RealmSystem

data = GameData()
rs = RealmSystem(data, random.Random())
hero = Character("韓立", elements=["金", "木", "水", "火"], root_type="quad")
rs.set_realm(hero, "mortal")
hero.add("lingshi", 500)
state = {"day": 0, "log": ["歡迎來到凡人修仙傳（獨立版，不需 Skyrim）"], "last_moon": None}
rs.on("CR_OnRealmChanged", lambda actor, order, sub, old: state["log"].append(f"★ 境界變更 → {data.realms[order]['name']}"))


def snapshot():
    r = rs.realm(hero)
    return {"name": hero.name, "realm": r["name"], "sub": r["sub"][hero.sub], "level": hero.level,
            "cap": r["levelRange"][1], "hp": hero.hp, "max_hp": hero.max_hp, "mp": hero.mp,
            "stamina": hero.stamina, "elements": hero.elements, "lingshi": hero.count("lingshi"),
            "lingye": hero.count("lingye"), "pills": hero.count("pill"), "day": state["day"],
            "treasures": hero.treasures, "bottleneck": rs.at_bottleneck(hero), "log": state["log"][-12:],
            "realms": [x["name"] for x in data.realms[:6]], "realm_index": hero.realm}


def act(cmd):
    log = state["log"]
    if cmd == "train":
        rs.gain_level(hero, 5)
        rs.advance_sub(hero)
        log.append("修煉一番" + ("，已達瓶頸，需要突破" if rs.at_bottleneck(hero) else ""))
    elif cmd == "buy_pill":
        if hero.remove("lingshi", 100):
            hero.add("pill")
            log.append("花 100 靈石買了一顆突破丹")
        else:
            log.append("靈石不足")
    elif cmd == "break":
        pill = "pill" if hero.count("pill") else None
        ok = rs.attempt_breakthrough(hero, pill)
        log.append("突破成功！" if ok else "突破失敗或尚未到瓶頸（失敗會損失一半 HP）")
    elif cmd == "refine":
        log.append("青竹蜂雲劍祭煉成功" if treasures.refine(rs, hero, "qingzhu_fengyunjian") else "祭煉條件不足（需境界＋靈石）")
    elif cmd == "wait":
        state["day"] += 30
        hero.hp = min(hero.max_hp, hero.hp + hero.max_hp)
        before = hero.count("lingye")
        state["last_moon"] = treasures.tick_zhangtianping(rs, hero, state["day"], 22, last_day=state["last_moon"])
        log.append(f"第 {state['day']} 日，掌天瓶月圓" + ("產出一滴靈液" if hero.count("lingye") > before else "無產出"))


PAGE = """<!doctype html><meta charset=utf-8><title>凡人修仙傳</title>
<style>body{font-family:sans-serif;max-width:640px;margin:2em auto;background:#14181d;color:#e6e2d3}
.bar{background:#333;height:14px;border-radius:7px;overflow:hidden;margin:4px 0 10px}.bar i{display:block;height:100%}
button{margin:4px;padding:8px 14px;font-size:15px}#log{background:#0c0f12;padding:10px;min-height:150px;border-radius:6px}
.realms span{padding:2px 8px;margin:2px;border:1px solid #555;border-radius:10px;display:inline-block}.realms .on{background:#b8893a;color:#000}</style>
<h1>凡人修仙傳</h1><div id=s></div>
<div><button onclick=a('train')>修煉</button><button onclick=a('buy_pill')>買突破丹(100靈石)</button>
<button onclick=a('break')>突破</button><button onclick=a('refine')>祭煉青竹蜂雲劍</button><button onclick=a('wait')>閉關 30 日</button></div>
<h3>紀錄</h3><div id=log></div>
<script>
async function a(c){await fetch('/act?c='+c,{method:'POST'});r()}
async function r(){const d=await (await fetch('/state')).json();
const bar=(v,m,c)=>`<div class=bar><i style="width:${100*v/m}%;background:${c}"></i></div>`;
s.innerHTML=`<div class=realms>${d.realms.map((n,i)=>`<span class="${i==d.realm_index?'on':''}">${n}</span>`).join('')}</div>
<p><b>${d.name}</b>　${d.realm}·${d.sub}　靈根：${d.elements.join('')}　第 ${d.day} 日</p>
等級 ${d.level}/${d.cap}${d.bottleneck?'　<b style=color:#e6a>【瓶頸】</b>':''}${bar(d.level,d.cap,'#b8893a')}
HP ${d.hp.toFixed(0)}/${d.max_hp}${bar(d.hp,d.max_hp,'#c44')}MP ${d.mp}${bar(d.mp,Math.max(d.mp,1000),'#48c')}
<p>靈石 ${d.lingshi}　突破丹 ${d.pills}　靈液 ${d.lingye}　法寶：${JSON.stringify(d.treasures)}</p>`;
log.innerHTML=d.log.map(x=>'<div>'+x+'</div>').join('')}
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
        act(self.path.split("c=")[-1])
        self._send("{}", "application/json")

    def log_message(self, *a):
        pass


def main():
    print("開啟瀏覽器：http://127.0.0.1:8765  （Ctrl+C 結束）")
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()


if __name__ == "__main__":
    main()
