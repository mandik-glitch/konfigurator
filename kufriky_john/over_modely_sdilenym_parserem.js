"use strict";
// Druhé, nezávislé měření stávajícím katalogovým parserem.
process.env.NODE_PATH="/opt/konfigurator/node_modules";
require("module").Module._initPaths();
const fs=require("fs"),path=require("path"),assert=require("assert/strict"),THREE=require("three");
const lib=require("../../scripts/2026-08-19_glb_real_geometry.js");
const root=__dirname,data=JSON.parse(fs.readFileSync(path.join(root,"kufriky.json"))),rows=[];
for(const r of data.records.filter(r=>r.group==="kufriky")){
  for(const v of r.envelope.variants){
    const file=path.join(root,v.file);assert.equal(lib.glbRizikaParseru(file).length,0);
    const m=lib.parseGlbMesh(file),b=new THREE.Box3().setFromObject(m),s=b.getSize(new THREE.Vector3()).toArray();
    assert.deepEqual(s,[r.outer.mm.width,r.outer.mm.length,r.outer.mm.height]);
    rows.push({sku:v.sku,size_xyz_mm:s,vertices:m.geometry.getAttribute("position").count});
  }
}
const references=[];
for(const name of ["Object_7.glb","product_3788.glb","product_3794.glb"]){
  const m=lib.parseGlbMesh(path.join("/opt/konfigurator/webapp/katalog",name)),b=new THREE.Box3().setFromObject(m);
  references.push({file:name,min_mm:b.min.toArray(),max_mm:b.max.toArray(),size_xyz_mm:b.getSize(new THREE.Vector3()).toArray()});
}
assert.ok(Math.abs(references[0].size_xyz_mm[1]-1000)<.001);
assert.ok(Math.abs(references[1].size_xyz_mm[0]-299)<.001);
assert.ok(Math.abs(references[1].size_xyz_mm[1]-399)<.001);
assert.ok(Math.abs(references[1].size_xyz_mm[2]-120)<.001);
assert.ok(Math.abs(references[2].size_xyz_mm[2]-220)<.001);
fs.writeFileSync(path.join(root,"overeni-modely/sdileny-parser.json"),JSON.stringify({status:"PASS_envelope_only",measured_glbs:rows.length,rows,references},null,2)+"\n");
console.log("Sdílený katalogový parser: 21 GLB ověřeno, 3 skutečné katalogové reference změřeny; X=Š, Y=L, Z=V, čísla v mm.");
