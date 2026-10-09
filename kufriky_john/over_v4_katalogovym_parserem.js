"use strict";
// Same parser used by local catalogue geometry, without modifying it.
process.env.NODE_PATH='/opt/konfigurator/node_modules';require('module').Module._initPaths();
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),THREE=require('three');
const lib=require('../../scripts/2026-08-19_glb_real_geometry.js');
const root=__dirname,data=JSON.parse(fs.readFileSync(path.join(root,'kufriky.json'))),rows=[];
for(const r of data.records.filter(r=>r.group==='kufriky'))for(const v of r.model_variants){
 const file=path.join(root,v.file);assert.equal(lib.glbRizikaParseru(file).length,0);
 const mesh=lib.parseGlbMesh(file),box=new THREE.Box3().setFromObject(mesh),size=box.getSize(new THREE.Vector3()).toArray(),target=[r.outer.mm.width,r.outer.mm.length,r.outer.mm.height];
 assert.ok(Math.max(...size.map((a,i)=>Math.abs(a-target[i])))<.01,v.sku);rows.push({sku:v.sku,size_xyz_mm:size,vertices:mesh.geometry.getAttribute('position').count});
}
const references=[];
for(const name of ['Object_7.glb','product_3788.glb','product_3794.glb']){
 const m=lib.parseGlbMesh(path.join('/opt/konfigurator/webapp/katalog',name));references.push({file:name,size_xyz_mm:new THREE.Box3().setFromObject(m).getSize(new THREE.Vector3()).toArray()});
}
assert.ok(Math.abs(references[0].size_xyz_mm[1]-1000)<.001);assert.ok(Math.abs(references[1].size_xyz_mm[0]-299)<.001);assert.ok(Math.abs(references[1].size_xyz_mm[1]-399)<.001);assert.ok(Math.abs(references[1].size_xyz_mm[2]-120)<.001);
assert.equal(rows.length,21);fs.writeFileSync(path.join(root,'overeni-tvar-v4/katalogovy-parser.json'),JSON.stringify({status:'PASS',glbs_measured:21,rows,references,units:'mm',axes:{X:'width',Y:'length',Z:'height'}},null,2)+'\n');
console.log('Stávající katalogový parser: 21 modelů a 3 skutečné katalogové reference OK.');
