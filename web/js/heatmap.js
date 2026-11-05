// Heatmap estilo GitHub: último ano de foco, uma célula por dia (dom → sáb).
import {
  DIAS, MESES, heatmap, niveis, nivel, dayKey, fmtDur, maiorSequencia, sequenciaAtual,
} from './core.js';

const CEL = 14, GAP = 3, TOPO = 18, SEMANAS = 53, ROT_W = 30;
const PASSO = CEL + GAP;
const ALT = TOPO + 7 * PASSO;

export const CORES_HEAT = ['#1c1e29', '#6b2d32', '#93393b', '#bc4646', '#e25454'];

export class Heatmap {
  constructor(root, { onTapDia }) {
    this.root = root;
    this.onTapDia = onTapDia;
    root.innerHTML = `
      <div class="heat-grade">
        <canvas class="heat-rot"></canvas>
        <div class="scroller"><canvas class="heat-plot"></canvas></div>
      </div>
      <div class="heat-legenda">
        <span class="heat-resumo"></span>
        <span class="heat-escala">menos ${CORES_HEAT.map((c) => `<i style="background:${c}"></i>`).join('')} mais</span>
      </div>`;
    this.rot = root.querySelector('.heat-rot');
    this.scroller = root.querySelector('.scroller');
    this.plot = root.querySelector('.heat-plot');
    this.resumoEl = root.querySelector('.heat-resumo');
    this.matriz = [];
    this.selDia = null;
    this.plot.addEventListener('click', (e) => {
      const w = Math.floor(e.offsetX / PASSO), wd = Math.floor((e.offsetY - TOPO) / PASSO);
      const c = this.matriz[wd]?.[w];
      if (c && c.data <= this.hoje) this.onTapDia(dayKey(c.data));
    });
  }

  setDados(registros, hoje) {
    this.hoje = hoje;
    this.matriz = heatmap(registros, hoje, SEMANAS);
    const valores = this.matriz.flat().filter((c) => c.data <= hoje).map((c) => c.seg);
    this.lim = niveis(valores);
    const ativos = valores.filter(Boolean);
    const total = ativos.reduce((a, b) => a + b, 0);
    const melhor = this.matriz.flat().reduce((m, c) => (c.seg > m.seg ? c : m), { seg: 0 });
    const ini = dayKey(this.matriz[0][0].data);
    const partes = [`<b>${total ? fmtDur(total) : '0m'}</b> de foco no último ano`, `${ativos.length} dias ativos`];
    if (ativos.length) {
      partes.push(`média ${fmtDur(total / ativos.length)}/dia`);
      partes.push(`melhor ${fmtDur(melhor.seg)} (${melhor.data.getDate()}/${melhor.data.getMonth() + 1})`);
    }
    partes.push(`sequência ${sequenciaAtual(registros, hoje)}d · maior ${maiorSequencia(registros.filter((r) => r.inicio >= ini))}d`);
    this.resumoEl.innerHTML = partes.join(' · ');
    this.desenhar();
  }

  desenhar() {
    const dpr = window.devicePixelRatio || 1;
    const css = getComputedStyle(document.documentElement);
    const t3 = css.getPropertyValue('--texto-3').trim();
    const dest = css.getPropertyValue('--destaque').trim();
    const t1 = css.getPropertyValue('--texto').trim();

    // rótulos dos dias (fixos à esquerda)
    this.rot.style.width = `${ROT_W}px`; this.rot.style.height = `${ALT}px`;
    this.rot.width = ROT_W * dpr; this.rot.height = ALT * dpr;
    const r = this.rot.getContext('2d');
    r.setTransform(dpr, 0, 0, dpr, 0, 0);
    r.font = '10px system-ui, sans-serif'; r.fillStyle = t3; r.textBaseline = 'middle';
    DIAS.forEach((d, i) => r.fillText(d, 0, TOPO + i * PASSO + CEL / 2));

    const W = SEMANAS * PASSO;
    this.plot.style.width = `${W}px`; this.plot.style.height = `${ALT}px`;
    this.plot.width = W * dpr; this.plot.height = ALT * dpr;
    const g = this.plot.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);

    // meses no topo
    g.font = '11px system-ui, sans-serif'; g.fillStyle = t3; g.textBaseline = 'top';
    let ultimo = -99;
    for (let w = 0; w < SEMANAS; w++) {
      const d = this.matriz[0][w].data;
      const ant = w ? this.matriz[0][w - 1].data : null;
      if ((!ant && d.getDate() <= 7) || (ant && ant.getMonth() !== d.getMonth())) {
        if (w - ultimo >= 3 && w <= SEMANAS - 2) {
          g.fillText(MESES[d.getMonth()] + (d.getMonth() === 0 ? ` ${String(d.getFullYear()).slice(2)}` : ''), w * PASSO, 0);
          ultimo = w;
        }
      }
    }

    const hk = dayKey(this.hoje);
    for (let wd = 0; wd < 7; wd++) {
      for (let w = 0; w < SEMANAS; w++) {
        const c = this.matriz[wd][w];
        if (c.data > this.hoje) continue;
        const x = w * PASSO, y = TOPO + wd * PASSO;
        g.fillStyle = CORES_HEAT[nivel(c.seg, this.lim)];
        g.beginPath(); g.roundRect(x, y, CEL, CEL, 3); g.fill();
        const k = dayKey(c.data);
        if (k === hk || k === this.selDia) {
          g.strokeStyle = k === hk ? dest : t1; g.lineWidth = 1.5;
          g.beginPath(); g.roundRect(x - 1, y - 1, CEL + 2, CEL + 2, 4); g.stroke();
        }
      }
    }
    this.scroller.scrollLeft = this.scroller.scrollWidth;
  }
}
