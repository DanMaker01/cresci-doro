// Núcleo do Crescidoro (web): modelos, estatísticas, persistência e timer.
// Mantém o mesmo formato de registro do app desktop (historico_pomodoro.json v2).

export const TIPOS = ['pomodoro', 'break', 'long_break'];
export const LABEL = { pomodoro: 'pomodoro', break: 'break', long_break: 'long' };
export const COR = { pomodoro: '#e25454', break: '#5484e8', long_break: '#4cba70' };
export const MOTIVOS = ['natural', 'pausado', 'fechado', 'manual'];
export const MOTIVO_DESC = {
  natural: 'tempo chegou ao fim',
  pausado: 'encerrado antes do fim',
  fechado: 'app fechado no meio',
  manual: 'adicionado à mão',
  desconhecido: 'registro antigo',
};
export const DIAS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
export const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

// ---------------------------------------------------------------- datas
const p2 = (n) => String(n).padStart(2, '0');
export const fmtDT = (d) =>
  `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;
export const parseDT = (s) => {
  const [a, b = '00:00:00'] = s.split(' ');
  const [y, m, d] = a.split('-').map(Number);
  const [h, mi, se] = b.split(':').map(Number);
  return new Date(y, m - 1, d, h, mi, se || 0);
};
export const dayKey = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
export const keyToDate = (k) => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
export const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
export const diffDays = (a, b) => Math.round((keyToDate(dayKey(a)) - keyToDate(dayKey(b))) / 864e5);
export const hojeDate = () => keyToDate(dayKey(new Date()));
export const fmtDia = (d) => `${DIAS[d.getDay()]} ${p2(d.getDate())}/${p2(d.getMonth() + 1)}/${d.getFullYear()}`;
export const fmtHM = (d) => `${p2(d.getHours())}:${p2(d.getMinutes())}`;

// ---------------------------------------------------------------- formatação
export function fmtMMSS(seg) {
  seg = Math.max(0, Math.floor(seg));
  return `${p2(Math.floor(seg / 60))}:${p2(seg % 60)}`;
}
export function fmtDur(seg) {
  seg = Math.max(0, Math.round(seg));
  if (seg < 60) return `${seg}s`;
  const m = Math.floor(seg / 60);
  if (m < 60) return (seg % 60 === 0 || m >= 10) ? `${m}m` : `${m}m${p2(seg % 60)}`;
  return `${Math.floor(m / 60)}h${p2(m % 60)}`;
}
export const fmtCampo = (seg) => `${Math.floor(seg / 60)}:${p2(seg % 60)}`;

// ---------------------------------------------------------------- registros
export const novoId = () =>
  (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : Math.random().toString(16).slice(2) + Date.now().toString(16)).slice(0, 12);

export const fimDe = (r) => new Date(parseDT(r.inicio).getTime() + r.duracao_s * 1000);
export const diaDe = (r) => r.inicio.slice(0, 10);

/** Normaliza registros do formato novo ou do antigo ({estado, duracao_s, timestamp=fim}). */
export function normalizar(d) {
  const estado = TIPOS.includes(d.estado) ? d.estado : 'pomodoro';
  const dur = Math.max(0, parseInt(d.duracao_s, 10) || 0);
  let inicio = d.inicio;
  if (!inicio && d.timestamp) inicio = fmtDT(new Date(parseDT(d.timestamp).getTime() - dur * 1000));
  if (!inicio || !dur) return null;
  return { id: d.id || novoId(), estado, inicio, duracao_s: dur, motivo: d.motivo || 'desconhecido' };
}

// ---------------------------------------------------------------- estatísticas
export function porTipo(regs) {
  const t = { pomodoro: 0, break: 0, long_break: 0 };
  for (const r of regs) t[r.estado] += r.duracao_s;
  return t;
}

/** Um item por dia em [ini, fim], inclusive os dias sem registro. */
export function serieDiaria(registros, ini, fim) {
  const n = diffDays(fim, ini) + 1;
  const dias = Array.from({ length: n }, (_, i) => {
    const data = addDays(ini, i);
    return { data, key: dayKey(data), regs: [] };
  });
  const idx = new Map(dias.map((d, i) => [d.key, i]));
  for (const r of registros) {
    const i = idx.get(diaDe(r));
    if (i !== undefined) dias[i].regs.push(r);
  }
  for (const d of dias) d.regs.sort((a, b) => a.inicio.localeCompare(b.inicio));
  return dias;
}

export function intervaloTotal(registros, hoje, minimo = 14) {
  let primeiro = addDays(hoje, -(minimo - 1));
  let ultimo = hoje;
  for (const r of registros) {
    const d = keyToDate(diaDe(r));
    if (d < primeiro) primeiro = d;
    if (d > ultimo) ultimo = d;
  }
  return [primeiro, ultimo];
}

/** Matriz [linha dom..sáb][semana] → {data, seg}, estilo GitHub (última coluna = semana atual). */
export function heatmap(registros, hoje, semanas = 53, tipos = ['pomodoro']) {
  const iniSem = addDays(hoje, -hoje.getDay());
  const s0 = addDays(iniSem, -7 * (semanas - 1));
  const tot = new Map();
  for (const r of registros) if (tipos.includes(r.estado)) tot.set(diaDe(r), (tot.get(diaDe(r)) || 0) + r.duracao_s);
  return Array.from({ length: 7 }, (_, wd) => Array.from({ length: semanas }, (_, w) => {
    const data = addDays(s0, 7 * w + wd);
    return { data, seg: tot.get(dayKey(data)) || 0 };
  }));
}

export function niveis(valores) {
  const v = valores.filter((x) => x > 0).sort((a, b) => a - b);
  if (!v.length) return [1, 1, 1];
  const q = (f) => v[Math.min(v.length - 1, Math.floor(f * (v.length - 1)))];
  return [q(0.25), q(0.5), q(0.75)];
}
export const nivel = (seg, lim) => (seg <= 0 ? 0 : 1 + lim.filter((l) => seg > l).length);

export function sequenciaAtual(registros, hoje) {
  const dias = new Set(registros.filter((r) => r.estado === 'pomodoro').map(diaDe));
  let d = dias.has(dayKey(hoje)) ? hoje : addDays(hoje, -1);
  let n = 0;
  while (dias.has(dayKey(d))) { n++; d = addDays(d, -1); }
  return n;
}

export function maiorSequencia(registros) {
  const dias = [...new Set(registros.filter((r) => r.estado === 'pomodoro').map(diaDe))].sort();
  let melhor = 0, atual = 0, ant = null;
  for (const k of dias) {
    const d = keyToDate(k);
    atual = ant && diffDays(d, ant) === 1 ? atual + 1 : 1;
    melhor = Math.max(melhor, atual);
    ant = d;
  }
  return melhor;
}

// ---------------------------------------------------------------- persistência
const CHAVE = 'crescidoro.v2';

export const SETTINGS_PADRAO = {
  pomodoro: 25 * 60, break: 5 * 60, long_break: 30 * 60,
  crescidoro_ativo: false, crescidoro_percentual: 10, ciclo_long: 4,
  grafico_modo: 'barras', grafico_periodo: '14d', grafico_tipos: [...TIPOS],
  som: true, vibrar: true, manter_tela: true, notificar: false,
};

export class Store {
  constructor() {
    this.registros = [];
    this.settings = { ...SETTINGS_PADRAO };
    this.timer = null;
    this.undoStack = [];
    this.ouvintes = new Set();
    this.load();
  }

  load() {
    try {
      const raw = JSON.parse(localStorage.getItem(CHAVE) || 'null');
      if (raw) {
        this.registros = (raw.registros || []).map(normalizar).filter(Boolean);
        this.settings = { ...SETTINGS_PADRAO, ...(raw.settings || {}) };
        this.timer = raw.timer || null;
      }
    } catch (e) {
      console.warn('dados inválidos, começando vazio', e);
    }
    this.ordenar();
  }

  save() {
    try {
      localStorage.setItem(CHAVE, JSON.stringify({
        versao: 2, registros: this.registros, settings: this.settings, timer: this.timer,
      }));
    } catch (e) {
      console.error('falha ao salvar', e);
    }
  }

  ordenar() { this.registros.sort((a, b) => a.inicio.localeCompare(b.inicio)); }
  on(fn) { this.ouvintes.add(fn); }
  emit() { for (const fn of this.ouvintes) fn(); }

  _snap() {
    this.undoStack.push(JSON.stringify(this.registros));
    if (this.undoStack.length > 50) this.undoStack.shift();
  }
  _commit() { this.ordenar(); this.save(); this.emit(); }

  add(r) { this._snap(); this.registros.push(r); this._commit(); return r; }
  update(r) {
    const i = this.registros.findIndex((x) => x.id === r.id);
    if (i < 0) return false;
    this._snap(); this.registros[i] = { ...r }; this._commit(); return true;
  }
  remove(id) {
    const i = this.registros.findIndex((x) => x.id === id);
    if (i < 0) return false;
    this._snap(); this.registros.splice(i, 1); this._commit(); return true;
  }
  undo() {
    if (!this.undoStack.length) return false;
    this.registros = JSON.parse(this.undoStack.pop());
    this._commit();
    return true;
  }
  get(id) { return this.registros.find((r) => r.id === id) || null; }

  /** Junta um JSON exportado (desktop ou web, v1 ou v2). Retorna nº de registros novos. */
  importar(texto) {
    const raw = JSON.parse(texto);
    const itens = Array.isArray(raw) ? raw : (raw.registros || []);
    const ids = new Set(this.registros.map((r) => r.id));
    const assin = new Set(this.registros.map((r) => `${r.estado}|${r.inicio}|${r.duracao_s}`));
    const novos = [];
    for (const d of itens) {
      const r = normalizar(d);
      if (!r) continue;
      const a = `${r.estado}|${r.inicio}|${r.duracao_s}`;
      if (ids.has(r.id) || assin.has(a)) continue;
      ids.add(r.id); assin.add(a); novos.push(r);
    }
    if (novos.length) { this._snap(); this.registros.push(...novos); this._commit(); }
    return novos.length;
  }

  exportar() {
    return JSON.stringify({ versao: 2, registros: this.registros }, null, 1);
  }
}

// ---------------------------------------------------------------- timer
/**
 * O estado do timer é guardado com timestamps, então ele continua certo
 * mesmo se o navegador fechar a aba: ao reabrir, o tempo é recalculado.
 */
export class Timer {
  constructor(store, { onRegistro, onNatural }) {
    this.store = store;
    this.onRegistro = onRegistro;
    this.onNatural = onNatural;
    const t = store.timer || {};
    this.estado = TIPOS.includes(t.estado) ? t.estado : 'pomodoro';
    this.acumulado = t.acumulado || 0;      // segundos contados antes do último start
    this.startedAt = t.startedAt || null;   // epoch ms do último start (null = pausado)
    this.inicio = t.inicio || null;         // 'YYYY-MM-DD HH:MM:SS' do 1º start
    this.pomodorosNoCiclo = t.pomodorosNoCiclo || 0;
    this.crescimentos = t.crescimentos || 0;
  }

  get s() { return this.store.settings; }
  get total() { return this.s[this.estado]; }
  get rodando() { return this.startedAt !== null; }
  decorrido(now = Date.now()) {
    return Math.min(this.total, this.acumulado + (this.rodando ? (now - this.startedAt) / 1000 : 0));
  }
  restante(now) { return Math.max(0, this.total - this.decorrido(now)); }
  progresso(now) { return this.total ? this.decorrido(now) / this.total : 1; }
  get emAndamento() { return this.decorrido() >= 1; }

  persist() {
    this.store.timer = {
      estado: this.estado, acumulado: this.acumulado, startedAt: this.startedAt, inicio: this.inicio,
      pomodorosNoCiclo: this.pomodorosNoCiclo, crescimentos: this.crescimentos,
    };
    this.store.save();
  }

  start() {
    if (this.rodando) return;
    this.startedAt = Date.now();
    if (!this.inicio) this.inicio = fmtDT(new Date());
    this.persist();
  }
  pause() {
    if (!this.rodando) return;
    this.acumulado = this.decorrido();
    this.startedAt = null;
    this.persist();
  }
  toggle() { this.rodando ? this.pause() : this.start(); }

  /** Chamar periodicamente; retorna true se a sessão terminou agora. */
  tick() {
    if (this.rodando && this.acumulado + (Date.now() - this.startedAt) / 1000 >= this.total) {
      this.acumulado = this.total;
      this.startedAt = null;
      this._finalizar('natural');
      return true;
    }
    return false;
  }

  registroParcial(motivo) {
    const d = Math.floor(this.decorrido());
    if (d < 1 || !this.inicio) return null;
    return { id: novoId(), estado: this.estado, inicio: this.inicio, duracao_s: d, motivo };
  }

  finalizar() {
    this.pause();
    if (this.emAndamento) this._finalizar('pausado');
    else this._resetar(this.estado);
  }

  trocar(tipo) {
    this.pause();
    const r = this.registroParcial('pausado');
    if (r) this.onRegistro(r);
    this._resetar(tipo);
  }

  duracaoAlterada(tipo) {
    if (tipo === this.estado && this.acumulado >= this.total) this.acumulado = Math.max(0, this.total - 1);
    this.persist();
  }

  _resetar(tipo) {
    this.estado = tipo;
    this.acumulado = 0;
    this.startedAt = null;
    this.inicio = null;
    this.persist();
  }

  _finalizar(motivo) {
    const r = this.registroParcial(motivo);
    const terminado = this.estado;
    if (r) this.onRegistro(r);
    let proximo = 'pomodoro';
    if (terminado === 'pomodoro') {
      if (motivo === 'natural') {
        this.pomodorosNoCiclo++;
        if (this.s.crescidoro_ativo) {
          const novo = Math.round(this.s.pomodoro * (1 + this.s.crescidoro_percentual / 100));
          this.s.pomodoro = Math.min(novo, 999 * 60 + 59);
          this.crescimentos++;
        }
      }
      const n = this.s.ciclo_long;
      proximo = n > 0 && this.pomodorosNoCiclo >= n ? 'long_break' : 'break';
    } else if (terminado === 'long_break') {
      this.pomodorosNoCiclo = 0;
    }
    this._resetar(proximo);
    if (motivo === 'natural' && this.onNatural) this.onNatural(terminado);
  }
}
