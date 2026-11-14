/* ==========================================================================
   controlGUI — a controlP5-shaped control panel for the browser
   Dependency-free. Pair with controlgui.css.

   const gui = new ControlGUI({ mount: '#app', title: 'MYLAB', tagline: 'what it makes' });
   gui.addSlider('reach', { min: 10, max: 120, step: 1, value: 30, group: 'Hook' });
   gui.on('change', (key, value, state) => { ... });          // every edit, immediate
   gui.on('commit', (state) => rebuild(state));               // after a quiet period (debounce)

   Principles carried over from controlP5 (Andreas Schlegel):
     - one registry, every controller has a unique name (key); get it back with gui.get / gui.controller(key)
     - auto-binding: gui.bind(obj) writes obj[key] = value on change and calls obj[key](value) when it is a function
     - a single controlEvent: gui.on('change', fn) receives everything; per-controller .onChange(fn) as well
     - method chaining on controllers: .setRange().setValue().setLabel().hide().show().lock().moveTo()
     - groups / tabs / collapsible groups, hide / show / lock the whole panel (alt-h toggles it)
     - properties: gui.save() / gui.load(json) / gui.toQuery() / gui.fromQuery(search)
     - setBroadcast(false): gui.set(key, v, { broadcast: false })
   ========================================================================== */
(function (root) {
  'use strict';

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const decimals = step => (step && step < 1) ? Math.min(4, Math.ceil(-Math.log10(step))) : 0;
  const fmt = (v, step) => Number(v).toFixed(decimals(step));
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  /* ---------------------------------------------------------------- Controller */
  class Controller {
    constructor(gui, key, item) {
      this.gui = gui; this.key = key; this.item = item;
      this.wrap = el('div', 'cg-ctl');
      this.wrap.dataset.key = key;
      this.listeners = [];
      this.broadcast = true;
    }
    // --- chainable setters (controlP5 parity)
    setLabel(text) { this.item.label = text; if (this.labelEl) this.labelEl.textContent = text; return this; }
    setValue(v, opts) { this.gui.set(this.key, v, opts); return this; }
    setRange(min, max) { this.item.min = min; this.item.max = max; if (this.range) { this.range.min = min; this.range.max = max; } this.paint(); return this; }
    setStep(step) { this.item.step = step; if (this.range) this.range.step = step; this.paint(); return this; }
    setOptions(options) { this.item.options = options; this.rebuildOptions && this.rebuildOptions(); this.paint(); return this; }
    show() { this.item.hidden = false; this.gui.refresh(); return this; }
    hide() { this.item.hidden = true; this.gui.refresh(); return this; }
    lock() { this.wrap.classList.add('locked'); return this; }
    unlock() { this.wrap.classList.remove('locked'); return this; }
    setBroadcast(b) { this.broadcast = !!b; return this; }
    moveTo(group, tab) { this.item.group = group; if (tab) this.item.tab = tab; this.gui._place(this); this.gui.refresh(); return this; }
    onChange(fn) { this.listeners.push(fn); return this; }
    getValue() { return this.gui.state[this.key]; }
    // --- internal
    emit(v) { if (!this.broadcast) return; this.listeners.forEach(fn => fn(v, this)); this.gui._changed(this.key, v); }
    paint() {}
  }

  class SliderController extends Controller {
    build() {
      const { item } = this;
      const row = el('div', 'row');
      this.labelEl = el('label', null, item.label);
      this.num = el('input', 'num'); this.num.type = 'text'; this.num.spellcheck = false;
      row.append(this.labelEl, this.num);
      this.range = el('input'); this.range.type = 'range';
      this.range.min = item.min; this.range.max = item.max; this.range.step = item.step;
      this.wrap.append(row, this.range);
      this.range.addEventListener('input', () => { this.gui.state[this.key] = Number(this.range.value); this.num.value = fmt(this.range.value, item.step); this.emit(this.getValue()); });
      const commit = () => { const v = Number(this.num.value); if (!isNaN(v)) { this.gui.state[this.key] = item.clamp === false ? v : clamp(v, item.min, item.max); this.paint(); this.emit(this.getValue()); } else this.paint(); };
      this.num.addEventListener('change', commit);
      this.num.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); this.num.blur(); } });
      return this;
    }
    paint() { const v = this.getValue(); this.range.value = v; this.num.value = fmt(v, this.item.step); }
  }

  class NumberController extends Controller {       // numberbox: value only, drag up/down or type
    build() {
      const { item } = this;
      const row = el('div', 'row');
      this.labelEl = el('label', null, item.label);
      this.num = el('input', 'num'); this.num.type = 'text'; this.num.spellcheck = false;
      row.append(this.labelEl, this.num);
      this.wrap.append(row);
      const commit = () => { const v = Number(this.num.value); if (!isNaN(v)) { this.gui.state[this.key] = clamp(v, item.min ?? -Infinity, item.max ?? Infinity); this.paint(); this.emit(this.getValue()); } else this.paint(); };
      this.num.addEventListener('change', commit);
      this.num.addEventListener('keydown', e => {
        const s = Number(item.step || 1) * (e.shiftKey ? 10 : 1);
        if (e.key === 'ArrowUp') { e.preventDefault(); this.num.value = fmt(this.getValue() + s, item.step); commit(); }
        if (e.key === 'ArrowDown') { e.preventDefault(); this.num.value = fmt(this.getValue() - s, item.step); commit(); }
        if (e.key === 'Enter') { e.preventDefault(); this.num.blur(); }
      });
      return this;
    }
    paint() { this.num.value = fmt(this.getValue(), this.item.step); }
  }

  class SegController extends Controller {           // radio as a segmented strip
    build() {
      const { item } = this;
      this.labelEl = el('div', 'seglabel', item.label);
      this.seg = el('div', 'cg-seg' + (item.wrap ? ' wrap' : ''));
      if (item.wrap) this.seg.style.setProperty('--cols', item.wrap);
      this.wrap.append(this.labelEl, this.seg);
      this.rebuildOptions();
      return this;
    }
    rebuildOptions() {
      this.seg.innerHTML = ''; this.btns = [];
      (this.item.options || []).forEach(opt => {
        const [val, label] = Array.isArray(opt) ? opt : [opt, String(opt)];
        const b = el('button', null, label); b.type = 'button'; b.dataset.val = val;
        b.addEventListener('click', () => { this.gui.state[this.key] = val; this.paint(); this.gui.refresh(); this.emit(val); });
        this.seg.appendChild(b); this.btns.push(b);
      });
    }
    paint() { const v = String(this.getValue()); this.btns.forEach(b => b.classList.toggle('on', b.dataset.val === v)); }
  }

  class ToggleController extends Controller {
    build() {
      const lab = el('label', 'cg-toggle');
      this.inp = el('input'); this.inp.type = 'checkbox';
      const box = el('span', 'box');
      this.labelEl = el('span', null, this.item.label);
      lab.append(this.inp, box, this.labelEl);
      this.wrap.append(lab);
      this.inp.addEventListener('change', () => { this.gui.state[this.key] = this.inp.checked; this.gui.refresh(); this.emit(this.inp.checked); });
      return this;
    }
    paint() { this.inp.checked = !!this.getValue(); }
  }

  class SelectController extends Controller {
    build() {
      this.labelEl = el('div', 'seglabel', this.item.label);
      this.sel = el('select', 'pick');
      this.wrap.append(this.labelEl, this.sel);
      this.rebuildOptions();
      this.sel.addEventListener('change', () => { this.gui.state[this.key] = this.sel.value; this.gui.refresh(); this.emit(this.sel.value); });
      return this;
    }
    rebuildOptions() {
      this.sel.innerHTML = '';
      (this.item.options || []).forEach(opt => { const [val, label] = Array.isArray(opt) ? opt : [opt, String(opt)]; const o = el('option', null, label); o.value = val; this.sel.appendChild(o); });
    }
    paint() { this.sel.value = this.getValue(); }
  }

  class TextController extends Controller {
    build() {
      const { item } = this;
      this.labelEl = el('div', 'seglabel', item.label);
      if (item.rows && item.rows > 1) { this.ta = el('textarea', 'txt'); this.ta.rows = item.rows; }
      else { this.ta = el('input', 'txt'); this.ta.type = 'text'; }
      this.ta.spellcheck = false;
      if (item.placeholder) this.ta.placeholder = item.placeholder;
      this.wrap.append(this.labelEl, this.ta);
      this.ta.addEventListener('input', () => { this.gui.state[this.key] = this.ta.value; this.emit(this.ta.value); });
      return this;
    }
    paint() { this.ta.value = this.getValue() ?? ''; }
  }

  class FileController extends Controller {
    build() {
      const { item } = this;
      this.labelEl = el('div', 'seglabel', item.label);
      this.inp = el('input'); this.inp.type = 'file'; if (item.accept) this.inp.accept = item.accept;
      const pick = el('label', 'act file'); pick.append(el('span', null, item.button || 'Choose file'), this.inp);
      this.note = el('div', 'cg-note', item.empty || 'No file loaded.');
      this.wrap.append(this.labelEl, pick, this.note);
      this.inp.addEventListener('change', async () => {
        const f = this.inp.files[0]; if (!f) return;
        const v = item.read === 'text' ? await f.text() : item.read === 'dataurl' ? await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); }) : f;
        this.gui.state[this.key] = v;
        this.note.innerHTML = ''; const b = el('b', null, f.name); this.note.append(b, ` · ${(f.size / 1024).toFixed(1)} kB`);
        this.emit(v);
      });
      return this;
    }
  }

  class ButtonController extends Controller {        // bang: fires, carries no value
    build() {
      this.btn = el('button', 'act' + (this.item.primary ? ' primary' : ''), this.item.label); this.btn.type = 'button';
      this.labelEl = this.btn;
      this.wrap.append(this.btn);
      this.btn.addEventListener('click', () => { this.listeners.forEach(fn => fn(this)); if (this.item.onClick) this.item.onClick(this.gui.state, this.gui); this.gui._bang(this.key); });
      return this;
    }
  }

  class NoteController extends Controller {
    build() { this.note = el('div', 'cg-note'); this.wrap.append(this.note); this.paint(); return this; }
    paint() { const v = this.item.html ?? this.gui.state[this.key] ?? this.item.text ?? ''; if (this.item.html != null) this.note.innerHTML = v; else this.note.textContent = v; }
    setText(t) { this.item.text = t; this.item.html = null; this.paint(); return this; }
    setHTML(h) { this.item.html = h; this.paint(); return this; }
  }

  const TYPES = { slider: SliderController, number: NumberController, seg: SegController, toggle: ToggleController,
                  select: SelectController, text: TextController, file: FileController, button: ButtonController, note: NoteController };

  /* ---------------------------------------------------------------- ControlGUI */
  class ControlGUI {
    constructor(opts = {}) {
      this.opts = Object.assign({ title: 'CONTROL', tagline: '', debounce: 180, readout: 'card', shortcuts: true, collapsible: false }, opts);
      this.state = Object.assign({}, opts.state || {});
      this.ctls = {}; this.order = []; this.groups = {}; this.tabs = []; this.activeTab = null;
      this.handlers = { change: [], commit: [], bang: [], tab: [] };
      this.bound = [];
      this._pending = null;
      this._dom();
      if (this.opts.shortcuts) document.addEventListener('keydown', e => { if (e.altKey && (e.key === 'h' || e.key === 'H')) { e.preventDefault(); this.togglePanel(); } });
    }

    _dom() {
      const o = this.opts;
      const host = typeof o.mount === 'string' ? document.querySelector(o.mount) : (o.mount || document.body);
      this.shell = el('div', 'cg-shell');
      this.panel = el('div', 'cg-panel');
      this.brand = el('div', 'cg-brand');
      this.brand.append(el('h1', null, o.title), el('span', null, o.tagline));
      this.tabStrip = el('div', 'cg-tabs'); this.tabStrip.style.display = 'none';
      this.controls = el('div', 'cg-controls');
      this.foot = el('div', 'cg-foot'); this.foot.style.display = 'none';
      this.panel.append(this.brand, this.tabStrip, this.controls, this.foot);
      this.stage = el('div', 'cg-stage');
      this.staleEl = el('div', 'cg-stale');
      this.hudEl = el('div', 'cg-hud');
      this.readoutEl = el('div', 'cg-readout ' + o.readout);
      this.warnEl = el('div', 'cg-warn');
      this.errEl = el('div', 'cg-err');
      this.stage.append(this.staleEl, this.hudEl, this.readoutEl, this.warnEl, this.errEl);
      if (o.status) { this.statusEl = el('div', 'cg-status'); this.statusMsg = el('div', 'msg'); this.statusErr = el('div', 'err'); this.statusEl.append(this.statusMsg, this.statusErr); this.stage.append(this.statusEl); this.stage.classList.add('has-status'); }
      this.shell.append(this.panel, this.stage);
      host.appendChild(this.shell);
      if (o.hud) this.hud(o.hud);
    }

    /* ---- building */
    add(type, key, item = {}) {
      if (this.ctls[key]) throw new Error(`controlGUI: duplicate key "${key}"`);
      const Cls = TYPES[type]; if (!Cls) throw new Error(`controlGUI: unknown type "${type}"`);
      item = Object.assign({ label: key.replace(/_/g, ' '), group: item.group || 'Controls' }, item, { type });
      if (type === 'slider' || type === 'number') { item.min ??= 0; item.max ??= 100; item.step ??= 1; }
      if (!(key in this.state)) this.state[key] = item.value ?? this._defaultFor(item);
      const c = new Cls(this, key, item).build();
      this.ctls[key] = c; this.order.push(key);
      this._place(c);
      c.paint();
      this.refresh();
      return c;
    }
    _defaultFor(item) {
      switch (item.type) {
        case 'slider': case 'number': return item.min;
        case 'toggle': return false;
        case 'seg': case 'select': { const o = item.options && item.options[0]; return Array.isArray(o) ? o[0] : o; }
        case 'text': return '';
        default: return null;
      }
    }
    addSlider(k, o) { return this.add('slider', k, o); }
    addNumber(k, o) { return this.add('number', k, o); }
    addSeg(k, o) { return this.add('seg', k, o); }
    addRadio(k, o) { return this.add('seg', k, o); }
    addToggle(k, o) { return this.add('toggle', k, o); }
    addSelect(k, o) { return this.add('select', k, o); }
    addText(k, o) { return this.add('text', k, o); }
    addFile(k, o) { return this.add('file', k, o); }
    addButton(k, o) { return this.add('button', k, o); }
    addBang(k, o) { return this.add('button', k, o); }
    addNote(k, o) { return this.add('note', k, o); }

    /** Build from a schema array: [{ key, type, label, group, tab, min, max, step, value, options, wrap, show, family }] */
    fromSchema(schema) { schema.forEach(it => { const { key, type, ...rest } = it; this.add(type, key, rest); }); return this; }

    /** Pinned foot: a name field and an action button (export). */
    addFoot({ name = 'part', nameKey = 'name', label = 'Export', onClick, hint } = {}) {
      this.foot.style.display = '';
      if (nameKey) {
        this.nameInput = el('input', 'name'); this.nameInput.value = this.state[nameKey] ?? name; this.nameInput.spellcheck = false;
        this.state[nameKey] = this.nameInput.value;
        this.nameInput.addEventListener('input', () => { this.state[nameKey] = this.nameInput.value; });
        this.foot.append(this.nameInput);
      }
      const b = el('button', 'act', label); b.type = 'button';
      b.addEventListener('click', () => onClick && onClick(this.state, this));
      this.foot.append(b);
      if (hint) this.foot.append(el('div', 'hint', hint));
      this.footButton = b;
      return this;
    }

    _group(name, tab) {
      const id = (tab ? tab + ':' : '') + name;
      if (this.groups[id]) return this.groups[id];
      const g = el('div', 'cg-group' + (this.opts.collapsible ? ' collapsible' : ''));
      g.dataset.tab = tab || '';
      g.dataset.name = name;
      const h = el('h2'); h.append(el('span', null, name));
      const body = el('div', 'cg-body');
      g.append(h, body);
      if (this.opts.collapsible) { const i = el('i', null, '—'); h.append(i); h.addEventListener('click', () => { g.classList.toggle('closed'); i.textContent = g.classList.contains('closed') ? '+' : '—'; }); }
      this.controls.appendChild(g);
      this.groups[id] = g;
      if (tab && !this.tabs.includes(tab)) { this.tabs.push(tab); this._paintTabs(); }
      return g;
    }
    _place(c) { const g = this._group(c.item.group, c.item.tab); g.querySelector('.cg-body').appendChild(c.wrap); }
    _paintTabs() {
      this.tabStrip.innerHTML = '';
      if (this.tabs.length < 2) { this.tabStrip.style.display = 'none'; this.activeTab = this.tabs[0] || null; return; }
      this.tabStrip.style.display = '';
      if (!this.activeTab) this.activeTab = this.tabs[0];
      this.tabs.forEach(t => { const b = el('button', null, t); b.type = 'button'; b.classList.toggle('on', t === this.activeTab); b.addEventListener('click', () => this.tab(t)); this.tabStrip.appendChild(b); });
    }
    tab(name) { this.activeTab = name; this._paintTabs(); this.refresh(); this.handlers.tab.forEach(fn => fn(name, this)); return this; }
    group(name, tab) { const g = this._group(name, tab); return { el: g, hide: () => { g.classList.add('hidden'); return this; }, show: () => { g.classList.remove('hidden'); return this; }, open: () => { g.classList.remove('closed'); return this; }, close: () => { g.classList.add('closed'); return this; } }; }

    /* ---- visibility rules */
    visible(item) {
      if (item.hidden) return false;
      if (item.family != null && String(this.state.family) !== String(item.family)) return false;
      if (typeof item.when === 'function' && !item.when(this.state)) return false;
      const s = item.show; if (!s) return true;
      const rules = Array.isArray(s) ? s : [s];
      return rules.every(r => {
        const v = this.state[r.key];
        if (r.in) return r.in.map(String).includes(String(v));
        if (r.not) return !r.not.map(String).includes(String(v));
        if (r.eq !== undefined) return String(v) === String(r.eq);
        if (r.gt !== undefined) return Number(v) > r.gt;
        if (r.lt !== undefined) return Number(v) < r.lt;
        if (r.truthy) return !!v;
        return true;
      });
    }
    refresh() {
      Object.values(this.ctls).forEach(c => { c.wrap.classList.toggle('hidden', !this.visible(c.item)); });
      Object.values(this.groups).forEach(g => {
        const inTab = !g.dataset.tab || g.dataset.tab === this.activeTab;
        const any = [...g.querySelectorAll('.cg-ctl')].some(e => !e.classList.contains('hidden'));
        g.classList.toggle('hidden', !(inTab && any) || g.classList.contains('force-hidden'));
      });
      return this;
    }

    /* ---- values + events */
    get(key) { return this.state[key]; }
    controller(key) { return this.ctls[key]; }
    set(key, value, { broadcast = true, refresh = true } = {}) {
      this.state[key] = value;
      const c = this.ctls[key]; if (c) c.paint();
      if (refresh) this.refresh();
      if (broadcast) { if (c) { c.listeners.forEach(fn => fn(value, c)); } this._changed(key, value); }
      return this;
    }
    setAll(values, opts) { Object.entries(values).forEach(([k, v]) => this.set(k, v, Object.assign({ refresh: false }, opts))); this.refresh(); return this; }
    on(event, fn) { (this.handlers[event] || (this.handlers[event] = [])).push(fn); return this; }
    off(event, fn) { const h = this.handlers[event]; if (h) this.handlers[event] = h.filter(f => f !== fn); return this; }
    bind(obj) { this.bound.push(obj); Object.keys(this.ctls).forEach(k => { if (k in this.state && typeof obj[k] !== 'function') obj[k] = this.state[k]; }); return this; }
    _changed(key, value) {
      this.bound.forEach(o => { if (typeof o[key] === 'function') o[key](value, this.state); else o[key] = value; });
      this.handlers.change.forEach(fn => fn(key, value, this.state, this));
      clearTimeout(this._pending);
      this._pending = setTimeout(() => this.handlers.commit.forEach(fn => fn(this.state, this)), this.opts.debounce);
    }
    _bang(key) { this.handlers.bang.forEach(fn => fn(key, this.state, this)); this.bound.forEach(o => { if (typeof o[key] === 'function') o[key](this.state); }); }
    commit() { clearTimeout(this._pending); this.handlers.commit.forEach(fn => fn(this.state, this)); return this; }

    /* ---- panel-level */
    hide(key) { if (key) { this.ctls[key] && this.ctls[key].hide(); } else this.shell.classList.add('cg-hidden-panel'); return this; }
    show(key) { if (key) { this.ctls[key] && this.ctls[key].show(); } else this.shell.classList.remove('cg-hidden-panel'); return this; }
    togglePanel() { this.shell.classList.toggle('cg-hidden-panel'); return this; }
    lock(key) { if (key) this.ctls[key] && this.ctls[key].lock(); else Object.values(this.ctls).forEach(c => c.lock()); return this; }
    unlock(key) { if (key) this.ctls[key] && this.ctls[key].unlock(); else Object.values(this.ctls).forEach(c => c.unlock()); return this; }
    remove(key) { const c = this.ctls[key]; if (!c) return this; c.wrap.remove(); delete this.ctls[key]; this.order = this.order.filter(k => k !== key); this.refresh(); return this; }

    /* ---- properties (save / load) */
    save() { return JSON.stringify({ controlGUI: 1, title: this.opts.title, state: this.state }, null, 2); }
    load(json) { const j = typeof json === 'string' ? JSON.parse(json) : json; this.setAll(j.state || j, { broadcast: false }); this.commit(); return this; }
    download(filename) {
      const name = filename || (this.opts.title.toLowerCase() + '_parameters.json');
      const a = el('a'); a.href = URL.createObjectURL(new Blob([this.save()], { type: 'application/json' })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      return this;
    }
    toQuery() { const q = new URLSearchParams(); Object.entries(this.state).forEach(([k, v]) => { if (v == null || typeof v === 'object') return; q.set(k, String(v)); }); return q; }
    fromQuery(search) {
      const q = new URLSearchParams(search ?? location.search); const vals = {};
      q.forEach((v, k) => { if (!(k in this.state)) return; const cur = this.state[k];
        vals[k] = typeof cur === 'number' ? Number(v) : typeof cur === 'boolean' ? (v === 'true' || v === '1') : v; });
      this.setAll(vals, { broadcast: false }); return this;
    }

    /* ---- stage: hud, readout, warnings, error, busy */
    hud(html) { this.hudEl.innerHTML = html; return this; }
    /** entries: [[label, value, 'hot'|'warn'|undefined], ...] or an object {label: value} */
    readout(entries) {
      const list = Array.isArray(entries) ? entries : Object.entries(entries || {});
      if (this.opts.readout === 'strip') {
        this.readoutEl.innerHTML = '';
        list.forEach(([k, v, flag]) => { const cell = el('div'); cell.append(el('dt', null, k), el('dd', flag || null, String(v))); this.readoutEl.appendChild(cell); });
      } else {
        this.readoutEl.innerHTML = '';
        if (!list.length) return this;
        const dl = el('dl');
        list.forEach(([k, v, flag]) => { dl.append(el('dt', null, k), el('dd', flag || null, String(v))); });
        this.readoutEl.appendChild(dl);
      }
      return this;
    }
    warn(lines) { this.warnEl.innerHTML = ''; (lines || []).forEach(t => this.warnEl.appendChild(el('div', 'w', t))); return this; }
    error(msg) { this.errEl.textContent = msg || ''; if (this.statusErr) this.statusErr.textContent = msg || ''; return this; }
    status(msg) { if (this.statusMsg) this.statusMsg.textContent = msg || ''; return this; }
    busy(on) { this.staleEl.classList.toggle('on', !!on); if (this.statusMsg) this.statusMsg.classList.toggle('cg-busy', !!on); return this; }
  }

  ControlGUI.Controller = Controller;
  ControlGUI.TYPES = TYPES;
  ControlGUI.VERSION = '1.0.0';
  root.ControlGUI = ControlGUI;
  if (typeof module !== 'undefined' && module.exports) module.exports = ControlGUI;
})(typeof window !== 'undefined' ? window : globalThis);
