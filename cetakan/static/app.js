"use strict";

const $ = (s) => document.querySelector(s);
const CM = 37.7953;   // piksel per cm pada 96 dpi
const PT = 96 / 72;   // piksel per pt

const state = {
  roles: {},            // kode peran → label
  formats: {},
  format: "docx",
  tpl: null,            // { id, name, data, overrides }
  content: null,        // { id, blocks, warnings }
  mode: "text",
  docFile: null,
  roleOverrides: {},    // kunci teks blok → peran pilihan pengguna
  previewItems: [],
  seq: 0,
};

const ROLE_ORDER = ["judul", "penulis", "bab", "bab_nama", "h1", "h2", "h3", "paragraf", "abstrak",
  "kata_kunci", "daftar", "lanjutan", "kutipan", "kode", "gambar", "keterangan_gambar", "keterangan_tabel",
  "pustaka", "abaikan"];
const DOC_RE = /\.(docx|pdf|doc|odt|rtf)$/i;

const store = {
  get(k) { try { return localStorage.getItem("cetakan." + k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem("cetakan." + k, v); } catch { /* mode privat */ } },
};

// ---------------------------------------------------------------------------
// utilitas
// ---------------------------------------------------------------------------
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function setStatus(msg, kind = "") {
  const el = $("#status");
  el.className = "status " + kind;
  el.innerHTML = msg;
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* bukan JSON */ }
    throw new Error(detail);
  }
  return res;
}

function postJSON(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

function fmtNum(n) { return String(Math.round(n * 100) / 100).replace(".", ","); }

function blockKey(b) { return (b.kind || "p") + "|" + (b.text || "").slice(0, 400); }

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------------------------------------------------------------------------
// gaya → CSS
// ---------------------------------------------------------------------------
function paraCSS(st) {
  if (!st) return "";
  const out = [];
  if (st.font) out.push(`font-family:"${st.font}","Times New Roman",serif`);
  out.push(`font-size:${(st.size || 11)}pt`);
  if (st.bold) out.push("font-weight:700");
  if (st.italic) out.push("font-style:italic");
  if (st.underline) out.push("text-decoration:underline");
  if (st.caps) out.push("text-transform:uppercase");
  if (st.small_caps) out.push("font-variant:small-caps");
  if (st.color && /^[0-9A-Fa-f]{6}$/.test(st.color)) out.push(`color:#${st.color}`);
  out.push(`text-align:${st.align || "left"}`);
  if (st.line_pt) out.push(`line-height:${st.line_pt}pt`);
  else out.push(`line-height:${((st.line_mult || 1) * 1.16).toFixed(3)}`);
  out.push(`padding-top:${st.before || 0}pt`, `padding-bottom:${st.after || 0}pt`);
  if (st.ind_left) out.push(`padding-left:${st.ind_left}cm`);
  if (st.ind_right) out.push(`padding-right:${st.ind_right}cm`);
  if (st.first_line) out.push(`text-indent:${st.first_line}cm`);
  return out.join(";");
}

function describeStyle(st, pageBreak) {
  if (!st) return "";
  const parts = [];
  parts.push(`${st.font || "Bawaan"} ${fmtNum(st.size || 11)} pt`);
  const deco = [];
  if (st.bold) deco.push("tebal");
  if (st.italic) deco.push("miring");
  if (st.underline) deco.push("garis bawah");
  if (st.caps || st.upper) deco.push("KAPITAL");
  if (deco.length) parts.push(deco.join(" "));
  parts.push({ left: "rata kiri", center: "rata tengah", right: "rata kanan", justify: "rata kiri-kanan" }[st.align] || "rata kiri");
  if (st.line_pt) parts.push(`spasi ${fmtNum(st.line_pt)} pt`);
  else if (st.line_mult) parts.push(`spasi ${fmtNum(st.line_mult)}`);
  if (st.first_line > 0) parts.push(`menjorok ${fmtNum(st.first_line)} cm`);
  if (st.first_line < 0) parts.push(`gantung ${fmtNum(-st.first_line)} cm`);
  if (st.ind_left > 0) parts.push(`kiri ${fmtNum(st.ind_left)} cm`);
  if (st.before) parts.push(`sebelum ${fmtNum(st.before)} pt`);
  if (st.after) parts.push(`sesudah ${fmtNum(st.after)} pt`);
  if (st.auto_num) parts.push("nomor otomatis");
  if (pageBreak) parts.push("halaman baru");
  return parts.join(" · ");
}

// ---------------------------------------------------------------------------
// 1. contoh format
// ---------------------------------------------------------------------------
async function uploadTemplate(file) {
  if (!file) return;
  if (!DOC_RE.test(file.name)) {
    setStatus(`Contoh harus .docx atau .pdf (<b>${esc(file.name)}</b> tidak didukung).`, "err");
    return;
  }
  setStatus(/\.pdf$/i.test(file.name)
    ? '<span class="spinner"></span>Membaca tata letak PDF dan mempelajari formatnya…'
    : '<span class="spinner"></span>Mempelajari format contoh…');
  const fd = new FormData();
  fd.append("file", file);
  try {
    const data = await (await api("/api/template", { method: "POST", body: fd })).json();
    state.tpl = { id: data.template_id, name: file.name, data, overrides: {} };
    $("#saveName").value = file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
    renderTemplate();
    renderLibrary();
    setStatus(`Format dipelajari dari <b>${esc(file.name)}</b>.`, "ok");
    await parseContent();
  } catch (e) {
    setStatus(esc(e.message), "err");
  }
}

function renderTemplate() {
  const t = state.tpl;
  $("#tplDrop").classList.toggle("hidden", !!t);
  $("#tplInfo").classList.toggle("hidden", !t);
  if (!t) return;
  const d = t.data;
  $("#tplName").textContent = t.name;
  const pg = d.page;
  const paper = Math.abs(pg.width - 21) < 0.2 && Math.abs(pg.height - 29.7) < 0.2 ? "A4"
    : Math.abs(pg.width - 21.59) < 0.2 && Math.abs(pg.height - 27.94) < 0.2 ? "Letter"
    : Math.abs(pg.width - 21.5) < 0.2 && Math.abs(pg.height - 33) < 0.3 ? "F4/Folio" : `${fmtNum(pg.width)}×${fmtNum(pg.height)} cm`;
  $("#tplPage").textContent = `Kertas ${paper} · margin atas ${fmtNum(pg.top)}, bawah ${fmtNum(pg.bottom)}, kiri ${fmtNum(pg.left)}, kanan ${fmtNum(pg.right)} cm · ${Object.keys(d.roles).length} gaya dipelajari`;

  const box = $("#tplRoles");
  box.innerHTML = "";
  for (const r of ROLE_ORDER) {
    const info = d.roles[r];
    if (!info) continue;
    const st = { ...info.style };
    const sample = document.createElement("div");
    sample.className = "lrole";
    const sampleCSS = paraCSS({ ...st, before: 0, after: 0, first_line: 0, ind_left: 0, ind_right: 0, line_mult: 1, line_pt: null, size: Math.min(Math.max(st.size || 11, 9), 15) });
    sample.innerHTML = `<div class="lrole-top"><b>${esc(info.label)}</b><span>paragraf #${info.index + 1}</span></div>
      <div class="lrole-sample" style="${esc(sampleCSS)}">${esc(info.sample || "—")}</div>
      <div class="lrole-attr">${esc(describeStyle(st, info.page_break))}</div>`;
    box.appendChild(sample);
    for (const c of d.context_roles || []) {
      if (c.role !== r) continue;
      const cs = { ...c.style };
      const el = document.createElement("div");
      el.className = "lrole ctx";
      el.innerHTML = `<div class="lrole-top"><b>${esc(c.label)}</b><span>paragraf #${c.index + 1}</span></div>
        <div class="lrole-attr">${esc(describeStyle(cs, false))}</div>`;
      box.appendChild(el);
    }
  }

  const list = $("#tplParas");
  list.innerHTML = "";
  const opts = ROLE_ORDER.map((r) => `<option value="${r}">${esc(state.roles[r] || r)}</option>`).join("");
  const frag = document.createDocumentFragment();
  for (const p of d.paragraphs) {
    const row = document.createElement("div");
    row.className = "para-row" + (t.overrides[p.i] ? " changed" : "");
    row.innerHTML = `<span class="t" title="${esc(p.text)}">${esc(p.text)}</span><select aria-label="Peran paragraf ${p.i + 1}">${opts}</select>`;
    const sel = row.querySelector("select");
    sel.value = p.role;
    sel.addEventListener("change", () => changeTemplateRole(p.i, sel.value));
    frag.appendChild(row);
  }
  list.appendChild(frag);
}

async function changeTemplateRole(i, role) {
  state.tpl.overrides[i] = role;
  try {
    const data = await (await postJSON(`/api/template/${state.tpl.id}/roles`, { overrides: state.tpl.overrides })).json();
    state.tpl.data = data;
    const open = $("#tplInspect").open;
    const scroll = $("#tplParas").scrollTop;
    renderTemplate();
    $("#tplInspect").open = open;
    $("#tplParas").scrollTop = scroll;
    await parseContent();
  } catch (e) {
    handleError(e);
  }
}

// ---------------------------------------------------------------------------
// pustaka format tersimpan
// ---------------------------------------------------------------------------
async function loadLibrary() {
  try {
    state.library = (await (await api("/api/library")).json()).formats;
  } catch { state.library = []; }
  renderLibrary();
}

function renderLibrary() {
  const list = state.library || [];
  $("#library").classList.toggle("hidden", !list.length);
  const box = $("#libList");
  box.innerHTML = "";
  for (const f of list) {
    const item = document.createElement("span");
    item.className = "lib-item" + (state.tpl && state.tpl.id === f.id ? " active" : "");
    item.innerHTML = `<button type="button" title="Pakai format ini">${esc(f.name)}</button><button type="button" class="del" aria-label="Hapus format ${esc(f.name)}" title="Hapus">×</button>`;
    item.firstChild.addEventListener("click", () => useFormat(f));
    item.lastChild.addEventListener("click", () => deleteFormat(f));
    box.appendChild(item);
  }
  const saved = state.tpl && list.some((f) => f.id === state.tpl.id);
  $("#saveBtn").textContent = saved ? "Perbarui" : "Simpan format";
}

async function useFormat(f) {
  setStatus('<span class="spinner"></span>Memuat format…');
  try {
    const data = await (await api(`/api/library/${f.id}/use`, { method: "POST" })).json();
    state.tpl = { id: data.template_id, name: data.name, data, overrides: data.overrides || {} };
    $("#saveName").value = data.name;
    renderTemplate();
    renderLibrary();
    setStatus(`Memakai format <b>${esc(data.name)}</b>.`, "ok");
    await parseContent();
  } catch (e) {
    setStatus(esc(e.message), "err");
  }
}

async function saveFormat(ev) {
  ev.preventDefault();
  if (!state.tpl) return;
  const name = $("#saveName").value.trim() || state.tpl.name;
  try {
    const data = await (await postJSON("/api/library", { template_id: state.tpl.id, name, overrides: state.tpl.overrides })).json();
    state.library = data.formats;
    state.tpl.name = name;
    $("#tplName").textContent = name;
    renderLibrary();
    setStatus(`Format <b>${esc(name)}</b> disimpan. Lain kali tinggal klik namanya.`, "ok");
  } catch (e) {
    setStatus(esc(e.message), "err");
  }
}

async function deleteFormat(f) {
  if (!confirm(`Hapus format “${f.name}”?`)) return;
  try {
    const res = await api(`/api/library/${f.id}`, { method: "DELETE" });
    state.library = (await res.json()).formats;
    renderLibrary();
  } catch (e) {
    setStatus(esc(e.message), "err");
  }
}

// ---------------------------------------------------------------------------
// 2. naskah
// ---------------------------------------------------------------------------
function hasInput() {
  return state.mode === "file" ? !!state.docFile : $("#text").value.trim().length > 0;
}

async function parseContent() {
  updateButtons();
  if (!hasInput()) {
    state.content = null;
    renderPreview(null);
    return;
  }
  const seq = ++state.seq;
  const fd = new FormData();
  if (state.tpl) fd.append("template_id", state.tpl.id);
  if (state.mode === "file") {
    fd.append("file", state.docFile);
    fd.append("skip_front", $("#skipFront").checked ? "true" : "false");
    if (/\.pdf$/i.test(state.docFile.name) && !state.content)
      setStatus('<span class="spinner"></span>Membaca tata letak PDF naskah…');
  }
  else {
    fd.append("text", $("#text").value);
    fd.append("merge_lines", $("#mergeLines").checked ? "true" : "false");
  }
  try {
    const data = await (await api("/api/content", { method: "POST", body: fd })).json();
    if (seq !== state.seq) return;
    state.content = { id: data.content_id, blocks: data.blocks, warnings: data.warnings };
    await refreshPreview(seq);
  } catch (e) {
    if (seq === state.seq) handleError(e);
  }
}

function roleMap() {
  const out = {};
  if (!state.content) return out;
  for (const b of state.content.blocks) {
    const r = state.roleOverrides[blockKey(b)];
    if (r && r !== b.auto) out[b.i] = r;
  }
  return out;
}

function request(format) {
  return {
    template_id: state.tpl.id, content_id: state.content.id, format,
    template_overrides: state.tpl.overrides, roles: roleMap(),
  };
}

async function refreshPreview(seq = ++state.seq) {
  updateButtons();
  if (!state.content) return renderPreview(null);
  if (!state.tpl) {
    renderPreview(fallbackPreview());
    return;
  }
  try {
    const data = await (await postJSON("/api/preview", request("docx"))).json();
    if (seq !== state.seq) return;
    renderPreview(data);
    const warns = [...new Set([...(state.content.warnings || []), ...(data.warnings || [])])];
    if (warns.length) setStatus("⚠ " + warns.map(esc).join("<br>⚠ "), "warn");
    else if ($("#status").classList.contains("err") || $("#status").classList.contains("warn")
             || $("#status .spinner")) setStatus("");
  } catch (e) {
    if (seq === state.seq) handleError(e);
  }
}

function handleError(e) {
  setStatus(esc(e.message), "err");
  if (/kedaluwarsa/.test(e.message) && /contoh/i.test(e.message)) {
    state.tpl = null;
    renderTemplate();
  }
}

// Tanpa contoh: tampilkan struktur hasil deteksi dengan gaya netral.
function fallbackPreview() {
  const base = { font: "Georgia", size: 11, align: "left", line_mult: 1.2, after: 6 };
  const headings = { judul: 16, bab: 14, bab_nama: 14, h1: 13, h2: 12, h3: 11.5 };
  const items = state.content.blocks.map((b) => {
    const role = state.roleOverrides[blockKey(b)] || b.role;
    if (b.kind === "table") return { b: b.i, role: "tabel", table: b.rows, style: base };
    const st = { ...base };
    if (headings[role]) Object.assign(st, { size: headings[role], bold: true, before: 8 });
    if (role === "judul" || role === "bab" || role === "bab_nama") st.align = "center";
    if (role === "daftar" || role === "kutipan") st.ind_left = 0.8;
    if (role === "pustaka") Object.assign(st, { ind_left: 1, first_line: -1 });
    const runs = (b.segs || []).map((s) => (s.media ? { media: true }
      : { ...s, b: s.b || undefined, i: s.i || undefined }));
    return { b: b.i, role, style: st, runs };
  });
  return { page: { width: 21, height: 29.7, top: 2.5, bottom: 2.5, left: 2.5, right: 2.5 }, items, neutral: true };
}

// ---------------------------------------------------------------------------
// pratinjau
// ---------------------------------------------------------------------------
function renderRuns(el, runs, paraStyle) {
  for (const r of runs || []) {
    if (r.media) {
      if (r.src) {
        const img = document.createElement("img");
        img.src = r.src;
        img.alt = "";
        img.className = "img";
        if (r.w) img.style.width = r.w + "cm";
        if (r.h) img.style.height = r.h + "cm";
        el.appendChild(img);
      } else {
        const m = document.createElement("span");
        m.className = "media";
        m.textContent = "gambar";
        el.appendChild(m);
      }
      continue;
    }
    let node = document.createTextNode(r.t);
    const css = [];
    if (r.b !== undefined && !!r.b !== !!paraStyle.bold) css.push(`font-weight:${r.b ? 700 : 400}`);
    if (r.i !== undefined && !!r.i !== !!paraStyle.italic) css.push(`font-style:${r.i ? "italic" : "normal"}`);
    if (r.u) css.push("text-decoration:underline");
    if (r.caps) css.push("text-transform:uppercase");
    if (r.size && paraStyle.size && Math.abs(r.size - paraStyle.size) > 0.1) css.push(`font-size:${r.size}pt`);
    if (r.font && r.font !== paraStyle.font) css.push(`font-family:"${r.font}",serif`);
    if (css.length || r.sup || r.sub) {
      const tag = r.sup ? "sup" : r.sub ? "sub" : "span";
      const s = document.createElement(tag);
      if (css.length) s.style.cssText = css.join(";");
      if (r.note !== undefined) { s.className = "fnref"; s.title = r.note; }
      s.appendChild(node);
      node = s;
    }
    el.appendChild(node);
  }
}

function renderPreview(data) {
  const pages = $("#pages");
  pages.innerHTML = "";
  $("#emptyState").classList.toggle("hidden", !!data);
  $("#counts").innerHTML = "";
  state.previewItems = data ? data.items : [];
  if (!data) return;
  $("#previewNote").textContent = data.neutral
    ? "Belum ada contoh format: struktur ditampilkan dengan gaya netral."
    : "Klik paragraf untuk mengubah perannya. Pratinjau ini perkiraan; PDF asli tersedia di langkah 3.";

  const pg = data.page;
  const pageW = pg.width * CM, pageH = pg.height * CM;
  const textW = (pg.width - pg.left - pg.right) * CM;
  const textH = (pg.height - pg.top - pg.bottom) * CM;

  // 1) susun semua paragraf dalam satu kolom untuk diukur
  pages.style.zoom = 1;
  const measure = document.createElement("div");
  measure.className = "page";
  measure.style.cssText = `position:absolute;visibility:hidden;left:-99999px;top:0;width:${textW}px`;
  pages.appendChild(measure);
  const els = [];
  const itemOf = new Map();
  const forced = roleMap();
  for (const it of data.items) {
    let el;
    if (it.table) {
      el = document.createElement("table");
      el.style.cssText = paraCSS({ ...it.style, before: 0, after: 0, first_line: 0 });
      el.innerHTML = it.table.map((r) => "<tr>" + r.map((c) => `<td>${esc(c)}</td>`).join("") + "</tr>").join("");
      el.dataset.b = it.b ?? "";
      el.addEventListener("click", (ev) => it.b != null && openPop(ev, it));
    } else {
      el = document.createElement("div");
      el.className = "pp" + (it.empty ? " empty" : "") + (it.b != null && forced[it.b] ? " forced" : "");
      el.style.cssText = paraCSS(it.style);
      if (it.label) el.appendChild(document.createTextNode(it.label + " "));
      renderRuns(el, it.runs, it.style || {});
      if (it.empty || !el.textContent) el.appendChild(document.createTextNode(" "));
      if (it.b != null && it.role && !it.empty) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = state.roles[it.role] || it.role;
        el.appendChild(tag);
        el.dataset.b = it.b;
        el.addEventListener("click", (ev) => openPop(ev, it));
      }
    }
    els.push({ el, it });
    itemOf.set(el, it);
    measure.appendChild(el);
  }

  // 2) potong menjadi halaman berdasarkan tinggi hasil ukur (satu kali tata letak)
  const pagesList = [[]];
  let top0 = 0;
  for (const { el, it } of els) {
    const top = el.offsetTop, bottom = top + el.offsetHeight;
    const cur = pagesList[pagesList.length - 1];
    if (cur.length && (it.page_break || bottom - top0 > textH)) {
      pagesList.push([]);
      top0 = top;
    }
    pagesList[pagesList.length - 1].push(el);
  }
  measure.remove();

  const scale = Math.min(1, ($("#paperWrap").clientWidth - 32) / pageW);
  pages.style.zoom = scale;
  const frag = document.createDocumentFragment();
  pagesList.forEach((list, n) => {
    const page = document.createElement("div");
    page.className = "page";
    page.style.cssText = `width:${pageW}px;min-height:${pageH}px;padding:${pg.top * CM}px ${pg.right * CM}px ${pg.bottom * CM}px ${pg.left * CM}px`;
    page.setAttribute("aria-label", `Halaman ${n + 1}`);
    const body = document.createElement("div");
    body.className = "page-body";
    for (const el of list) body.appendChild(el);
    page.appendChild(body);
    const notes = [];
    for (const el of list) {
      const it = itemOf.get(el);
      for (const r of (it && it.runs) || []) if (r.note !== undefined) notes.push(r);
    }
    if (notes.length) {
      const fn = document.createElement("div");
      fn.className = "fnotes";
      fn.style.fontFamily = (data.items.find((i) => i.style && i.style.font) || {}).style?.font || "";
      for (const r of notes) {
        const line = document.createElement("div");
        line.innerHTML = `<sup>${esc(r.t)}</sup> ${esc(r.note)}`;
        fn.appendChild(line);
      }
      page.appendChild(fn);
    }
    frag.appendChild(page);
  });
  pages.appendChild(frag);

  // ringkasan
  const count = {};
  for (const it of data.items) if (it.role && !it.empty) count[it.role] = (count[it.role] || 0) + 1;
  const heads = ["bab", "h1", "h2", "h3"].reduce((a, r) => a + (count[r] || 0), 0);
  const chips = [`${pagesList.length} halaman`];
  if (heads) chips.push(`${heads} judul`);
  if (count.paragraf) chips.push(`${count.paragraf} paragraf`);
  if (count.pustaka) chips.push(`${count.pustaka} pustaka`);
  if (count.tabel) chips.push(`${count.tabel} tabel`);
  $("#counts").innerHTML = chips.map((c) => `<span class="chip">${c}</span>`).join("");
}

// ---------------------------------------------------------------------------
// ubah peran blok naskah
// ---------------------------------------------------------------------------
let popTarget = null;

function openPop(ev, it) {
  ev.stopPropagation();
  const block = state.content?.blocks[it.b];
  if (!block) return;
  document.querySelectorAll(".pp.sel").forEach((e) => e.classList.remove("sel"));
  document.querySelectorAll(`[data-b="${it.b}"]`).forEach((e) => e.classList.add("sel"));
  popTarget = block;
  const cur = state.roleOverrides[blockKey(block)] || block.role;
  const grid = $("#popGrid");
  grid.innerHTML = "";
  const roles = block.kind === "table" ? ["abaikan"] : ROLE_ORDER;
  for (const r of roles) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = r === "abaikan" ? "Hapus dari hasil" : state.roles[r];
    if (r === cur) b.className = "cur";
    b.addEventListener("click", () => setBlockRole(block, r));
    grid.appendChild(b);
  }
  const pop = $("#rolePop");
  pop.classList.remove("hidden");
  const w = pop.offsetWidth, h = pop.offsetHeight;
  const x = Math.min(ev.clientX + 8, window.innerWidth - w - 8);
  const y = Math.min(ev.clientY + 8, window.innerHeight - h - 8);
  pop.style.left = Math.max(8, x) + "px";
  pop.style.top = Math.max(8, y) + "px";
}

function closePop() {
  $("#rolePop").classList.add("hidden");
  document.querySelectorAll(".pp.sel").forEach((e) => e.classList.remove("sel"));
  popTarget = null;
}

function setBlockRole(block, role) {
  const key = blockKey(block);
  if (role === block.auto) delete state.roleOverrides[key];
  else state.roleOverrides[key] = role;
  closePop();
  refreshPreview();
}

// ---------------------------------------------------------------------------
// 3. unduh
// ---------------------------------------------------------------------------
function renderFormats() {
  const box = $("#formats");
  box.innerHTML = "";
  for (const [k, f] of Object.entries(state.formats)) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "fmt";
    b.setAttribute("role", "radio");
    b.textContent = f.label.replace(/ \(.+\)/, "");
    b.title = f.available ? f.label : `${f.label} tidak tersedia di server ini`;
    b.disabled = !f.available;
    b.setAttribute("aria-checked", String(k === state.format));
    b.addEventListener("click", () => {
      state.format = k;
      store.set("format", k);
      renderFormats();
    });
    box.appendChild(b);
  }
}

function updateButtons() {
  const ready = !!(state.tpl && hasInput());
  $("#downloadBtn").disabled = !ready;
  $("#pdfBtn").disabled = !ready || !state.formats.pdf?.available;
  const f = state.formats[state.format];
  $("#downloadBtn").textContent = `Unduh ${f ? f.label.replace(/ \(.+\)/, "") : ""}`.trim();
}

async function produce(format, inline = false) {
  if (!state.content) await parseContent();
  if (!state.content || !state.tpl) return null;
  const body = { ...request(format), inline };
  const res = await postJSON("/api/generate", body);
  const blob = await res.blob();
  let name = "hasil-cetakan." + format;
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename\*=UTF-8''([^;]+)/);
  if (m) name = decodeURIComponent(m[1]);
  let warnings = [];
  try { warnings = JSON.parse(decodeURIComponent(res.headers.get("X-Cetakan-Warnings") || "%5B%5D")); } catch { /* abaikan */ }
  return { blob, name, warnings };
}

async function download() {
  const btn = $("#downloadBtn");
  btn.disabled = true;
  const label = btn.textContent;
  btn.innerHTML = '<span class="spinner"></span>Menyusun…';
  try {
    const out = await produce(state.format);
    if (!out) return;
    const url = URL.createObjectURL(out.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = out.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    const w = out.warnings.length ? "<br>⚠ " + out.warnings.map(esc).join("<br>⚠ ") : "";
    setStatus(`Selesai: <b>${esc(out.name)}</b>${w}`, out.warnings.length ? "warn" : "ok");
  } catch (e) {
    handleError(e);
  } finally {
    btn.textContent = label;
    updateButtons();
  }
}

async function showPdf() {
  const btn = $("#pdfBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Menyusun PDF…';
  try {
    const out = await produce("pdf", true);
    if (!out) return;
    const frame = $("#pdfFrame");
    if (frame.dataset.url) URL.revokeObjectURL(frame.dataset.url);
    const url = URL.createObjectURL(new Blob([out.blob], { type: "application/pdf" }));
    frame.dataset.url = url;
    frame.src = url;
    $("#pdfDialog").showModal();
  } catch (e) {
    handleError(e);
  } finally {
    btn.textContent = "Lihat PDF asli";
    updateButtons();
  }
}

// ---------------------------------------------------------------------------
// pemasangan
// ---------------------------------------------------------------------------
function wireDrop(zone, input, onFile) {
  input.addEventListener("change", () => { onFile(input.files[0]); input.value = ""; });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.tab === mode;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", String(on));
  });
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== mode));
  state.roleOverrides = {};
  parseContent();
}

function textStats() {
  const v = $("#text").value;
  const words = v.trim() ? v.trim().split(/\s+/).length : 0;
  $("#textStats").textContent = words ? `${words.toLocaleString("id-ID")} kata` : "";
}

async function init() {
  try {
    const info = await (await api("/api/info")).json();
    state.roles = info.roles;
    state.formats = info.formats;
  } catch (e) {
    setStatus("Server tidak dapat dihubungi: " + esc(e.message), "err");
    return;
  }
  const saved = store.get("format");
  if (saved && state.formats[saved]?.available) state.format = saved;
  renderFormats();

  wireDrop($("#tplDrop"), $("#tplFile"), uploadTemplate);
  $("#tplChange").addEventListener("click", () => $("#tplFile").click());
  wireDrop($("#docDrop"), $("#docFile"), (f) => {
    if (!f) return;
    if (!DOC_RE.test(f.name)) {
      setStatus(`Naskah harus .docx atau .pdf, atau salin teksnya ke tab “Ketik / tempel”.`, "err");
      return;
    }
    state.content = null;
    state.docFile = f;
    state.roleOverrides = {};
    $("#docName").textContent = f.name;
    $("#docRow").classList.remove("hidden");
    $("#docDrop").classList.add("hidden");
    parseContent();
  });
  $("#docClear").addEventListener("click", () => {
    state.docFile = null;
    $("#docRow").classList.add("hidden");
    $("#docDrop").classList.remove("hidden");
    parseContent();
  });

  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.tab)));
  const text = $("#text");
  text.value = store.get("draft") || "";
  $("#mergeLines").checked = store.get("merge") === "1";
  textStats();
  const onText = debounce(() => { store.set("draft", text.value); parseContent(); }, 350);
  text.addEventListener("input", () => { textStats(); updateButtons(); onText(); });
  $("#mergeLines").addEventListener("change", (e) => { store.set("merge", e.target.checked ? "1" : "0"); parseContent(); });
  $("#skipFront").checked = store.get("skipFront") !== "0";
  $("#skipFront").addEventListener("change", (e) => { store.set("skipFront", e.target.checked ? "1" : "0"); state.roleOverrides = {}; parseContent(); });
  $("#saveForm").addEventListener("submit", saveFormat);
  loadLibrary();

  $("#downloadBtn").addEventListener("click", download);
  $("#pdfBtn").addEventListener("click", showPdf);
  $("#pdfClose").addEventListener("click", () => $("#pdfDialog").close());
  $("#helpBtn").addEventListener("click", () => $("#helpDialog").showModal());
  $("#helpClose").addEventListener("click", () => $("#helpDialog").close());
  $("#popReset").addEventListener("click", () => popTarget && setBlockRole(popTarget, popTarget.auto));
  document.addEventListener("click", (e) => { if (!$("#rolePop").contains(e.target)) closePop(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePop(); });
  window.addEventListener("resize", debounce(() => {
    const pages = $("#pages");
    const first = pages.querySelector(".page");
    if (first) pages.style.zoom = Math.min(1, ($("#paperWrap").clientWidth - 32) / first.offsetWidth);
  }, 150));

  updateButtons();
  if (hasInput()) parseContent();
}

init();
