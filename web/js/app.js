// Interface do Crescidoro (web/PWA).
import {
  TIPOS, LABEL, COR, MOTIVOS, MOTIVO_DESC, Store, Timer, fmtMMSS, fmtDur, fmtCampo, fmtDT, parseDT,
  fimDe, diaDe, dayKey, keyToDate, hojeDate, fmtDia, fmtHM, porTipo, sequenciaAtual, novoId,
} from './core.js';
import { Grafico } from './chart.js';
import { Heatmap } from './heatmap.js';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const store = new Store();
const s = store.settings;
let vista = s.grafico_modo; // 'barras' | 'linha' | 'mapa'

// ================================================================ som / vibração / tela
const audio = new Audio('sucesso.mp3');
audio.preload = 'auto';
let audioLiberado = false;
document.addEventListener('pointerdown', () => {
  if (audioLiberado) return;
  audioLiberado = true;
  audio.muted = true;
  audio.play().then(() => { audio.pause(); audio.currentTime = 0; audio.muted = false; })
    .catch(() => { audio.muted = false; audioLiberado = false; });
}, { capture: true });

function tocar() {
  if (!s.som) return;
  try { audio.currentTime = 0; audio.play().catch(() => {}); } catch (e) { /* ignora */ }
}

let wakeLock = null;
async function syncWakeLock() {
  const quer = s.manter_tela && timer.rodando && document.visibilityState === 'visible';
  try {
    if (quer && !wakeLock && 'wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } else if (!quer && wakeLock) {
      await wakeLock.release();
      wakeLock = null;
    }
  } catch (e) { wakeLock = null; }
}

async function notificar(texto) {
  if (!s.notificar || !('Notification' in window) || Notification.permission !== 'granted') return;
  if (document.visibilityState === 'visible') return;
  try {
    const reg = await navigator.serviceWorker?.ready;
    const op = { body: texto, icon: 'icon-192.png', badge: 'icon-192.png', vibrate: [200, 100, 200], tag: 'crescidoro' };
    if (reg) reg.showNotification('crescidoro', op); else new Notification('crescidoro', op);
  } catch (e) { /* ignora */ }
}

// ================================================================ timer
const timer = new Timer(store, {
  onRegistro: (r) => {
    store.add(r);
    if (r.motivo !== 'natural') toast(`${LABEL[r.estado]} de ${fmtDur(r.duracao_s)} salvo como '${r.motivo}'`, desfazer);
  },
  onNatural: (tipo) => {
    tocar();
    if (s.vibrar && navigator.vibrate) navigator.vibrate([250, 120, 250]);
    const msg = tipo === 'pomodoro' && s.crescidoro_ativo
      ? `pomodoro concluído — próximo: ${fmtMMSS(s.pomodoro)}`
      : `${LABEL[tipo]} concluído`;
    toast(msg);
    notificar(msg);
    store.save();
  },
});

// ================================================================ toast
let toastTimer = 0;
function toast(msg, acao = null, ms = 4000) {
  const el = $('#toast');
  el.innerHTML = `<span>${esc(msg)}</span>${acao ? '<button>desfazer</button>' : ''}`;
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('on'));
  if (acao) $('button', el).onclick = () => { acao(); esconderToast(); };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(esconderToast, acao ? 6000 : ms);
}
function esconderToast() {
  const el = $('#toast');
  el.classList.remove('on');
  setTimeout(() => { if (!el.classList.contains('on')) el.hidden = true; }, 250);
}
function desfazer() {
  toast(store.undo() ? 'alteração desfeita' : 'nada para desfazer');
}

// ================================================================ bottom sheet
let aoFecharSheet = null;
function abrirSheet(html, { aoFechar } = {}) {
  const sh = $('#sheet'), veu = $('#veu');
  sh.innerHTML = `<div class="puxador"></div><button class="fechar" aria-label="fechar">
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>${html}`;
  $('.fechar', sh).onclick = fecharSheet;
  sh.hidden = false; veu.hidden = false;
  requestAnimationFrame(() => { sh.classList.add('on'); veu.classList.add('on'); });
  aoFecharSheet = aoFechar || null;
  return sh;
}
function fecharSheet() {
  const sh = $('#sheet'), veu = $('#veu');
  sh.classList.remove('on'); veu.classList.remove('on');
  setTimeout(() => { if (!sh.classList.contains('on')) { sh.hidden = true; veu.hidden = true; sh.innerHTML = ''; } }, 220);
  const f = aoFecharSheet; aoFecharSheet = null;
  if (f) f();
}
$('#veu').addEventListener('click', fecharSheet);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#sheet').hidden) fecharSheet(); });
// arrastar para baixo no puxador fecha
(() => {
  let y0 = null;
  const sh = $('#sheet');
  sh.addEventListener('touchstart', (e) => { if (e.target.closest('.puxador, .sheet-topo')) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener('touchmove', (e) => {
    if (y0 === null) return;
    const dy = Math.max(0, e.touches[0].clientY - y0);
    sh.style.transform = `translateY(${dy}px)`;
  }, { passive: true });
  sh.addEventListener('touchend', (e) => {
    if (y0 === null) return;
    const dy = e.changedTouches[0].clientY - y0;
    sh.style.transform = '';
    y0 = null;
    if (dy > 80) fecharSheet();
  });
})();

const limparSelecao = () => { grafico.selId = null; grafico.selDia = null; heat.selDia = null; grafico.pedirDesenho(); };

// ---------------------------------------------------------------- dia
function sheetDia(key) {
  const regs = store.registros.filter((r) => diaDe(r) === key);
  const pt = porTipo(regs);
  grafico.selDia = key; grafico.selId = null; grafico.pedirDesenho();
  const linhas = regs.map((r) => `
    <button class="linha-reg" data-id="${r.id}">
      <i style="background:${COR[r.estado]}"></i>
      <span class="hora">${fmtHM(parseDT(r.inicio))}–${fmtHM(fimDe(r))}</span>
      <span class="tipo" style="color:${COR[r.estado]}">${LABEL[r.estado]}</span>
      <span class="dur">${fmtDur(r.duracao_s)}</span>
      <span class="motivo">${r.motivo === 'desconhecido' ? '?' : r.motivo}</span>
    </button>`).join('');
  const resumo = TIPOS.filter((t) => pt[t]).map((t) => `<span style="color:${COR[t]}">${LABEL[t]} ${fmtDur(pt[t])}</span>`).join(' ');
  const sh = abrirSheet(`
    <div class="sheet-topo"><h2>${fmtDia(keyToDate(key))}</h2><div class="resumo">${resumo || 'sem registros'}</div></div>
    <div class="lista">${linhas || '<p class="vazio">nenhum registro neste dia</p>'}</div>
    <button class="btn largo" id="sh-novo">+ novo registro</button>`, { aoFechar: limparSelecao });
  $$('.linha-reg', sh).forEach((b) => (b.onclick = () => sheetRegistro(store.get(b.dataset.id))));
  $('#sh-novo', sh).onclick = () => sheetEditar(null, key);
}

// ---------------------------------------------------------------- registro
function sheetRegistro(r) {
  if (!r) return;
  grafico.selId = r.id; grafico.selDia = diaDe(r); grafico.pedirDesenho();
  const sh = abrirSheet(`
    <div class="sheet-topo">
      <h2 style="color:${COR[r.estado]}">${LABEL[r.estado]} · ${fmtDur(r.duracao_s)}</h2>
      <div class="resumo">${fmtDia(parseDT(r.inicio))} · ${fmtHM(parseDT(r.inicio))}–${fmtHM(fimDe(r))}</div>
      <div class="resumo fraco">fim: ${r.motivo} — ${MOTIVO_DESC[r.motivo] || ''}</div>
    </div>
    <div class="menu">
      <button id="m-editar">editar</button>
      <button id="m-dup">duplicar</button>
      <button id="m-dia">ver registros do dia</button>
      <button id="m-rem" class="perigo">remover</button>
    </div>`, { aoFechar: limparSelecao });
  $('#m-editar', sh).onclick = () => sheetEditar(r);
  $('#m-dup', sh).onclick = () => {
    store.add({ id: novoId(), estado: r.estado, inicio: fmtDT(fimDe(r)), duracao_s: r.duracao_s, motivo: 'manual' });
    fecharSheet();
    toast('registro duplicado', desfazer);
  };
  $('#m-dia', sh).onclick = () => sheetDia(diaDe(r));
  $('#m-rem', sh).onclick = () => { store.remove(r.id); fecharSheet(); toast('registro removido', desfazer); };
}

// ---------------------------------------------------------------- editar / novo
function segmentado(nome, opcoes, atual) {
  return `<div class="seg grande" data-nome="${nome}">${opcoes.map(([v, txt, cor]) =>
    `<button type="button" data-v="${v}" class="${v === atual ? 'on' : ''}" ${cor ? `style="--c:${cor}"` : ''}>${cor ? '<i></i>' : ''}${txt}</button>`).join('')}</div>`;
}
function ligarSegmentado(el, aoMudar) {
  $$('button', el).forEach((b) => (b.onclick = () => {
    $$('button', el).forEach((x) => x.classList.toggle('on', x === b));
    aoMudar && aoMudar(b.dataset.v);
  }));
}
const valorSeg = (el) => $('button.on', el)?.dataset.v;

function sheetEditar(r, key = null) {
  const novo = !r;
  if (novo) {
    key = key || dayKey(new Date());
    const regs = store.registros.filter((x) => diaDe(x) === key);
    let ini;
    if (regs.length) ini = new Date(Math.max(...regs.map((x) => fimDe(x).getTime())));
    else if (key === dayKey(new Date())) ini = new Date(Date.now() - 25 * 60e3);
    else { ini = keyToDate(key); ini.setHours(9); }
    ini.setSeconds(0);
    r = { id: novoId(), estado: 'pomodoro', inicio: fmtDT(ini), duracao_s: 25 * 60, motivo: 'manual' };
  }
  const ini = parseDT(r.inicio);
  const sh = abrirSheet(`
    <div class="sheet-topo"><h2>${novo ? 'novo registro' : 'editar registro'}</h2></div>
    <form class="form" autocomplete="off">
      ${segmentado('tipo', TIPOS.map((t) => [t, LABEL[t], COR[t]]), r.estado)}
      <div class="campos2">
        <label>data<input type="date" name="data" value="${dayKey(ini)}" required></label>
        <label>início<input type="time" name="hora" value="${fmtHM(ini)}" required></label>
      </div>
      <div class="campos2">
        <label>minutos<input type="number" name="min" inputmode="numeric" min="0" max="999" value="${Math.floor(r.duracao_s / 60)}"></label>
        <label>segundos<input type="number" name="seg" inputmode="numeric" min="0" max="59" value="${r.duracao_s % 60}"></label>
      </div>
      <div class="rotulo">fim</div>
      ${segmentado('motivo', MOTIVOS.map((m) => [m, m]), r.motivo)}
      <p class="dica" id="f-dica"></p>
      <div class="acoes-form">
        <button type="button" class="btn" id="f-cancelar">cancelar</button>
        <button type="submit" class="btn primario">salvar</button>
      </div>
    </form>`, { aoFechar: limparSelecao });
  const f = $('form', sh);
  $$('.seg', f).forEach((el) => ligarSegmentado(el, atualizarDica));
  function ler() {
    const [h, mi] = (f.hora.value || '').split(':').map(Number);
    const d = f.data.value ? keyToDate(f.data.value) : null;
    const dur = (parseInt(f.min.value, 10) || 0) * 60 + Math.min(59, parseInt(f.seg.value, 10) || 0);
    if (!d || Number.isNaN(h) || dur <= 0) return null;
    d.setHours(h, mi, 0, 0);
    if (!novo && fmtDT(d).slice(0, 16) === r.inicio.slice(0, 16)) d.setSeconds(ini.getSeconds());
    return { id: r.id, estado: valorSeg($('[data-nome=tipo]', f)), inicio: fmtDT(d), duracao_s: dur,
             motivo: valorSeg($('[data-nome=motivo]', f)) || r.motivo };
  }
  function atualizarDica() {
    const x = ler();
    $('#f-dica', sh).textContent = x ? `termina às ${fmtHM(fimDe(x))} · ${MOTIVO_DESC[x.motivo] || ''}` : 'preencha data, início e duração';
  }
  f.addEventListener('input', atualizarDica);
  atualizarDica();
  $('#f-cancelar', sh).onclick = fecharSheet;
  f.onsubmit = (e) => {
    e.preventDefault();
    const x = ler();
    if (!x) { toast('confira data, início e duração'); return; }
    if (novo) store.add(x); else store.update(x);
    fecharSheet();
    grafico.focarDia(diaDe(x));
    toast(novo ? 'registro adicionado' : 'registro atualizado', desfazer);
  };
}

// ---------------------------------------------------------------- ajustes
function sheetAjustes() {
  const linhaDur = (t) => `
    <div class="ajuste-dur"><span><i style="background:${COR[t]}"></i>${LABEL[t]}</span>
      <input type="number" inputmode="numeric" min="0" max="999" data-t="${t}" data-p="min" value="${Math.floor(s[t] / 60)}">
      <b>:</b>
      <input type="number" inputmode="numeric" min="0" max="59" data-t="${t}" data-p="seg" value="${s[t] % 60}">
    </div>`;
  const toggle = (k, txt, sub = '') => `
    <label class="toggle"><span>${txt}${sub ? `<small>${sub}</small>` : ''}</span>
      <input type="checkbox" data-k="${k}" ${s[k] ? 'checked' : ''}><i></i></label>`;
  const sh = abrirSheet(`
    <div class="sheet-topo"><h2>ajustes</h2></div>
    <div class="grupo"><div class="rotulo">durações (min : seg)</div>${TIPOS.map(linhaDur).join('')}</div>
    <div class="grupo">
      ${toggle('crescidoro_ativo', 'crescidoro', 'aumenta o pomodoro a cada pomodoro concluído')}
      <div class="ajuste-num"><span>crescer</span><input type="number" inputmode="numeric" min="1" max="200" data-n="crescidoro_percentual" value="${s.crescidoro_percentual}"><b>%</b></div>
      <div class="ajuste-num"><span>long break a cada</span><input type="number" inputmode="numeric" min="0" max="20" data-n="ciclo_long" value="${s.ciclo_long}"><b>pomos</b></div>
    </div>
    <div class="grupo">
      ${toggle('som', 'som ao terminar')}
      <button class="btn pequeno" id="aj-testar">testar som</button>
      ${toggle('vibrar', 'vibrar ao terminar')}
      ${toggle('manter_tela', 'manter a tela ligada', 'enquanto o timer roda (recomendado: com a tela apagada o navegador pode pausar o som)')}
      ${toggle('notificar', 'notificação', 'avisa se o app estiver em segundo plano')}
    </div>
    <div class="grupo">
      <div class="rotulo">dados (ficam só neste aparelho)</div>
      <div class="acoes-form">
        <label class="btn">importar<input type="file" accept=".json,application/json" id="aj-import" hidden></label>
        <button class="btn" id="aj-export">exportar</button>
      </div>
      <p class="dica">importar aceita o historico_pomodoro.json do app do PC; registros repetidos são ignorados.</p>
    </div>`);
  $$('.ajuste-dur input', sh).forEach((inp) => inp.addEventListener('change', () => {
    const t = inp.dataset.t;
    const min = parseInt($(`input[data-t=${t}][data-p=min]`, sh).value, 10) || 0;
    const seg = Math.min(59, parseInt($(`input[data-t=${t}][data-p=seg]`, sh).value, 10) || 0);
    const tot = Math.min(999 * 60 + 59, min * 60 + seg);
    if (tot <= 0) { inp.value = inp.dataset.p === 'min' ? Math.floor(s[t] / 60) : s[t] % 60; return; }
    s[t] = tot;
    timer.duracaoAlterada(t);
    render();
  }));
  $$('input[data-n]', sh).forEach((inp) => inp.addEventListener('change', () => {
    const k = inp.dataset.n;
    const v = parseInt(inp.value, 10);
    const [lo, hi] = k === 'ciclo_long' ? [0, 20] : [1, 200];
    if (Number.isNaN(v) || v < lo || v > hi) { inp.value = s[k]; return; }
    s[k] = v; store.save(); render();
  }));
  $$('input[data-k]', sh).forEach((inp) => inp.addEventListener('change', async () => {
    const k = inp.dataset.k;
    s[k] = inp.checked;
    if (k === 'notificar' && inp.checked && 'Notification' in window && Notification.permission !== 'granted') {
      const p = await Notification.requestPermission();
      if (p !== 'granted') { s[k] = false; inp.checked = false; toast('permissão de notificação negada'); }
    }
    store.save(); syncWakeLock(); render();
  }));
  $('#aj-testar', sh).onclick = () => { audio.currentTime = 0; audio.play().catch(() => toast('o navegador bloqueou o som')); };
  $('#aj-export', sh).onclick = () => {
    const blob = new Blob([store.exportar()], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `crescidoro-historico-${dayKey(new Date())}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  $('#aj-import', sh).onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const n = store.importar(await file.text());
      toast(n ? `${n} registros importados` : 'nenhum registro novo', n ? desfazer : null);
    } catch (err) {
      toast('arquivo inválido');
    }
    e.target.value = '';
  };
}

function sheetDuracao(t) {
  const sh = abrirSheet(`
    <div class="sheet-topo"><h2 style="color:${COR[t]}">duração · ${LABEL[t]}</h2></div>
    <form class="form">
      <div class="campos2">
        <label>minutos<input type="number" name="min" inputmode="numeric" min="0" max="999" value="${Math.floor(s[t] / 60)}"></label>
        <label>segundos<input type="number" name="seg" inputmode="numeric" min="0" max="59" value="${s[t] % 60}"></label>
      </div>
      <div class="atalhos">${[5, 10, 15, 25, 30, 45, 50, 60].map((m) => `<button type="button" data-m="${m}">${m}</button>`).join('')}</div>
      <div class="acoes-form">
        <button type="button" class="btn" id="d-cancelar">cancelar</button>
        <button type="submit" class="btn primario">salvar</button>
      </div>
    </form>`);
  const f = $('form', sh);
  $$('.atalhos button', f).forEach((b) => (b.onclick = () => { f.min.value = b.dataset.m; f.seg.value = 0; }));
  $('#d-cancelar', sh).onclick = fecharSheet;
  f.onsubmit = (e) => {
    e.preventDefault();
    const tot = (parseInt(f.min.value, 10) || 0) * 60 + Math.min(59, parseInt(f.seg.value, 10) || 0);
    if (tot <= 0) return;
    s[t] = Math.min(999 * 60 + 59, tot);
    timer.duracaoAlterada(t);
    fecharSheet();
    render();
  };
}

// ================================================================ histórico
const grafico = new Grafico($('#grafico'), {
  onTapRegistro: (r) => sheetRegistro(r),
  onTapDia: (k) => sheetDia(k),
});
const heat = new Heatmap($('#mapa'), {
  onTapDia: (k) => { heat.selDia = k; heat.desenhar(); sheetDia(k); },
});
grafico.periodo = s.grafico_periodo;
grafico.tipos = s.grafico_tipos.filter((t) => TIPOS.includes(t));
if (!grafico.tipos.length) grafico.tipos = [...TIPOS];
grafico.modo = vista === 'linha' ? 'linha' : 'barras';
grafico.onScrollInfo = atualizarFaixa;

function atualizarFaixa() {
  if (vista === 'mapa') return;
  const vis = grafico.visiveis();
  if (!vis.length) return;
  const p2 = (n) => String(n).padStart(2, '0');
  const a = vis[0].data, b = vis[vis.length - 1].data;
  $('#faixa').textContent = `${p2(a.getDate())}/${p2(a.getMonth() + 1)} – ${p2(b.getDate())}/${p2(b.getMonth() + 1)}`;
  const tot = porTipo(vis.flatMap((d) => d.regs));
  $('#totais').innerHTML = grafico.tipos.map((t) => `<span style="color:${COR[t]}">${fmtDur(tot[t])}</span>`).join('');
}

function atualizarHistorico() {
  const hoje = hojeDate();
  grafico.setDados(store.registros, hoje);
  heat.setDados(store.registros, hoje);
  atualizarCabecalho();
}
store.on(atualizarHistorico);

function salvarGrafico() {
  s.grafico_modo = vista;
  s.grafico_periodo = grafico.periodo;
  s.grafico_tipos = [...grafico.tipos];
  store.save();
}

function renderToolbar() {
  $$('#vistas button').forEach((b) => b.classList.toggle('on', b.dataset.v === vista));
  $$('#periodos button').forEach((b) => b.classList.toggle('on', b.dataset.v === grafico.periodo));
  $$('#chips button').forEach((b) => b.classList.toggle('on', grafico.tipos.includes(b.dataset.t)));
  const mapa = vista === 'mapa';
  $('#filtros').hidden = mapa;
  $('#faixa-linha').hidden = mapa;
  $('#grafico').hidden = mapa;
  $('#mapa').hidden = !mapa;
  if (mapa) heat.desenhar(); else { grafico.render(); }
}

$$('#vistas button').forEach((b) => (b.onclick = () => {
  vista = b.dataset.v;
  if (vista !== 'mapa') grafico.modo = vista;
  salvarGrafico(); renderToolbar();
}));
$$('#periodos button').forEach((b) => (b.onclick = () => {
  grafico.periodo = b.dataset.v; grafico._ancorarFim = true;
  salvarGrafico(); renderToolbar();
}));
$$('#chips button').forEach((b) => (b.onclick = () => {
  const t = b.dataset.t, tipos = grafico.tipos;
  if (tipos.includes(t)) { if (tipos.length > 1) tipos.splice(tipos.indexOf(t), 1); }
  else { tipos.push(t); tipos.sort((x, y) => TIPOS.indexOf(x) - TIPOS.indexOf(y)); }
  salvarGrafico(); renderToolbar(); grafico.pedirDesenho();
}));
$('#b-novo').onclick = () => sheetEditar(null, dayKey(new Date()));

// ================================================================ timer UI
$$('#abas button').forEach((b) => (b.onclick = () => {
  const t = b.dataset.t;
  if (t !== timer.estado || timer.emAndamento) timer.trocar(t);
  else if (!timer.rodando) sheetDuracao(t);   // tocar na aba ativa parada = editar duração
  render();
}));
$('#b-play').onclick = () => { timer.toggle(); syncWakeLock(); render(); };
$('#b-fim').onclick = () => { timer.finalizar(); syncWakeLock(); render(); };
$('#tempo').onclick = () => { if (!timer.emAndamento) sheetDuracao(timer.estado); };
$('#b-cresc').onclick = () => {
  s.crescidoro_ativo = !s.crescidoro_ativo; store.save(); render();
  toast(s.crescidoro_ativo ? 'crescidoro ligado' : 'crescidoro desligado');
};
$('#b-ajustes').onclick = sheetAjustes;

function atualizarCabecalho() {
  const hk = dayKey(new Date());
  const regs = store.registros.filter((r) => diaDe(r) === hk);
  const foco = regs.filter((r) => r.estado === 'pomodoro').reduce((a, r) => a + r.duracao_s, 0);
  const n = regs.filter((r) => r.estado === 'pomodoro' && r.motivo === 'natural').length;
  const seq = sequenciaAtual(store.registros, hojeDate());
  $('#stats').textContent = [`hoje ${foco ? fmtDur(foco) : '0m'}`, `${n} completo${n === 1 ? '' : 's'}`,
    seq ? `${seq}d seguidos` : ''].filter(Boolean).join(' · ');
}

let ultimoDia = dayKey(new Date());
function render() {
  timer.tick();
  const est = timer.estado;
  document.documentElement.style.setProperty('--modo', COR[est]);
  $$('#abas button').forEach((b) => {
    b.classList.toggle('on', b.dataset.t === est);
    $('small', b).textContent = fmtMMSS(s[b.dataset.t]);
  });
  const rest = timer.restante();
  $('#tempo').textContent = fmtMMSS(Math.ceil(rest - 1e-6));
  $('#progresso').style.width = `${(timer.progresso() * 100).toFixed(2)}%`;
  $('#desde').textContent = timer.inicio ? `desde ${fmtHM(parseDT(timer.inicio))}` : '';
  const n = s.ciclo_long;
  $('#ciclo').innerHTML = n > 0 ? Array.from({ length: n }, (_, i) => `<i class="${i < Math.min(timer.pomodorosNoCiclo, n) ? 'on' : ''}"></i>`).join('') : '';
  $('#b-play').textContent = timer.rodando ? 'pausar' : (timer.emAndamento ? 'continuar' : 'iniciar');
  $('#b-play').classList.toggle('rodando', timer.rodando);
  $('#b-fim').disabled = !timer.emAndamento;
  const prox = Math.round(s.pomodoro * (1 + s.crescidoro_percentual / 100));
  $('#b-cresc').classList.toggle('on', s.crescidoro_ativo);
  $('#b-cresc').innerHTML = `<i></i>crescidoro +${s.crescidoro_percentual}%${s.crescidoro_ativo ? ` <span>→ ${fmtMMSS(prox)}</span>` : ''}`;
  document.title = timer.emAndamento ? `${timer.rodando ? '' : '⏸ '}${fmtMMSS(rest)} · ${LABEL[est]}` : 'crescidoro';
  if (dayKey(new Date()) !== ultimoDia) { ultimoDia = dayKey(new Date()); atualizarHistorico(); }
}

document.addEventListener('visibilitychange', () => { render(); syncWakeLock(); });
setInterval(render, 250);

// ================================================================ início
atualizarHistorico();
renderToolbar();
render();
syncWakeLock();
if (timer.store.timer && timer.inicio && !timer.rodando && timer.emAndamento) toast('sessão pausada restaurada');

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
