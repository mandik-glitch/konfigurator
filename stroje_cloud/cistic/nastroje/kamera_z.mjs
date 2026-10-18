// Převod kamery (cx,cy,cz,yaw,pitch,roll,fov; z' nad zemí) na kameru render.mjs (model má počátek ve středu obálky → z = z' − 390).
export function kameraZ(c) {
  const [cx, cy, cz, yaw, pitch, roll, fov] = c, ya = yaw * Math.PI / 180, pi = pitch * Math.PI / 180;
  const f = [Math.cos(pi) * Math.cos(ya), Math.cos(pi) * Math.sin(ya), Math.sin(pi)];
  const pos = [cx, cy, cz - 390];
  return { pos, target: [pos[0] + f[0] * 1000, pos[1] + f[1] * 1000, pos[2] + f[2] * 1000], fov, up: [0, 0, 1], roll, shiftX: 0, shiftY: 0 };
}
