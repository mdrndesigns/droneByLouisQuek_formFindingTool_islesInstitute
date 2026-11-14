/* DronePendantSpeakerTool - browser side.
   The Python engine owns the geometry; this page sends the state, draws what comes back. */
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const TABS = { 'Pendant': 'Form', 'Top rock - dome + speaker pod': 'Form', 'Base rock - deck + keel': 'Form',
               'Seam line': 'Form', 'Surface texture': 'Form', 'Diffuser peak (centre cone)': 'Form', 'Gap - struts': 'Build', 'Speaker': 'Build', 'Twist-lock': 'Build',
               'Electronics': 'Build', 'Hanging': 'Build', 'Print': 'Output', 'View': 'Output', 'Set': 'Output' };
const CLIENT_ONLY = ['explode', 'section', 'hardware', 'annot', 'ov', 'name', 'count'];

const j = await (await fetch('/defaults')).json();
const gui = new ControlGUI({ mount: document.body, title: 'DronePendantSpeakerTool', state: j.defaults, debounce: 220,
  hud: '<b>Drone</b> · drag to orbit · wheel to zoom · right-drag to pan · alt-h hides the panel' });
const schema = j.catalog.schema.map(it => ({ ...it, tab: TABS[it.group] || 'Form' }));
schema.splice(schema.findIndex(it => it.key === 'annot') + 1, 0,
  { key: 'ov', type: 'slider', label: 'Overlay strength', group: 'View', tab: 'Output', min: 0.15, max: 1, step: 0.05, value: 0.7,
    show: { key: 'annot', truthy: true } });
schema.push({ key: 'count', type: 'slider', label: 'Pendants in set', group: 'Set', tab: 'Output', min: 2, max: 8, step: 1, value: 6 });
schema.push({ key: 'export_set', type: 'button', label: 'Export set · new seed per pendant', group: 'Set', tab: 'Output' });
gui.fromSchema(schema);
gui.addFoot({ name: 'drone_01', label: 'Export STL + 3MF + parameters', onClick: () => exportZip(1),
              hint: 'One zip: every part in print orientation, hardware list, parameters.json.' });
window.DRONE = gui;

/* ---------- presets write the sliders, the sliders stay free ---------- */
gui.controller('preset').onChange(k => { const { label, ...v } = j.catalog.presets[k]; gui.setAll(v, { broadcast: false }); gui.commit(); });
gui.controller('driver').onChange(k => {
  const d = j.catalog.drivers[k]; const v = {};
  ['spk_cut', 'spk_bcd', 'spk_frame', 'spk_depth', 'spk_magnet'].forEach(n => { if (n in d) v[n] = d[n]; });
  gui.setAll(v, { broadcast: false }); gui.commit();
});
['t_', 'b_'].forEach((pre, i) => gui.controller(pre + 'form').onChange(k => {
  const f = j.catalog.forms[k]; const v = {};
  ['sq', 'facets', 'facet_depth', 'sharp', 'namp', 'nscale'].forEach(n => { v[pre + n] = f[n]; });
  v[pre + 'taper'] = f.taper[i];
  gui.setAll(v, { broadcast: false }); gui.commit();
}));
gui.on('bang', key => {
  if (key === 'reseed') { gui.set('seed', Math.floor(Math.random() * 9999)); gui.commit(); }
  if (key === 'export_set') exportZip(gui.get('count'));
});

/* ---------- stage ---------- */
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0xffffff);
renderer.localClippingEnabled = true;
gui.stage.prepend(renderer.domElement);
const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'dp-annot'); gui.stage.append(svg);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 5, 8000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.addEventListener('change', draw);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8890b0, 1.35));
const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(300, -500, 700); scene.add(sun);
const fillL = new THREE.DirectionalLight(0xffffff, 0.6); fillL.position.set(-400, 300, -200); scene.add(fillL);

const clip = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
// printed parts: one hue, a different tone per part so neighbours separate (most of all when exploded)
const TONES = { top_dome: 0x2f45d8, crown: 0x8592f0, top_tray: 0x9aa6f4, top_pod: 0x3b52e6, peak: 0x6f7ff0, base_deck: 0x2a3fc8, base_keel: 0x2236b4 };
const partMats = {};
const matFor = name => partMats[name] || (partMats[name] = new THREE.MeshStandardMaterial({
  color: TONES[name] ?? 0x3b52e6, roughness: 0.62, metalness: 0.0, side: THREE.DoubleSide,
  polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }));
const matHw = new THREE.MeshStandardMaterial({ color: 0xd0d0d0, roughness: 0.5, transparent: true, opacity: 0.6, side: THREE.DoubleSide, depthWrite: false });
const matEdge = new THREE.LineBasicMaterial({ color: 0x0a0d2a, transparent: true, opacity: 0.28 });
const matBed = new THREE.LineBasicMaterial({ color: 0x8a8d99 });
const root = new THREE.Group(); scene.add(root);
let items = [], lastView = null, lastQuery = null, sizeRef = 240, printed = [];

function resize() {
  const w = gui.stage.clientWidth, h = gui.stage.clientHeight;
  renderer.setSize(w, h, false); renderer.domElement.style.width = '100%'; renderer.domElement.style.height = '100%';
  camera.aspect = w / h; camera.updateProjectionMatrix(); draw();
}
new ResizeObserver(resize).observe(gui.stage);

/* ---------- annotation overlay: part IDs and dimensions, projected from the model every frame ---------- */
let dims = [];
const P3 = new THREE.Vector3();
function proj(p, w, h) { P3.set(p[0], p[1], p[2]).project(camera); return [(P3.x + 1) / 2 * w, (1 - P3.y) / 2 * h]; }
const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;');

function draw() {
  renderer.render(scene, camera);
  const w = gui.stage.clientWidth, h = gui.stage.clientHeight;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  document.documentElement.style.setProperty('--ov', gui.get('ov') ?? 0.7);
  if (!gui.get('annot')) { svg.innerHTML = ''; return; }
  const print = gui.get('view') === 'print';
  let lines = '', texts = '', dlines = '', axis = '';
  if (print || gui.get('explode') === 0) dims.forEach(d => {            // dimensions only where the model is in true position
    const A = proj(d.a, w, h), B = proj(d.b, w, h);
    const dx = B[0] - A[0], dy = B[1] - A[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L * 5, ny = dx / L * 5;
    dlines += `<path d="M${A[0]} ${A[1]}L${B[0]} ${B[1]}M${A[0] - nx} ${A[1] - ny}L${A[0] + nx} ${A[1] + ny}M${B[0] - nx} ${B[1] - ny}L${B[0] + nx} ${B[1] + ny}"/>`;
    texts += `<text class="dim" x="${(A[0] + B[0]) / 2}" y="${(A[1] + B[1]) / 2 + 3.5}" text-anchor="middle">${esc(d.t)}</text>`;
  });
  const vis = items.filter(it => it.group.visible);
  if (print) {
    vis.forEach(it => {
      const b = it.box, c = proj([(b.min.x + b.max.x) / 2, b.min.y - 34, 0], w, h);
      texts += `<text class="${it.fits ? 'id' : 'id bad'}" x="${c[0]}" y="${c[1] + 12}" text-anchor="middle"><tspan class="code">${it.id}</tspan> ${esc(it.title)}</text>`
            + `<text class="sub" x="${c[0]}" y="${c[1] + 25}" text-anchor="middle">${esc(it.size)} mm · ${it.grams} g</text>`
            + `<text class="sub" x="${c[0]}" y="${c[1] + 37}" text-anchor="middle">${esc(it.orient)} · supports ${esc(it.support)}</text>`;
    });
  } else {
    const ex = gui.get('explode');
    if (ex > 0 && vis.length) {                                  // assembly axis: the hang line every part travels along
      const zs = vis.flatMap(it => [it.box.min.z + it.group.position.z, it.box.max.z + it.group.position.z]);
      const A = proj([0, 0, Math.max(...zs) + 20], w, h), B = proj([0, 0, Math.min(...zs) - 20], w, h);
      axis = `<path d="M${A[0]} ${A[1]}L${B[0]} ${B[1]}"/>`;
    }
    // each label sits level with its own part, pushed apart only as far as needed, clear of the readout card
    const card = gui.stage.querySelector('.cg-readout'), top = (card ? card.offsetTop + card.offsetHeight : 0) + 22, gapY = 16;
    const rows = vis.map(it => {
      const a = it.anchor, z = it.group.position.z;
      return { it, p: proj([a[0], a[1], a[2] + z], w, h) };
    }).sort((m, n) => m.p[1] - n.p[1]);
    let y = top - gapY;
    rows.forEach(r => { y = Math.max(r.p[1] + 3, y + gapY); r.y = y; });
    const over = rows.length ? rows[rows.length - 1].y - (h - 24) : 0;   // ran off the bottom: slide the stack up, not above top
    if (over > 0) for (let i = rows.length - 1, lim = h - 24; i >= 0; i--, lim -= gapY) rows[i].y = Math.max(Math.min(rows[i].y, lim), top);
    const x0 = Math.max(w - 290, Math.max(...rows.map(r => r.p[0]), 0) + 60);
    rows.forEach(r => {
      const ly = r.y - 3.5;
      lines += `<path d="M${x0 - 6} ${ly}L${x0 - 22} ${ly}L${r.p[0] + 4} ${r.p[1]}"/><circle cx="${r.p[0]}" cy="${r.p[1]}" r="2"/>`;
      texts += `<text class="id" x="${x0}" y="${r.y}"><tspan class="code">${r.it.id}</tspan> ${esc(r.it.title)} <tspan class="sz">${esc(r.it.size)}</tspan></text>`;
    });
  }
  svg.innerHTML = `<g class="ax">${axis}</g><g class="dm">${dlines}</g><g class="ln">${lines}</g>${texts}`;
}

function fit(keepDir = false) {
  const box = new THREE.Box3().setFromObject(root); if (box.isEmpty()) return;
  const sph = box.getBoundingSphere(new THREE.Sphere());
  const v = THREE.MathUtils.degToRad(camera.fov) / 2, h = Math.atan(Math.tan(v) * camera.aspect);
  const dist = sph.radius / Math.sin(Math.min(v, h)) * 1.02;
  const dir = keepDir ? camera.position.clone().sub(controls.target)
            : gui.get('view') === 'print' ? new THREE.Vector3(0.0, -0.75, 1) : new THREE.Vector3(0.75, -1, 0.28);
  camera.position.copy(sph.center).addScaledVector(dir.normalize(), dist);
  controls.target.copy(sph.center); controls.update();
}

function applyView() {
  const e = gui.get('view') === 'print' ? 0 : gui.get('explode') * sizeRef * 0.55;
  const cut = gui.get('section') ? [clip] : [];
  Object.values(partMats).forEach(m => { m.clippingPlanes = cut; }); matHw.clippingPlanes = cut; matEdge.clippingPlanes = cut;
  items.forEach(it => { it.group.position.z = it.ex * e; it.group.visible = it.kind === 'part' || gui.get('hardware'); });
  draw();
}

// leader target: a real surface point on the +x side, in the middle band of the part's height
function anchorOf(pos, b) {
  const z0 = b.min.z + (b.max.z - b.min.z) * 0.3, z1 = b.max.z - (b.max.z - b.min.z) * 0.3, cy = (b.min.y + b.max.y) / 2;
  let best = null, score = -Infinity;
  for (let i = 0; i < pos.length; i += 3) {
    const z = pos[i + 2]; if (z < z0 || z > z1) continue;
    const s = pos[i] - Math.abs(pos[i + 1] - cy) * 0.6;
    if (s > score) { score = s; best = [pos[i], pos[i + 1], z]; }
  }
  return best || [b.max.x, cy, (b.min.z + b.max.z) / 2];
}

function show(buf) {
  const dv = new DataView(buf); const hl = dv.getUint32(0, true);
  const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hl)));
  let off = 4 + hl;
  root.clear(); items.forEach(it => { it.geo.dispose(); it.edges.dispose(); }); items = [];
  head.items.forEach(it => {
    const pos = new Float32Array(buf.slice(off, off + it.nv * 12)); off += it.nv * 12;
    const idx = new Uint32Array(buf.slice(off, off + it.nf * 12)); off += it.nf * 12;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.computeVertexNormals(); geo.computeBoundingBox();
    const g = new THREE.Group();
    g.add(new THREE.Mesh(geo, it.kind === 'part' ? matFor(it.name) : matHw));
    const edges = new THREE.EdgesGeometry(geo, it.kind === 'part' ? 38 : 30);
    g.add(new THREE.LineSegments(edges, matEdge));
    root.add(g); items.push({ ...it, group: g, geo, edges, box: geo.boundingBox, anchor: anchorOf(pos, geo.boundingBox) });
  });
  printed = head.printed; dims = head.dims; sizeRef = Math.max(gui.get('t_w'), gui.get('b_w'));
  if (gui.get('view') === 'print') {                       // bed outline under the row of parts
    const [bx, by] = head.bed; const pts = [[-bx / 2, -by / 2], [bx / 2, -by / 2], [bx / 2, by / 2], [-bx / 2, by / 2], [-bx / 2, -by / 2]]
      .map(p => new THREE.Vector3(p[0], p[1], 0));
    const bed = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), matBed);
    const big = items.reduce((m, n) => (n.box.max.x - n.box.min.x > m.box.max.x - m.box.min.x ? n : m), items[0]);
    bed.position.set((big.box.min.x + big.box.max.x) / 2, (big.box.min.y + big.box.max.y) / 2, 0); root.add(bed);
  }
  gui.readout(head.derived); gui.warn(head.warnings);
  applyView();                                               // place exploded parts first, then frame what is visible
  if (lastView !== gui.get('view')) { fit(); lastView = gui.get('view'); draw(); }
}

function serverQuery() { const q = gui.toQuery(); CLIENT_ONLY.forEach(k => q.delete(k)); return q.toString(); }

let ctrl;
gui.on('change', key => { if (['explode', 'section', 'hardware', 'annot', 'ov'].includes(key)) { applyView(); if (key === 'explode') { fit(true); draw(); } } });
gui.on('commit', async () => {
  const q = serverQuery(); if (q === lastQuery) return;
  if (ctrl) ctrl.abort(); ctrl = new AbortController(); gui.busy(true);
  try {
    const res = await fetch('/preview.bin?' + q, { signal: ctrl.signal });
    if (!res.ok) { gui.error((await res.json()).errors.join(' · ')); return; }   // keep the last good drawing
    gui.error(''); lastQuery = q; show(await res.arrayBuffer());
  } catch (e) { if (e.name !== 'AbortError') gui.error('Preview failed: ' + e.message); }
  finally { gui.busy(false); }
});

async function exportZip(count) {
  gui.busy(true); gui.error('');
  try {
    const name = (gui.get('name') || 'drone').replace(/[^\w-]/g, '_');
    const res = await fetch(`/export?${serverQuery()}&name=${name}&count=${count}`);
    if (!res.ok) { gui.error((await res.json()).errors.join(' · ')); return; }
    const errs = JSON.parse(res.headers.get('X-Errors') || '[]');
    if (errs.length) gui.warn(errs.map(e => 'Not built: ' + e));
    const a = document.createElement('a'); a.href = URL.createObjectURL(await res.blob()); a.download = name + (count > 1 ? '_set' : '') + '.zip'; a.click();
  } catch (e) { gui.error('Export failed: ' + e.message); }
  finally { gui.busy(false); }
}

gui.fromQuery(location.search); resize(); gui.commit();
