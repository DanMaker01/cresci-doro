"""Heatmap estilo GitHub: último ano de foco (pomodoro), uma célula por dia.

Colunas = semanas (a última é a atual), linhas = domingo → sábado,
meses no topo e legenda "menos ■■■■■ mais" com 5 níveis (quartis).
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pygame

from . import theme as T
from ..models import Registro
from ..stats import (heatmap, niveis, nivel, maior_sequencia, sequencia_atual,
                     fmt_dur, DIAS_SEMANA, DIAS_DOMINGO)

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


class Heatmap:
    SEMANAS = 53
    LARG_ROTULO = 34
    ALT_MESES = 20
    GAP = 3

    def __init__(self, rect, on_click_dia: Callable[[date], None]):
        self.rect = pygame.Rect(rect)
        self.on_click_dia = on_click_dia
        self.matriz: list = []
        self.limiares = [1, 1, 1]
        self.hoje = date.today()
        self.sel_dia: Optional[date] = None
        self.resumo = {}
        self._celulas: list[tuple[pygame.Rect, date, int]] = []
        self._hover: Optional[tuple[date, int]] = None
        self.cores = self._paleta()

    @staticmethod
    def _paleta() -> list:
        vazio = (28, 30, 41)
        base = T.TIPO_COR["pomodoro"]
        return [vazio] + [T.mix(vazio, base, f) for f in (0.40, 0.60, 0.80, 1.0)]

    # ---- dados ----------------------------------------------------------------
    def set_dados(self, registros: list[Registro], hoje: date) -> None:
        self.hoje = hoje
        self.matriz = heatmap(registros, hoje, self.SEMANAS)
        valores = [s for linha in self.matriz for d, s in linha if d <= hoje]
        self.limiares = niveis(valores)
        ativos = [s for s in valores if s]
        self.resumo = {
            "total": sum(valores),
            "dias": len(ativos),
            "media": sum(ativos) / len(ativos) if ativos else 0,
            "melhor": max(((d, s) for linha in self.matriz for d, s in linha), key=lambda x: x[1],
                          default=(None, 0)),
            "seq": sequencia_atual(registros, hoje),
            "maior_seq": maior_sequencia([r for r in registros
                                          if r.dia >= self.matriz[0][0][0]]),
        }

    # ---- geometria ------------------------------------------------------------
    def _geom(self):
        """(x0, y0, célula) com a grade centralizada no retângulo."""
        larg_util = self.rect.w - self.LARG_ROTULO
        cel = max(6, min(18, (larg_util + self.GAP) // self.SEMANAS - self.GAP))
        passo = cel + self.GAP
        larg = self.LARG_ROTULO + self.SEMANAS * passo - self.GAP
        alt = self.ALT_MESES + 7 * passo - self.GAP + 34 + 26  # meses + grade + legenda + resumo
        x0 = self.rect.x + (self.rect.w - larg) // 2 + self.LARG_ROTULO
        y0 = self.rect.y + max(0, (self.rect.h - alt) // 2) + self.ALT_MESES
        return x0, y0, cel

    # ---- eventos ----------------------------------------------------------------
    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            for rect, d, _ in self._celulas:
                if rect.collidepoint(ev.pos):
                    self.on_click_dia(d)
                    return True
        return False

    def update_hover(self, pos) -> None:
        self._hover = None
        for rect, d, s in self._celulas:
            if rect.inflate(self.GAP, self.GAP).collidepoint(pos):
                self._hover = (d, s)
                return

    @property
    def cursor_mao(self) -> bool:
        return self._hover is not None

    def tooltip(self) -> list:
        if not self._hover:
            return []
        d, s = self._hover
        dia = f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m/%Y}"
        if not s:
            return [(f"sem foco · {dia}", T.TEXTO_2, False)]
        return [(f"{fmt_dur(s)} de foco", T.clarear(T.TIPO_COR["pomodoro"], 0.2), True),
                (dia, T.TEXTO_2, False)]

    # ---- desenho -------------------------------------------------------------------
    def draw(self, tela) -> None:
        self._celulas.clear()
        if not self.matriz:
            return
        x0, y0, cel = self._geom()
        passo = cel + self.GAP

        # meses no topo: onde a coluna muda de mês (pela 1ª linha), com espaço mínimo
        ultimo_x = -999
        for w in range(self.SEMANAS):
            d = self.matriz[0][w][0]
            anterior = self.matriz[0][w - 1][0] if w else None
            if (anterior is None and d.day <= 7) or (anterior and anterior.month != d.month):
                x = x0 + w * passo
                if x - ultimo_x >= 3 * passo and w <= self.SEMANAS - 2:
                    nome = MESES[d.month - 1] + (f" {d:%y}" if d.month == 1 else "")
                    T.blit_txt(tela, nome, 11, T.TEXTO_3, (x, y0 - 6), "bottomleft")
                    ultimo_x = x

        # dias da semana
        for wd in range(7):
            T.blit_txt(tela, DIAS_DOMINGO[wd], 10, T.TEXTO_3,
                       (x0 - 8, y0 + wd * passo + cel / 2), "midright")

        # células
        raio = 3 if cel >= 10 else 2
        for wd in range(7):
            for w in range(self.SEMANAS):
                d, s = self.matriz[wd][w]
                if d > self.hoje:
                    continue
                rect = pygame.Rect(x0 + w * passo, y0 + wd * passo, cel, cel)
                cor = self.cores[nivel(s, self.limiares)]
                if self._hover and self._hover[0] == d:
                    cor = T.clarear(cor, 0.2)
                pygame.draw.rect(tela, cor, rect, border_radius=raio)
                if d == self.hoje:
                    pygame.draw.rect(tela, T.DESTAQUE, rect.inflate(2, 2), 1, border_radius=raio + 1)
                elif d == self.sel_dia:
                    pygame.draw.rect(tela, T.TEXTO, rect.inflate(2, 2), 1, border_radius=raio + 1)
                self._celulas.append((rect, d, s))

        # legenda (direita) e resumo (esquerda)
        y_leg = y0 + 7 * passo + 14
        x_dir = x0 + self.SEMANAS * passo - self.GAP
        r = T.blit_txt(tela, "mais", 11, T.TEXTO_3, (x_dir, y_leg + cel / 2), "midright")
        x = r.left - 6 - cel
        for c in reversed(self.cores):
            pygame.draw.rect(tela, c, (x, y_leg, cel, cel), border_radius=raio)
            x -= cel + self.GAP
        T.blit_txt(tela, "menos", 11, T.TEXTO_3, (x + cel, y_leg + cel / 2), "midright")

        rs = self.resumo
        partes = [f"{fmt_dur(rs['total']) if rs['total'] else '0m'} de foco no último ano",
                  f"{rs['dias']} dia{'s' if rs['dias'] != 1 else ''} ativos"]
        if rs["dias"]:
            partes.append(f"média {fmt_dur(rs['media'])}/dia ativo")
            md, ms = rs["melhor"]
            partes.append(f"melhor dia {fmt_dur(ms)} ({md:%d/%m})")
        partes.append(f"maior sequência {rs['maior_seq']}d")
        T.blit_txt(tela, "   ·   ".join(partes), 12, T.TEXTO_2, (x0, y_leg + cel / 2), "midleft")
