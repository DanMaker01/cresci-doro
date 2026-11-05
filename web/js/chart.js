// Gráfico diário: 3 barras por dia (pomodoro / break / long), cada uma
// subdividida pelos registros do dia. Rolagem horizontal nativa (toque).
import {
  TIPOS, COR, MESES, DIAS, serieDiaria, intervaloTotal, porTipo, fmtDur, dayKey,
} from './core.js';

const ALT = 250;          // altura total (css px)
const TOPO = 14;
const BASE = 34;          // rótulos do eixo X
const EIXO_W = 38;

function passoBonito(max, alvo = 4) {
  const c = [1, 2, 5, 10, 15, 20, 30, 60, 90, 120, 180, 240, 360, 480, 720].map((m) => m * 60);
  for (const x of c) if (max / x <= alvo) return x;
  return c[c.length - 1] * Math.ceil(max / (c[c.length - 1] * alvo));
}

const mix = (hex, alvo, t) => {
  const a = parseInt(hex.slice(1), 16), b = parseInt(alvo.slice(1), 16);
  const ch = (v, s) => (v >> s) & 255;
  const m = (s) => Math.round(ch(a, s) + (ch(b, s) - ch(a, s)) * t);
  return `rgb(${m(16)},${m(8)},${m(0)})`;
};

export class Grafico {
  constructor(root, { onTapRegistro, onTapDia }) {
    this.root = root;
    this.onTapRegistro = onTapRegistro;
    this.onTapDia = onTapDia;
    root.innerHTML = `<canvas class="eixo"></canvas><div class="scroller"><canvas class="plot"></canvas></div>`;
    this.eixo = root.querySelector('.eixo');
    this.scroller = root.querySelector('.scroller');
    this.plot = root.querySelector('.plot');

    this.modo = 'barras';
    this.periodo = '14d';
    this.tipos = [...TIPOS];
    this.dias = [];
    this.hoje = new Date();
    this.selId = null;
    this.selDia = null;
    this.ymax = 0;
    this._ancorarFim = true;
    this._raf = 0;
    this.onScrollInfo = null;

    this.scroller.addEventListener('scroll', () => {
      const s = this.scroller;
      this._ancorarFim = s.scrollLeft >= s.scrollWidth - s.clientWidth - 2;
      this.pedirDesenho();
    }, { passive: true });
    this.plot.addEventListener('click', (e) => this._tap(e));
    new ResizeObserver(() => this.render()).observe(this.scroller);
  }

  setDados(registros, hoje) {
    this.hoje = hoje;
    const [a, b] = intervaloTotal(registros, hoje, 14);
    this.dias = serieDiaria(registros, a, b);
    this.render();
  }

  get slot() {
    const w = this.scroller.clientWidth || 320;
    if (this.periodo === '14d') return w / 14;
    return Math.max(10, w / Math.max(1, this.dias.length));
  }

  /** Recalcula tamanho do canvas (mudou dados, período ou largura). */
  render() {
    const w = Math.max(1, Math.round(this.dias.length * this.slot));
    const dpr = Math.min(window.devicePixelRatio || 1, 16000 / w);
    this.dpr = dpr;
    this.plot.style.width = `${w}px`;
    this.plot.style.height = `${ALT}px`;
    this.plot.width = Math.round(w * dpr);
    this.plot.height = Math.round(ALT * dpr);
    const ed = window.devicePixelRatio || 1;
    this.eixo.style.width = `${EIXO_W}px`;
    this.eixo.style.height = `${ALT}px`;
    this.eixo.width = EIXO_W * ed;
    this.eixo.height = ALT * ed;
    if (this._ancorarFim) this.scroller.scrollLeft = this.scroller.scrollWidth;
    this.pedirDesenho();
  }

  irParaFim() { this._ancorarFim = true; this.scroller.scrollLeft = this.scroller.scrollWidth; this.pedirDesenho(); }

  focarDia(key) {
    const i = this.dias.findIndex((d) => d.key === key);
    if (i < 0) return;
    const x = i * this.slot, s = this.scroller;
    if (x < s.scrollLeft || x + this.slot > s.scrollLeft + s.clientWidth) {
      s.scrollLeft = x - s.clientWidth / 2 + this.slot / 2;
    }
    this.pedirDesenho();
  }

  visiveis() {
    const s = this.scroller, slot = this.slot;
    const i0 = Math.max(0, Math.floor((s.scrollLeft + 0.5) / slot));
    const i1 = Math.min(this.dias.length, Math.ceil((s.scrollLeft + s.clientWidth - 0.5) / slot));
    return this.dias.slice(i0, i1);
  }

  pedirDesenho() {
    if (!this._raf) this._raf = requestAnimationFrame(() => { this._raf = 0; this._desenhar(); });
  }

  // ---------------------------------------------------------------- desenho
  _alvoY() {
    let m = 0;
    for (const d of this.visiveis()) {
      const pt = porTipo(d.regs);
      for (const t of this.tipos) m = Math.max(m, pt[t]);
    }
    m = Math.max(m, 30 * 60);
    const passo = passoBonito(m);
    return [passo * Math.ceil(m / passo), passo];
  }

  _desenhar() {
    const [alvo, passo] = this._alvoY();
    if (!this.ymax) this.ymax = alvo;
    this.ymax += (alvo - this.ymax) * 0.3;
    if (Math.abs(alvo - this.ymax) > alvo * 0.005) this.pedirDesenho();
    else this.ymax = alvo;

    const css = getComputedStyle(document.documentElement);
    const C = {
      grid: css.getPropertyValue('--grid').trim(),
      borda: css.getPropertyValue('--borda').trim(),
      t2: css.getPropertyValue('--texto-2').trim(),
      t3: css.getPropertyValue('--texto-3').trim(),
      t1: css.getPropertyValue('--texto').trim(),
      dest: css.getPropertyValue('--destaque').trim(),
      sel: css.getPropertyValue('--sel').trim(),
      bg: css.getPropertyValue('--bg').trim(),
    };
    const ph = ALT - TOPO - BASE;
    const y = (s) => TOPO + ph - (s / this.ymax) * ph;

    // ---- eixo Y
    const e = this.eixo.getContext('2d');
    const ed = window.devicePixelRatio || 1;
    e.setTransform(ed, 0, 0, ed, 0, 0);
    e.clearRect(0, 0, EIXO_W, ALT);
    e.font = '11px system-ui, sans-serif';
    e.fillStyle = C.t3;
    e.textAlign = 'right';
    e.textBaseline = 'middle';
    for (let v = passo; v <= this.ymax + 1; v += passo) e.fillText(fmtDur(v), EIXO_W - 6, y(v));

    // ---- área
    const g = this.plot.getContext('2d');
    const slot = this.slot;
    const W = this.dias.length * slot;
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    g.clearRect(0, 0, W, ALT);

    g.strokeStyle = C.grid;
    g.lineWidth = 1;
    for (let v = passo; v <= this.ymax + 1; v += passo) {
      g.beginPath(); g.moveTo(0, Math.round(y(v)) + 0.5); g.lineTo(W, Math.round(y(v)) + 0.5); g.stroke();
    }
    g.strokeStyle = C.borda;
    g.beginPath(); g.moveTo(0, TOPO + ph + 0.5); g.lineTo(W, TOPO + ph + 0.5); g.stroke();

    const s = this.scroller;
    const i0 = Math.max(0, Math.floor(s.scrollLeft / slot) - 16);
    const i1 = Math.min(this.dias.length, Math.ceil((s.scrollLeft + s.clientWidth) / slot) + 16);
    const pontos = Object.fromEntries(this.tipos.map((t) => [t, []]));

    for (let i = i0; i < i1; i++) {
      const dia = this.dias[i];
      const x0 = i * slot;
      if (dia.key === this.selDia) {
        g.fillStyle = C.sel;
        g.beginPath(); g.roundRect(x0 + 1, TOPO, slot - 2, ph, 4); g.fill();
      }
      if (dia.data.getDate() === 1 && slot < 30) {
        g.strokeStyle = C.grid;
        g.beginPath(); g.moveTo(Math.round(x0) + 0.5, TOPO); g.lineTo(Math.round(x0) + 0.5, TOPO + ph); g.stroke();
        g.fillStyle = C.t3; g.font = '11px system-ui, sans-serif'; g.textAlign = 'left'; g.textBaseline = 'top';
        g.fillText(MESES[dia.data.getMonth()], x0 + 4, 0);
      }
      if (this.modo === 'barras') this._grupo(g, dia, x0, slot, y, C);
      else {
        const pt = porTipo(dia.regs);
        for (const t of this.tipos) pontos[t].push([x0 + slot / 2, y(pt[t]), pt[t]]);
      }
      this._rotulo(g, dia, x0 + slot / 2, slot, TOPO + ph, C);
    }

    if (this.modo === 'linha') {
      for (const t of this.tipos) {
        const pts = pontos[t];
        g.strokeStyle = COR[t]; g.lineWidth = 2; g.lineJoin = 'round';
        g.beginPath();
        pts.forEach(([px, py], k) => (k ? g.lineTo(px, py) : g.moveTo(px, py)));
        g.stroke();
        g.fillStyle = COR[t];
        for (const [px, py, v] of pts) if (v) { g.beginPath(); g.arc(px, py, slot > 12 ? 3.5 : 2, 0, 7); g.fill(); }
      }
    }
    if (this.onScrollInfo) this.onScrollInfo();
  }

  _geomGrupo(x0, slot) {
    const n = this.tipos.length;
    const grupo = slot * (slot >= 20 ? 0.88 : 0.92);
    const gap = slot / n >= 8 ? 2 : (slot / n >= 4 ? 1 : 0);
    const bw = Math.max(1, (grupo - gap * (n - 1)) / n);
    const gx = x0 + (slot - (bw * n + gap * (n - 1))) / 2;
    return { n, gap, bw, gx };
  }

  _pilha(dia, tipo, y) {
    const regs = dia.regs.filter((r) => r.estado === tipo);
    let acum = 0;
    return regs.map((r) => {
      const top = y(acum + r.duracao_s), bot = y(acum);
      acum += r.duracao_s;
      return { r, top, bot };
    });
  }

  _grupo(g, dia, x0, slot, y, C) {
    const { gap, bw, gx } = this._geomGrupo(x0, slot);
    this.tipos.forEach((t, j) => {
      const x = gx + j * (bw + gap);
      const segs = this._pilha(dia, t, y);
      if (!segs.length && slot >= 20) {
        g.fillStyle = mix(COR[t], C.bg, 0.8);
        g.fillRect(x, y(0) - 2, bw, 2);
      }
      for (const { r, top, bot } of segs) {
        const h = Math.max(1, bot - top);
        const sep = h > 4 ? 1 : 0;
        g.fillStyle = r.motivo === 'pausado' || r.motivo === 'fechado' ? mix(COR[t], C.bg, 0.45) : COR[t];
        g.beginPath();
        g.roundRect(x, top + sep, bw, Math.max(1, h - 2 * sep), h > 5 && bw > 5 ? 2 : 0);
        g.fill();
        if (r.id === this.selId) {
          g.strokeStyle = '#fff'; g.lineWidth = 2;
          g.beginPath(); g.roundRect(x - 2, top - 1, bw + 4, h + 2, 3); g.stroke();
        }
      }
    });
  }

  _rotulo(g, dia, cx, slot, yb, C) {
    const d = dia.data;
    const hoje = dia.key === dayKey(this.hoje);
    const cor = hoje ? C.dest : (dia.key === this.selDia ? C.t1 : C.t3);
    g.textAlign = 'center'; g.textBaseline = 'top';
    if (slot >= 34) {
      g.font = `${hoje ? '600 ' : ''}11px system-ui, sans-serif`; g.fillStyle = cor;
      g.fillText(`${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`, cx, yb + 6);
      g.font = '10px system-ui, sans-serif'; g.fillStyle = hoje ? C.dest : C.t3;
      g.fillText(hoje ? 'hoje' : DIAS[d.getDay()], cx, yb + 20);
    } else if (slot >= 16) {
      g.font = `${hoje ? '600 ' : ''}11px system-ui, sans-serif`; g.fillStyle = cor;
      g.fillText(String(d.getDate()), cx, yb + 6);
      g.font = '9px system-ui, sans-serif'; g.fillStyle = C.t3;
      g.fillText(hoje ? 'hoje' : DIAS[d.getDay()][0], cx, yb + 20);
    } else if (d.getDay() === 1 || hoje) {
      g.font = '10px system-ui, sans-serif'; g.fillStyle = cor;
      const txt = hoje ? 'hoje' : `${d.getDate()}/${d.getMonth() + 1}`;
      g.fillText(txt, Math.min(cx, this.dias.length * slot - g.measureText(txt).width / 2 - 1), yb + 8);
    }
  }

  // ---------------------------------------------------------------- toque
  _tap(e) {
    const slot = this.slot;
    const x = e.offsetX, yy = e.offsetY;
    const i = Math.floor(x / slot);
    const dia = this.dias[i];
    if (!dia) return;
    if (this.modo === 'barras') {
      const ph = ALT - TOPO - BASE;
      const y = (s) => TOPO + ph - (s / this.ymax) * ph;
      const { n, gap, bw, gx } = this._geomGrupo(i * slot, slot);
      if (x >= gx - 8 && x <= gx + n * (bw + gap) + 8) {
        const j = Math.max(0, Math.min(n - 1, Math.floor((x - gx + gap / 2) / (bw + gap))));
        const segs = this._pilha(dia, this.tipos[j], y);
        let melhor = null, dist = 1e9;
        for (const sg of segs) {
          const d = yy < sg.top ? sg.top - yy : (yy > sg.bot ? yy - sg.bot : 0);
          if (d < dist) { dist = d; melhor = sg; }
        }
        if (melhor && dist <= 10) { this.onTapRegistro(melhor.r); return; }
      }
    }
    this.onTapDia(dia.key);
  }
}

export { EIXO_W };
