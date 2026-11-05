"""Gráfico diário com pomodoro, break e long.

- Barras: em cada dia, uma barra por tipo (lado a lado). Cada barra é
  subdividida pelos registros daquele tipo no dia, em ordem cronológica
  (o primeiro embaixo). Cada segmento é clicável individualmente.
- Linha: uma linha por tipo com o total diário.
- Dias sem registro aparecem zerados.
- Período "14d": janela de 14 dias com scroll horizontal por todo o histórico.
  Período "total": todo o histórico comprimido (scroll se não couber).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Callable, Optional

import pygame

from . import theme as T
from ..models import Registro, TIPOS, TIPO_LABEL, MOTIVO_DESC
from ..stats import Dia, serie_diaria, intervalo_total, fmt_dur, DIAS_SEMANA

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _passo_bonito(maximo: float, alvo: int = 4) -> float:
    """Passo 'redondo' em segundos para o eixo Y."""
    candidatos = [60 * m for m in (1, 2, 5, 10, 15, 20, 30, 60, 90, 120, 180, 240, 360, 480, 720)]
    for c in candidatos:
        if maximo / c <= alvo:
            return c
    return candidatos[-1] * math.ceil(maximo / (candidatos[-1] * alvo))


class Grafico:
    MARG_ESQ = 40
    MARG_DIR = 4
    MARG_TOPO = 18
    MARG_BASE = 36
    ALT_SCROLL = 6
    SLOT_MIN = 9

    def __init__(self, rect,
                 on_click_registro: Callable[[Registro, tuple], None],
                 on_click_dia: Callable[[date, tuple], None]):
        self.rect = pygame.Rect(rect)
        self.on_click_registro = on_click_registro
        self.on_click_dia = on_click_dia

        self.modo = "barras"
        self.periodo = "14d"
        self.tipos: list[str] = list(TIPOS)

        self.dias: list[Dia] = []
        self.hoje = date.today()
        self.offset = 0.0
        self._ancorado_fim = True
        self.ymax_anim = 0.0

        self.sel_registro_id: Optional[str] = None
        self.sel_dia: Optional[date] = None

        self._hits_seg: list[tuple[pygame.Rect, Registro]] = []
        self._hits_dia: list[tuple[pygame.Rect, Dia]] = []
        self._hover_reg: Optional[Registro] = None
        self._hover_dia: Optional[Dia] = None
        self._arrastando = False
        self._arraste_dx = 0

    # ---- geometria ----------------------------------------------------------
    @property
    def plot(self) -> pygame.Rect:
        r = self.rect
        return pygame.Rect(r.x + self.MARG_ESQ, r.y + self.MARG_TOPO,
                           r.w - self.MARG_ESQ - self.MARG_DIR,
                           r.h - self.MARG_TOPO - self.MARG_BASE - self.ALT_SCROLL)

    @property
    def slot(self) -> float:
        n = max(1, len(self.dias))
        if self.periodo == "14d":
            return self.plot.w / 14
        return max(self.SLOT_MIN, self.plot.w / n)

    @property
    def largura_total(self) -> float:
        return len(self.dias) * self.slot

    @property
    def max_offset(self) -> float:
        return max(0.0, self.largura_total - self.plot.w)

    @property
    def track(self) -> pygame.Rect:
        p = self.plot
        return pygame.Rect(p.x, self.rect.bottom - self.ALT_SCROLL, p.w, self.ALT_SCROLL)

    @property
    def thumb(self) -> Optional[pygame.Rect]:
        if self.max_offset <= 0:
            return None
        tr = self.track
        w = max(30, tr.w * self.plot.w / self.largura_total)
        x = tr.x + (tr.w - w) * (self.offset / self.max_offset)
        return pygame.Rect(int(x), tr.y, int(w), tr.h)

    # ---- dados ----------------------------------------------------------------
    def set_dados(self, registros: list[Registro], hoje: date) -> None:
        self.hoje = hoje
        ini, fim = intervalo_total(registros, hoje, 14)
        self.dias = serie_diaria(registros, ini, fim)
        self._clamp(manter_fim=self._ancorado_fim)

    def _clamp(self, manter_fim=False) -> None:
        if manter_fim:
            self.offset = self.max_offset
        self.offset = max(0.0, min(self.offset, self.max_offset))
        self._ancorado_fim = self.offset >= self.max_offset - 1

    def set_periodo(self, periodo: str) -> None:
        self.periodo = periodo
        self._clamp(manter_fim=True)

    def rolar(self, px: float) -> None:
        self.offset += px
        self._clamp()

    def rolar_dias(self, n: int) -> None:
        self.rolar(n * self.slot)

    def ir_para_fim(self) -> None:
        self._clamp(manter_fim=True)

    def ir_para_inicio(self) -> None:
        self.offset = 0
        self._clamp()

    def focar_dia(self, d: date) -> None:
        if not self.dias:
            return
        idx = (d - self.dias[0].data).days
        if not 0 <= idx < len(self.dias):
            return
        x = idx * self.slot
        if x < self.offset or x + self.slot > self.offset + self.plot.w:
            self.offset = x - self.plot.w / 2 + self.slot / 2
            self._clamp()

    def _indices_visiveis(self) -> tuple[int, int]:
        eps = 1e-6
        i0 = max(0, int((self.offset + eps) // self.slot))
        i1 = min(len(self.dias), int(math.ceil((self.offset + self.plot.w - eps) / self.slot)))
        return i0, i1

    def visiveis(self) -> list[Dia]:
        if not self.dias:
            return []
        i0, i1 = self._indices_visiveis()
        return self.dias[i0:i1]

    def faixa_visivel(self) -> str:
        v = self.visiveis()
        if not v:
            return ""
        return f"{v[0].data:%d/%m} – {v[-1].data:%d/%m/%y}"

    # ---- eventos ----------------------------------------------------------------
    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                passo = self.slot if self.periodo == "14d" else max(self.slot, 20)
                self.rolar((-ev.y + ev.x) * passo)
                return True
            return False

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            th = self.thumb
            if ev.button == 1 and th and th.inflate(0, 10).collidepoint(ev.pos):
                self._arrastando = True
                self._arraste_dx = ev.pos[0] - th.x
                return True
            if ev.button == 1 and th and self.track.inflate(0, 10).collidepoint(ev.pos):
                self.rolar(self.plot.w * (1 if ev.pos[0] > th.centerx else -1))
                return True
            if not self.rect.collidepoint(ev.pos):
                return False
            for r, reg in self._hits_seg:
                if r.collidepoint(ev.pos):
                    self.sel_registro_id = reg.id
                    self.sel_dia = reg.dia
                    self.on_click_registro(reg, ev.pos)
                    return True
            for r, dia in self._hits_dia:
                if r.collidepoint(ev.pos):
                    self.sel_registro_id = None
                    self.sel_dia = dia.data
                    self.on_click_dia(dia.data, ev.pos)
                    return True
            return True

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self._arrastando:
            self._arrastando = False
            return True

        if ev.type == pygame.MOUSEMOTION and self._arrastando:
            th, tr = self.thumb, self.track
            if th and tr.w > th.w:
                x = ev.pos[0] - self._arraste_dx - tr.x
                self.offset = x / (tr.w - th.w) * self.max_offset
                self._clamp()
            return True
        return False

    def limpar_selecao(self) -> None:
        self.sel_registro_id = None
        self.sel_dia = None

    def update_hover(self, pos, bloqueado=False) -> None:
        self._hover_reg = None
        self._hover_dia = None
        if bloqueado or self._arrastando or not self.plot.inflate(0, self.MARG_BASE).collidepoint(pos):
            return
        for r, reg in self._hits_seg:
            if r.collidepoint(pos):
                self._hover_reg = reg
                break
        for r, dia in self._hits_dia:
            if r.collidepoint(pos):
                self._hover_dia = dia
                break

    @property
    def cursor_mao(self) -> bool:
        return self._hover_reg is not None or self._hover_dia is not None or self._arrastando

    def tooltip(self) -> list:
        if self._hover_reg:
            r = self._hover_reg
            cor = T.TIPO_COR[r.estado]
            return [
                (f"{TIPO_LABEL[r.estado]}  {fmt_dur(r.duracao_s)}", T.clarear(cor, 0.2), True),
                (f"{r.inicio:%d/%m  %H:%M} – {r.fim:%H:%M}", T.TEXTO, False),
                (f"{r.motivo} · {MOTIVO_DESC.get(r.motivo, '')}", T.TEXTO_3, False),
            ]
        if self._hover_dia:
            d = self._hover_dia
            pt = d.por_tipo()
            linhas = [(f"{DIAS_SEMANA[d.data.weekday()]} {d.data:%d/%m/%Y}", T.TEXTO, True)]
            if not d.registros:
                linhas.append(("sem registros", T.TEXTO_3, False))
            for t in TIPOS:
                if pt[t]:
                    n = sum(1 for r in d.registros if r.estado == t)
                    linhas.append((f"{TIPO_LABEL[t]}  {fmt_dur(pt[t])}  ·  {n}x", T.TIPO_COR[t], False))
            return linhas
        return []

    # ---- desenho -------------------------------------------------------------------
    def draw(self, tela) -> None:
        self._hits_seg.clear()
        self._hits_dia.clear()
        p = self.plot
        slot = self.slot
        visiveis = self.visiveis()

        # escala Y (animada): maior barra individual visível
        alvo = max((max((d.por_tipo()[t] for t in self.tipos), default=0) for d in visiveis), default=0)
        alvo = max(alvo, 30 * 60)
        passo = _passo_bonito(alvo)
        alvo = passo * math.ceil(alvo / passo)
        if self.ymax_anim <= 0:
            self.ymax_anim = alvo
        self.ymax_anim += (alvo - self.ymax_anim) * 0.25
        ymax = self.ymax_anim

        def y_de(seg):
            return p.bottom - seg / ymax * p.h

        v = passo
        while v <= ymax + 1:
            y = int(y_de(v))
            if y >= p.top - 1:
                pygame.draw.line(tela, T.GRID, (p.x, y), (p.right, y), 1)
                T.blit_txt(tela, fmt_dur(v), 11, T.TEXTO_3, (p.x - 8, y), "midright")
            v += passo
        pygame.draw.line(tela, T.BORDA, (p.x, p.bottom), (p.right, p.bottom), 1)

        tela.set_clip(pygame.Rect(p.x, self.rect.y, p.w, self.rect.h))
        i0 = self._indices_visiveis()[0]
        pontos = {t: [] for t in self.tipos}
        meses = []
        for k, dia in enumerate(visiveis):
            x0 = p.x + (i0 + k) * slot - self.offset
            cx = x0 + slot / 2
            col = pygame.Rect(int(x0), p.y, int(math.ceil(slot)), p.h + 30)
            self._hits_dia.append((col.clip(pygame.Rect(p.x, p.y, p.w, p.h + 30)), dia))

            if self._hover_dia is dia or dia.data == self.sel_dia:
                pygame.draw.rect(tela, T.HOVER_COL, (col.x, p.y, col.w, p.h), border_radius=4)
            if dia.data.day == 1 and slot < 30:
                pygame.draw.line(tela, T.GRID, (col.x, p.y), (col.x, p.bottom), 1)
                meses.append((col.x, dia.data))

            if self.modo == "barras":
                self._desenhar_grupo(tela, dia, x0, slot, y_de)
            else:
                pt = dia.por_tipo()
                for t in self.tipos:
                    pontos[t].append((cx, y_de(pt[t]), pt[t]))
            self._rotulo_x(tela, dia, cx, slot, p)

        if self.modo == "linha":
            self._desenhar_linhas(tela, pontos, slot)
        for mx, md in meses:
            nome = MESES[md.month - 1] + (f" {md:%y}" if md.month == 1 else "")
            T.blit_txt(tela, nome, 11, T.TEXTO_3, (mx + 4, p.y - 2))
        tela.set_clip(None)

        th = self.thumb
        if th:
            hover = th.inflate(0, 10).collidepoint(pygame.mouse.get_pos()) or self._arrastando
            pygame.draw.rect(tela, T.GRID, self.track, border_radius=3)
            pygame.draw.rect(tela, (110, 115, 140) if hover else (70, 74, 96), th, border_radius=3)

        if not any(d.registros for d in self.dias):
            T.blit_txt(tela, "sem registros ainda", 14, T.TEXTO_3, p.center, "center")

    def _desenhar_grupo(self, tela, dia: Dia, x0, slot, y_de) -> None:
        n = len(self.tipos)
        grupo = slot * (0.78 if slot >= 20 else 0.9)
        gap = 2 if slot / n >= 8 else (1 if slot / n >= 4 else 0)
        bw = max(1.0, (grupo - gap * (n - 1)) / n)
        gx = x0 + (slot - (bw * n + gap * (n - 1))) / 2
        for j, t in enumerate(self.tipos):
            x = int(round(gx + j * (bw + gap)))
            w = max(1, int(round(gx + j * (bw + gap) + bw)) - x)
            regs = sorted((r for r in dia.registros if r.estado == t), key=lambda r: r.inicio)
            if not regs and slot >= 20:
                base = int(y_de(0))
                pygame.draw.rect(tela, T.mix(T.TIPO_COR[t], T.BG, 0.8), (x, base - 2, w, 2))
            acum = 0
            for reg in regs:
                y_top = int(round(y_de(acum + reg.duracao_s)))
                y_bot = int(round(y_de(acum)))
                acum += reg.duracao_s
                r = pygame.Rect(x, y_top, w, max(1, y_bot - y_top))
                cor = T.TIPO_COR[t]
                interrompido = reg.motivo in ("pausado", "fechado")
                if interrompido:
                    cor = T.mix(cor, T.BG, 0.45)
                if self._hover_reg is not None and self._hover_reg.id == reg.id:
                    cor = T.clarear(cor, 0.28)
                corpo = r.inflate(0, -2) if r.h > 4 else r   # separação entre registros
                pygame.draw.rect(tela, cor, corpo, border_radius=2 if r.h > 5 and w > 5 else 0)
                if reg.id == self.sel_registro_id:
                    pygame.draw.rect(tela, (255, 255, 255), r.inflate(4, 2), 2, border_radius=3)
                hit = r.inflate(max(0, 8 - w), max(0, 6 - r.h))
                self._hits_seg.append((hit, reg))

    def _desenhar_linhas(self, tela, pontos, slot) -> None:
        for t in self.tipos:
            pts = pontos[t]
            if len(pts) > 1:
                pygame.draw.lines(tela, T.escurecer(T.TIPO_COR[t], 0.15), False,
                                  [(x, y) for x, y, _ in pts], 2)
            for x, y, v in pts:
                if v:
                    pygame.draw.circle(tela, T.TIPO_COR[t], (int(x), int(y)), 4 if slot > 12 else 2)

    def _rotulo_x(self, tela, dia: Dia, cx, slot, p) -> None:
        d = dia.data
        hoje = d == self.hoje
        cor = T.DESTAQUE if hoje else (T.TEXTO if d == self.sel_dia else T.TEXTO_3)
        y = p.bottom + 6
        if slot >= 34:
            T.blit_txt(tela, f"{d:%d/%m}", 11, cor, (cx, y), "midtop", bold=hoje)
            T.blit_txt(tela, "hoje" if hoje else DIAS_SEMANA[d.weekday()], 10,
                       cor if hoje else T.TEXTO_3, (cx, y + 14), "midtop")
        elif slot >= 16:
            T.blit_txt(tela, f"{d.day}", 10, cor, (cx, y), "midtop", bold=hoje)
        elif d.weekday() == 0 or hoje:
            s = T.render("hoje" if hoje else f"{d:%d/%m}", 10, cor)
            r = s.get_rect(midtop=(cx, y))
            r.right = min(r.right, p.right)
            tela.blit(s, r)
