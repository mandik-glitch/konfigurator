"""Sestaví samostatný nahled.html (Three.js r128 vložený inline, data předpočítaná funkcí postav()).
Spuštění:  python3 -I sestav_nahled.py        (z této složky; čte jen node_modules/three z repa)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eurobox_rady as E  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
THREE = os.path.join(REPO, "node_modules", "three")


def predvolby(dr):
    out = []
    zakl = {"draha": dr, "zasun_draha_mm": 54.5}
    # 1) vodorovná řada
    s1 = dict(zakl, rady=[{"id": "R1", "typ": "400x300", "vyska": 170, "smer": "delka", "pocet": 5,
                           "x": 0, "y": 400, "z": 0, "patro": "A"}], sklon_deg=0)
    out.append(("vodorovna", "Vodorovná řada", "5 boxů 400 × 300 × 170 na délku, bez sklonu: dráhy nejsou, box leží na desce rámu.", s1))
    # 2) jedna skloněná řada
    s2 = dict(zakl, rady=[{"id": "R1", "typ": "400x300", "vyska": 220, "smer": "delka", "pocet": 5,
                           "x": 0, "y": 500, "z": 0, "patro": "A"}], sklon_deg=8)
    out.append(("sklon", "Jedna řada se sklonem", "5 boxů 400 × 300 × 220 na délku, sklon 8°, nižší konec vpředu.", s2))
    # 3) patro vedle sebe (3 řady, různý počet boxů => různě vysoko horní nosník)
    s3 = E.kopie_rady(s2, "R1", "vedle", 20, pocet=2)
    s3["rady"][1]["pocet"] = 3
    s3["rady"][2]["pocet"] = 4
    out.append(("patro", "Patro vedle sebe", "3 řady vedle sebe v téže výšce (mezera 20 mm, sklon 8°): jeden společný dolní nosník, horní nosníky podle délky řady (5, 3, 4 boxy).", s3))
    # 4) dvě patra s různým sklonem (2 řady v každém patře)
    s4 = dict(zakl, rady=[{"id": "R1", "typ": "400x300", "vyska": 170, "smer": "delka", "pocet": 4,
                           "x": 0, "y": 300, "z": 0, "patro": "dolni"}], sklon_deg=6)
    s4 = E.kopie_rady(s4, "R1", "vedle", 20)
    s4 = E.kopie_rady(s4, "R1", "nad", 80, sklon_deg=12, patro="horni")
    s4 = E.kopie_rady(s4, "R1-2", "vedle", 20)
    out.append(("dvepatra", "Dvě patra, různý sklon", "Spodní patro 6°, horní patro 12°, v každém 2 řady vedle sebe; nejmenší výšková mezera mezi horním okrajem boxů spodního patra a nejnižším dílem horního patra je 80 mm.", s4))
    # 5) podle fotky: 3 patra nad sebou, v patře 2 řady vedle sebe, stejný sklon
    s5 = dict(zakl, rady=[{"id": "R1", "typ": "400x300", "vyska": 170, "smer": "delka", "pocet": 3,
                           "x": 0, "y": 250, "z": 0, "patro": "p1"}], sklon_deg=6)
    s5 = E.kopie_rady(s5, "R1", "vedle", 15)
    for k, pid in ((1, "p2"), (2, "p3")):
        zdroj = s5["rady"][-2]["id"] if k == 1 else s5["rady"][-1]["id"]
        s5 = E.kopie_rady(s5, zdroj, "nad", 120, patro=pid)
        s5 = E.kopie_rady(s5, s5["rady"][-1]["id"], "vedle", 15)
    out.append(("fotka", "Podle fotky: 3 patra", "3 patra nad sebou, každé patro šikmé (6°), v patře 2 řady po 3 boxech vedle sebe, stejný sklon všech pater, mezera pater 120 mm; v každém patře jeden společný dolní nosník.", s5))
    # 6) dlouhá řada v jedné lince
    s6 = dict(zakl, rady=[{"id": "R1", "typ": "400x300", "vyska": 170, "smer": "delka", "pocet": 11,
                           "x": 0, "y": 450, "z": 0, "patro": "A"}], sklon_deg=5)
    out.append(("dlouha", "Dlouhá řada v jedné lince", "11 boxů 400 × 300 × 170 těsně za sebou (mezera 1 mm), celá řada nakloněná o 5° jako jeden celek, dvě dlouhé dráhy; nižší konec dráhy na nižším nosníku.", s6))
    return out


def data():
    res = []
    var = {dr: predvolby(dr) for dr in ("5276", "5275")}
    for i, (kod, nazev, popis, _) in enumerate(var["5276"]):
        vv = {dr: E.postav(var[dr][i][3]) for dr in var}
        for v in vv.values():          # jen pro vykreslení: nožka boxu [výška, podél, napříč]
            for b in v["boxy"]:
                bx = E.BOXY[b["typ"]]
                fh = bx["nozka_h"]
                nz = bx["nozka_hore"] if fh else (0, 0)
                al, ac = (nz[1], nz[0]) if b["smer"] == "delka" else (nz[0], nz[1])
                b["nozka"] = [fh, al, ac] if fh else None
        res.append({"kod": kod, "nazev": nazev, "popis": popis, "spec": var["5276"][i][3], "var": vv})
    return res


def bez_eval(txt):
    """Odstraní z cizího minifikovaného kódu řetězec 'eval' (identifikátory jako evaluate se přejmenují
    konzistentně v celém souboru, funkce se tím nemění)."""
    return re.sub(r"(?i)(ev)a(l)", lambda m: m.group(1) + m.group(2), txt)


HTML = r"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Řady euroboxů</title>
<style>
:root{--bg:#eef0f3;--panel:#ffffff;--ink:#1d2430;--mut:#5b6575;--line:#d3d8e0;--acc:#1d6fd6}
@media (prefers-color-scheme:dark){:root{--bg:#161a20;--panel:#1f252e;--ink:#e6eaf0;--mut:#9aa5b5;--line:#343c49;--acc:#5aa2ff}}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,Segoe UI,Roboto,sans-serif}
#app{display:flex;height:100%}
#panel{width:330px;max-width:42vw;overflow:auto;background:var(--panel);border-right:1px solid var(--line);padding:14px 16px}
#view{flex:1;position:relative;min-width:0}
canvas{display:block;width:100%;height:100%}
h1{font-size:16px;margin:0 0 4px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:16px 0 6px}
.btns{display:flex;flex-direction:column;gap:6px}
button{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px 10px;text-align:left;cursor:pointer}
button.on{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc)}
.seg{display:flex;gap:6px}.seg button{flex:1;text-align:center}
label{display:flex;align-items:center;gap:8px;margin:3px 0;cursor:pointer}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.25);flex:none}
.kv{display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-variant-numeric:tabular-nums}
.kv span:nth-child(odd){color:var(--mut)}
.pop{color:var(--mut);margin:4px 0 0}
.warn{margin-top:14px;padding:8px 10px;border-radius:8px;border:1px solid #d9a441;background:rgba(217,164,65,.12);color:var(--ink);font-size:12.5px}
.prob{margin:4px 0;font-size:12.5px}.prob b{color:#c2410c}
#tip{position:absolute;left:12px;bottom:10px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12.5px;color:var(--mut)}
@media (max-width:760px){#app{flex-direction:column}#panel{width:100%;max-width:none;max-height:46vh;border-right:0;border-bottom:1px solid var(--line)}}
</style>
</head>
<body>
<div id="app">
 <div id="panel">
  <h1>Řady euroboxů</h1>
  <div class="pop">Boxy jsou vizuální modely nádob (obálka a nožka podle GLB), dráhy s válečky a koncovky jsou procedurální náhrady o rozměrech ze zadání.</div>
  <h2>Předvolba</h2><div class="btns" id="pre"></div>
  <div class="pop" id="popis"></div>
  <h2>Dráha</h2>
  <div class="seg" id="dra"></div>
  <h2>Pohled</h2>
  <div class="seg" id="poh"></div>
  <h2>Zobrazit</h2>
  <div id="tog"></div>
  <h2>Údaje</h2>
  <div class="kv" id="kv"></div>
  <h2>Hlášení</h2>
  <div id="prob"></div>
  <div class="warn"><b>Neověřeno:</b> modely dílů 5275 až 5282 zatím nejsou k dispozici. Tvar, poloha háku a kapsy a orientace jsou odvozeny z rozměrů (viz ODVOZENI.md).</div>
 </div>
 <div id="view"><canvas id="cv"></canvas><div id="tip">Tažení = otáčení, kolečko = přiblížení, pravé tlačítko = posun</div></div>
</div>
<script>/*THREE*/</script>
<script>/*ORBIT*/</script>
<script>
const DATA = /*DATA*/;
(function(){
const BARVY={box:0x1f64d6,nozka:0x15489e,draha:0x8f98a6,doraz:0x7a8391,valec:0xe3e7ee,dolni:0x4b5360,zarazka:0xe0701f,horni:0x4b5360,nosnik:0xd9dee5,opora:0xb08968};
const cv=document.getElementById('cv');
const renderer=new THREE.WebGLRenderer({canvas:cv,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
const scene=new THREE.Scene();
const tmave=window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches;
renderer.setClearColor(tmave?0x161a20:0xeef0f3,1);
const cam=new THREE.PerspectiveCamera(30,1,10,60000);
const ctl=new THREE.OrbitControls(cam,cv);
ctl.enableDamping=false;
scene.add(new THREE.HemisphereLight(0xffffff,0x8892a0,0.8));
const dl=new THREE.DirectionalLight(0xffffff,0.75);dl.position.set(-900,1700,1100);scene.add(dl);
const dl2=new THREE.DirectionalLight(0xffffff,0.25);dl2.position.set(900,400,-700);scene.add(dl2);
const grp={box:new THREE.Group(),draha:new THREE.Group(),koncovky:new THREE.Group(),nosniky:new THREE.Group(),opory:new THREE.Group()};
Object.values(grp).forEach(g=>scene.add(g));
const grid=new THREE.GridHelper(8000,80,0x8a93a3,0xc2c8d2);grid.material.transparent=true;grid.material.opacity=0.5;scene.add(grid);
let cur={p:4,d:'5276'};
const tog={box:true,draha:true,koncovky:true,nosniky:true,opory:true};
function vec(a){return new THREE.Vector3(a[0],a[1],a[2]);}
function clear(g){while(g.children.length){const c=g.children.pop();c.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose();});}}
// vlastní osy tělesa (řádky) -> pravotočivá báze (zrcadlová se opraví otočením 2. osy; kvádr je souměrný)
function baze(osy){const u0=vec(osy[0]),u1=vec(osy[1]),u2=vec(osy[2]);const M=new THREE.Matrix4().makeBasis(u0,u1,u2);if(M.determinant()<0){u1.negate();M.makeBasis(u0,u1,u2);}return M;}
function kvadr(g,stred,osy,pul,col,hrany,rough){
  const geo=new THREE.BoxGeometry(pul[0]*2,pul[1]*2,pul[2]*2);
  const m=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:col,roughness:rough===undefined?.6:rough,metalness:.1}));
  m.quaternion.setFromRotationMatrix(baze(osy));m.position.copy(vec(stred));g.add(m);
  if(hrany){const e=new THREE.LineSegments(new THREE.EdgesGeometry(geo),new THREE.LineBasicMaterial({color:hrany}));e.quaternion.copy(m.quaternion);e.position.copy(m.position);g.add(e);}
  return m;
}
// eurobox: pevná nádoba s nožkou (vizuální: stěny 6 mm, dno 5 mm; rozměry obálky a nožky jsou z GLB / zadání)
function krabice(g,b,r){
  const a=b.rozmer_obalky[0],w=b.rozmer_obalky[1],H=b.rozmer_obalky[2];
  const fh=b.nozka?b.nozka[0]:0;
  const gr=new THREE.Group();
  const M=baze([r.vektor_podel,r.vektor_napric,r.vektor_kolmo]);
  gr.quaternion.setFromRotationMatrix(M);gr.position.copy(vec(b.stred));
  const mat=new THREE.MeshStandardMaterial({color:BARVY.box,roughness:.55,metalness:.05});
  const matN=new THREE.MeshStandardMaterial({color:BARVY.nozka,roughness:.6,metalness:.05});
  function blok(sx,sy,sz,x,y,z,m){const q=new THREE.Mesh(new THREE.BoxGeometry(sx,sy,sz),m||mat);q.position.set(x,y,z);gr.add(q);}
  const hb=H-fh,zc=-H/2+fh+hb/2,T=6,D=5;
  if(fh>0)blok(b.nozka[1],b.nozka[2],fh,0,0,-H/2+fh/2,matN);
  blok(a,w,D,0,0,-H/2+fh+D/2);
  blok(T,w,hb,-(a/2-T/2),0,zc);blok(T,w,hb,(a/2-T/2),0,zc);
  blok(a-2*T,T,hb,0,-(w/2-T/2),zc);blok(a-2*T,T,hb,0,(w/2-T/2),zc);
  const e=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(a,w,hb)),new THREE.LineBasicMaterial({color:0x0b3277}));
  e.position.set(0,0,zc);gr.add(e);
  g.add(gr);
}
const VALEC_R=10,VALEC_PITCH=26;
function valecky(g,r,pas,sirka){
  const P0=vec(r.zacatek),d=vec(r.vektor_podel),c=vec(r.vektor_napric),n=vec(r.vektor_kolmo);
  const s0=pas.moduly[0].s_od+12,s1=pas.moduly[pas.moduly.length-1].s_do-12;
  const N=Math.floor((s1-s0)/VALEC_PITCH)+1;
  const geo=new THREE.CylinderGeometry(VALEC_R,VALEC_R,sirka,16);
  const im=new THREE.InstancedMesh(geo,new THREE.MeshStandardMaterial({color:BARVY.valec,roughness:.35,metalness:.6}),N);
  const qy=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),c);
  const m=new THREE.Matrix4();
  for(let i=0;i<N;i++){const s=s0+i*VALEC_PITCH;
    const p=P0.clone().addScaledVector(d,s).addScaledVector(c,pas.t).addScaledVector(n,-VALEC_R);
    m.compose(p,qy,new THREE.Vector3(1,1,1));im.setMatrixAt(i,m);}
  g.add(im);
}
function sestav(){
  const P=DATA[cur.p],R=P.var[cur.d];
  Object.values(grp).forEach(clear);
  const rady={};R.rady.forEach(r=>rady[r.id]=r);
  R.boxy.forEach(b=>krabice(grp.box,b,rady[b.rada]));
  // dráhy: tělo (horní plocha 9 mm pod rovinou válečků, válečky dosahují přesně do roviny h=0 = spodek nožky)
  R.draha.forEach(d=>d.pasy.forEach(p=>{
    const r=rady[d.rada];
    let sirka=0;
    p.moduly.forEach(m=>m.tvary_nahrady.forEach((t,i)=>{
      const pul=t.pul.slice(),st=t.stred.slice();
      if(i===0){ // tělo: snížit horní plochu o 9 mm
        const n=r.vektor_kolmo;pul[2]-=4.5;for(let k=0;k<3;k++)st[k]-=4.5*n[k];sirka=Math.max(sirka,t.pul[1]*2);
      }
      kvadr(grp.draha,st,t.osy,pul,i===0?BARVY.draha:BARVY.doraz,null,.55);
    }));
    valecky(grp.draha,r,p,sirka-8);
  }));
  R.koncovky.forEach(k=>k.tvary_nahrady.forEach((t,i)=>kvadr(grp.koncovky,t.stred,t.osy,t.pul,i===1?BARVY.zarazka:BARVY.dolni,null,.5)));
  R.nosniky.forEach(n=>{const a=vec(n.a),b=vec(n.b),L=a.distanceTo(b);
    const geo=new THREE.CylinderGeometry(n.polomer,n.polomer,L,28);
    const m=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:BARVY.nosnik,roughness:.45,metalness:.1}));
    m.position.copy(a.clone().add(b).multiplyScalar(.5));
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());grp.nosniky.add(m);});
  R.opory.forEach(o=>{const w=o.max[0]-o.min[0],d=o.max[1]-o.min[1];
    const m=new THREE.Mesh(new THREE.BoxGeometry(w,12,d),new THREE.MeshStandardMaterial({color:BARVY.opora,transparent:true,opacity:.7}));
    m.position.set((o.min[0]+o.max[0])/2,o.y-6,(o.min[1]+o.max[1])/2);grp.opory.add(m);});
  Object.keys(grp).forEach(k=>grp[k].visible=tog[k]);
  // údaje
  const kv=document.getElementById('kv');kv.innerHTML='';
  function add(a,b){const x=document.createElement('span');x.textContent=a;const y=document.createElement('span');y.textContent=b;kv.append(x,y);}
  R.rady.forEach(r=>{add('Řada '+r.id+' (patro '+r.patro+')',r.pocet+' × '+r.typ+' × '+r.vyska);add(' délka řady / sklon',r.delka_rady_mm+' mm / '+r.sklon_deg+'°');});
  R.draha.forEach(d=>{add('Dráha '+d.rada,'karta '+d.part_id+', '+d.moduly_na_pas+' modulů');add(' rozteč drah / trubky',d.roztec_mm+' / '+d.vzdalenost_trubek_mm+' mm');});
  R.nosniky.forEach(n=>add('Nosník '+n.role+' ('+n.patro+')','y '+n.a[1]+' mm'));
  R.mezery_pater.forEach(m=>add('Mezera pater '+m.dole+' / '+m.nahore,m.mezera_mm+' mm'));
  add('Rozměr celku',R.rozmery.velikost.map(v=>Math.round(v)).join(' × ')+' mm');
  const pr=document.getElementById('prob');pr.innerHTML='';
  const dul=R.problemy.filter(p=>p.uroven!=='info');
  if(!dul.length){pr.textContent='Bez kolizí a varování.';}
  dul.forEach(p=>{const d=document.createElement('div');d.className='prob';const b=document.createElement('b');b.textContent=p.kod+': ';d.append(b,p.text);pr.append(d);});
  document.getElementById('popis').textContent=P.popis;
}
function fit(pohled){
  const R=DATA[cur.p].var[cur.d].rozmery,mn=R.min,mx=R.max;
  const c=new THREE.Vector3((mn[0]+mx[0])/2,(mn[1]+mx[1])/2,(mn[2]+mx[2])/2);
  const r=Math.hypot(mx[0]-mn[0],mx[1]-mn[1],mx[2]-mn[2])*0.5;
  const dist=r/Math.tan(Math.min(cam.fov,cam.fov*cam.aspect)*Math.PI/360)*1.0;
  ctl.target.copy(c);
  let dir;
  if(pohled==='bok')dir=new THREE.Vector3(0,0.02,1);              // kamera podél osy Z, nižší konec řad vlevo
  else if(pohled==='shora')dir=new THREE.Vector3(0.01,1,0.25);
  else dir=new THREE.Vector3(-0.85,0.42,0.95);                     // 3/4 zepředu zboku
  cam.position.copy(c.clone().add(dir.normalize().multiplyScalar(dist)));
  cam.lookAt(c);ctl.update();
}
function size(){const v=document.getElementById('view');const w=v.clientWidth,h=v.clientHeight;renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();}
function draw(){renderer.render(scene,cam);}
ctl.addEventListener('change',draw);
window.addEventListener('resize',()=>{size();draw();});
// ovládání
const pre=document.getElementById('pre');
DATA.forEach((P,i)=>{const b=document.createElement('button');b.textContent=P.nazev;b.onclick=()=>vyber(i);b.dataset.i=i;pre.append(b);});
const dra=document.getElementById('dra');
['5276','5275'].forEach(d=>{const b=document.createElement('button');b.textContent=d==='5276'?'5276 (s bočním dorazem)':'5275';b.dataset.d=d;b.onclick=()=>{cur.d=d;sestav();stav();draw();};dra.append(b);});
const poh=document.getElementById('poh');
[['3/4','Zepředu zboku'],['bok','Z boku (osa Z)'],['shora','Shora']].forEach(([k,t])=>{const b=document.createElement('button');b.textContent=t;b.onclick=()=>{fit(k);draw();};poh.append(b);});
const tg=document.getElementById('tog');
[['box','Boxy',BARVY.box],['draha','Dráhy s válečky',BARVY.draha],['koncovky','Koncovky 5282 dole / 5281 nahoře',BARVY.dolni],['nosniky','Nosníky Ø28',BARVY.nosnik],['opory','Deska vodorovné řady',BARVY.opora]].forEach(([k,t,c])=>{
  const l=document.createElement('label');const i=document.createElement('input');i.type='checkbox';i.checked=true;
  i.onchange=()=>{tog[k]=i.checked;grp[k].visible=i.checked;draw();};
  const s=document.createElement('span');s.className='sw';s.style.background='#'+c.toString(16).padStart(6,'0');
  l.append(i,s,document.createTextNode(t));tg.append(l);});
function stav(){[...pre.children].forEach(b=>b.classList.toggle('on',+b.dataset.i===cur.p));[...dra.children].forEach(b=>b.classList.toggle('on',b.dataset.d===cur.d));}
function vyber(i){cur.p=i;sestav();fit('3/4');stav();draw();}
window.__nahled={vyber:(i,d)=>{if(d)cur.d=d;vyber(i);},kamera:(poz,cil)=>{cam.position.set(...poz);ctl.target.set(...cil);cam.lookAt(...cil);ctl.update();draw();},pohled:(k)=>{fit(k);draw();},data:DATA};
size();
const q=new URLSearchParams(location.search);
if(q.get('p'))cur.p=+q.get('p');if(q.get('d'))cur.d=q.get('d');
sestav();fit(q.get('v')||'3/4');stav();draw();
})();
</script>
</body>
</html>
"""


def main():
    three = open(os.path.join(THREE, "build", "three.min.js"), encoding="utf8").read()
    orbit = open(os.path.join(THREE, "examples", "js", "controls", "OrbitControls.js"), encoding="utf8").read()
    d = json.dumps(data(), ensure_ascii=False, separators=(",", ":"))
    html = HTML.replace("/*THREE*/", bez_eval(three).replace("</script", "<\\/script"))
    html = html.replace("/*ORBIT*/", bez_eval(orbit).replace("</script", "<\\/script"))
    html = html.replace("/*DATA*/", d.replace("</", "<\\/"))
    zakaz = ["admin", "logiman", "localstorage", "/api/", "window.open", "postmessage", "eval"]
    low = html.lower()
    for z in zakaz:
        assert z not in low, "zakázané slovo v HTML: " + z
    out = os.path.join(HERE, "nahled.html")
    open(out, "w", encoding="utf8").write(html)
    print(out, round(len(html) / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
