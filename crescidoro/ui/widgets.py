"""Widgets básicos: botão, campo de texto e tooltip."""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from . import theme as T


class Botao:
    def __init__(self, rect, texto: str, acao: Callable[[], None], cor=T.PANEL_2,
                 tam=13, bold=True, dica: str = "", flat: bool = False, ponto=None):
        self.rect = pygame.Rect(rect)
        self.flat = flat        # sem fundo; só texto (fundo leve no hover/ativo)
        self.ponto = ponto      # cor de um marcador circular à esquerda do texto
        self.texto = texto
        self.acao = acao
        self.cor = cor
        self.tam = tam
        self.bold = bold
        self.dica = dica
        self.ativo = False      # estado "selecionado" (toggle)
        self.habilitado = True
        self.visivel = True
        self.hover = False

    def handle(self, ev) -> bool:
        if not (self.visivel and self.habilitado):
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.acao()
            return True
        return False

    def update_hover(self, pos) -> None:
        self.hover = self.visivel and self.rect.collidepoint(pos)

    def draw(self, tela) -> None:
        if not self.visivel:
            return
        if self.flat:
            self._draw_flat(tela)
            return
        if not self.habilitado:
            fundo, txt = T.PANEL, T.TEXTO_3
        elif self.ativo:
            fundo, txt = self.cor, T.TEXTO
        else:
            fundo = T.mix(T.PANEL_2, self.cor, 0.28) if self.cor != T.PANEL_2 else T.PANEL_2
            txt = T.TEXTO_2
        if self.hover and self.habilitado:
            fundo = T.clarear(fundo, 0.10)
            txt = T.TEXTO
        pygame.draw.rect(tela, fundo, self.rect, border_radius=7)
        if self.ativo:
            pygame.draw.rect(tela, T.clarear(self.cor, 0.35), self.rect, 1, border_radius=7)
        T.blit_txt(tela, self.texto, self.tam, txt, self.rect.center, "center", self.bold)

    def _draw_flat(self, tela) -> None:
        if not self.habilitado:
            txt = T.TEXTO_4
        elif self.ativo:
            txt = T.TEXTO
        else:
            txt = T.TEXTO_2 if self.hover else T.TEXTO_3
        if self.habilitado and (self.ativo or self.hover):
            fundo = T.PANEL_2 if self.ativo else T.HOVER_COL
            pygame.draw.rect(tela, fundo, self.rect, border_radius=6)
        if self.ponto:
            s = T.render(self.texto, self.tam, txt, self.bold)
            total = 12 + s.get_width()
            x = self.rect.centerx - total // 2
            cor = self.ponto if self.ativo else T.mix(self.ponto, T.BG, 0.65)
            pygame.draw.circle(tela, cor, (x + 4, self.rect.centery), 4)
            tela.blit(s, s.get_rect(midleft=(x + 12, self.rect.centery)))
        else:
            T.blit_txt(tela, self.texto, self.tam, txt, self.rect.center, "center", self.bold)


class CampoTexto:
    """Campo de texto de uma linha.

    `permitido` filtra os caracteres digitados; `on_commit(texto)` é chamado
    ao pressionar Enter/Tab ou ao perder o foco e deve retornar o texto
    normalizado (ou None para rejeitar e restaurar o valor anterior).
    """

    def __init__(self, rect, texto="", permitido="0123456789", max_len=4,
                 on_commit: Optional[Callable[[str], Optional[str]]] = None,
                 cor=T.BORDA, tam=15, placeholder="", align="center", flat=False):
        self.rect = pygame.Rect(rect)
        self.flat = flat  # sem caixa até hover/foco
        self.texto = texto
        self._confirmado = texto
        self.permitido = permitido
        self.max_len = max_len
        self.on_commit = on_commit
        self.cor = cor
        self.tam = tam
        self.placeholder = placeholder
        self.align = align
        self.foco = False
        self.erro = False
        self.visivel = True
        self.hover = False
        self._selecionar_tudo = False
        self.cor_texto = T.TEXTO_2

    def set(self, texto: str) -> None:
        if not self.foco:
            self.texto = texto
            self._confirmado = texto
            self.erro = False

    def focar(self) -> None:
        self.foco = True
        self._selecionar_tudo = True

    def commit(self) -> None:
        if not self.foco:
            return
        self.foco = False
        if self.on_commit:
            res = self.on_commit(self.texto)
            if res is None:
                self.texto = self._confirmado
                self.erro = True
                return
            self.texto = res
        self._confirmado = self.texto
        self.erro = False

    def cancelar(self) -> None:
        self.foco = False
        self.texto = self._confirmado

    def handle_key(self, ev) -> bool:
        """Retorna True se consumiu o evento (só quando focado)."""
        if not self.foco:
            return False
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.commit()
        elif ev.key == pygame.K_ESCAPE:
            self.cancelar()
        elif ev.key == pygame.K_BACKSPACE:
            if self._selecionar_tudo:
                self.texto = ""
            else:
                self.texto = self.texto[:-1]
            self._selecionar_tudo = False
        elif ev.unicode and ev.unicode in self.permitido:
            if self._selecionar_tudo:
                self.texto = ""
                self._selecionar_tudo = False
            if len(self.texto) < self.max_len:
                self.texto += ev.unicode
        else:
            return ev.key != pygame.K_TAB  # Tab fica para o gerenciador de foco
        return True

    def update_hover(self, pos) -> None:
        self.hover = self.visivel and self.rect.collidepoint(pos)

    def draw(self, tela, agora_ms: int = 0) -> None:
        if not self.visivel:
            return
        fundo = T.PANEL_2 if not self.foco else T.mix(T.PANEL_2, self.cor, 0.15)
        if self.flat and not (self.foco or self.hover or self.erro):
            fundo = None
        elif self.flat and not self.foco:
            fundo = T.HOVER_COL
        if fundo:
            pygame.draw.rect(tela, fundo, self.rect, border_radius=6)
        caixa = not self.flat or self.foco or self.erro
        if caixa:
            if self.erro:
                borda = T.PERIGO
            elif self.foco:
                borda = T.clarear(self.cor, 0.3)
            elif self.hover:
                borda = T.mix(T.BORDA, self.cor, 0.6)
            else:
                borda = T.mix(T.BORDA, self.cor, 0.35)
            pygame.draw.rect(tela, borda, self.rect, 1 if not self.foco else 2, border_radius=6)

        if self.texto:
            cor = self.cor_texto if self.flat and not self.foco else T.TEXTO
            txt = self.texto
        else:
            cor = T.TEXTO_3
            txt = self.placeholder
        s = T.render(txt, self.tam, cor)
        if self.align == "center":
            r = s.get_rect(center=self.rect.center)
        else:
            r = s.get_rect(midleft=(self.rect.x + 8, self.rect.centery))
        if self.foco and self._selecionar_tudo and self.texto:
            pygame.draw.rect(tela, T.mix(fundo, self.cor, 0.5), r.inflate(4, 2), border_radius=3)
        tela.blit(s, r)
        if self.foco and (agora_ms // 500) % 2 == 0:
            x = r.right + 1 if self.texto else r.left
            pygame.draw.line(tela, T.TEXTO, (x, self.rect.y + 7), (x, self.rect.bottom - 7), 1)


def desenhar_tooltip(tela, linhas: list, pos, cor_borda=T.BORDA) -> None:
    """linhas: lista de (texto, cor, bold)."""
    if not linhas:
        return
    pad = 9
    surfs = [T.render(t, 13, c, b) for t, c, b in linhas]
    w = max(s.get_width() for s in surfs) + pad * 2
    h = sum(s.get_height() for s in surfs) + pad * 2 + 2 * (len(surfs) - 1)
    x, y = pos[0] + 16, pos[1] + 16
    W, H = tela.get_size()
    if x + w > W - 6:
        x = pos[0] - w - 12
    if y + h > H - 6:
        y = pos[1] - h - 12
    rect = pygame.Rect(x, y, w, h)
    sombra = pygame.Surface((w, h), pygame.SRCALPHA)
    sombra.fill((0, 0, 0, 90))
    tela.blit(sombra, rect.move(3, 4))
    pygame.draw.rect(tela, (12, 13, 19), rect, border_radius=8)
    pygame.draw.rect(tela, cor_borda, rect, 1, border_radius=8)
    yy = y + pad
    for s in surfs:
        tela.blit(s, (x + pad, yy))
        yy += s.get_height() + 2


class MenuPopup:
    """Menu de contexto. itens: lista de (texto, acao, cor) ou None (separador)."""

    LARG = 190
    ALT_ITEM = 30

    def __init__(self, pos, itens: list, titulo: list | None = None, limites: pygame.Rect | None = None):
        self.itens = itens
        self.titulo = titulo or []          # linhas (texto, cor, bold)
        self.hover = -1
        alt_tit = (len(self.titulo) * 18 + 12) if self.titulo else 0
        h = alt_tit + sum(self.ALT_ITEM if it else 9 for it in itens) + 8
        x, y = pos[0] + 4, pos[1] + 4
        lim = limites or pygame.display.get_surface().get_rect()
        if x + self.LARG > lim.right - 6:
            x = pos[0] - self.LARG - 4
        if y + h > lim.bottom - 6:
            y = max(lim.top + 6, pos[1] - h - 4)
        self.rect = pygame.Rect(x, y, self.LARG, h)
        self._alt_tit = alt_tit
        self._rects: list = []
        yy = y + alt_tit + 4
        for it in itens:
            if it is None:
                self._rects.append(None)
                yy += 9
            else:
                self._rects.append(pygame.Rect(x + 4, yy, self.LARG - 8, self.ALT_ITEM))
                yy += self.ALT_ITEM

    def handle(self, ev) -> str | None:
        """Retorna 'acionado' (item escolhido), 'fechar' (clique fora/Esc),
        'consumido' ou None."""
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            return "fechar"
        if ev.type == pygame.KEYDOWN:
            validos = [i for i, it in enumerate(self.itens) if it]
            if ev.key in (pygame.K_DOWN, pygame.K_UP) and validos:
                if self.hover not in validos:
                    self.hover = validos[0] if ev.key == pygame.K_DOWN else validos[-1]
                else:
                    k = validos.index(self.hover) + (1 if ev.key == pygame.K_DOWN else -1)
                    self.hover = validos[k % len(validos)]
                return "consumido"
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and 0 <= self.hover < len(self.itens) \
                    and self.itens[self.hover]:
                self.itens[self.hover][1]()
                return "acionado"
            return "consumido"
        if ev.type == pygame.MOUSEMOTION:
            self.hover = next((i for i, r in enumerate(self._rects) if r and r.collidepoint(ev.pos)), -1)
            return "consumido" if self.rect.collidepoint(ev.pos) else None
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(ev.pos):
                return "fechar"
            for it, r in zip(self.itens, self._rects):
                if it and r.collidepoint(ev.pos) and ev.button == 1:
                    it[1]()
                    return "acionado"
            return "consumido"
        if ev.type == pygame.MOUSEWHEEL:
            return "fechar"
        return None

    @property
    def cursor_mao(self) -> bool:
        return self.hover >= 0

    def draw(self, tela) -> None:
        sombra = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 110))
        tela.blit(sombra, self.rect.move(4, 6))
        pygame.draw.rect(tela, (20, 21, 30), self.rect, border_radius=10)
        pygame.draw.rect(tela, T.BORDA, self.rect, 1, border_radius=10)
        y = self.rect.y + 10
        for txt, cor, bold in self.titulo:
            T.blit_txt(tela, txt, 12, cor, (self.rect.x + 14, y), bold=bold)
            y += 18
        if self.titulo:
            ly = self.rect.y + self._alt_tit
            pygame.draw.line(tela, T.BORDA, (self.rect.x + 8, ly), (self.rect.right - 8, ly))
        for i, (it, r) in enumerate(zip(self.itens, self._rects)):
            if it is None:
                pygame.draw.line(tela, T.GRID, (self.rect.x + 10, self._sep_y(i)),
                                 (self.rect.right - 10, self._sep_y(i)))
                continue
            texto, _, cor = it
            if i == self.hover:
                pygame.draw.rect(tela, (40, 43, 60), r, border_radius=6)
            T.blit_txt(tela, texto, 13, cor or T.TEXTO, (r.x + 10, r.centery), "midleft")

    def _sep_y(self, i) -> int:
        anterior = next((r for r in reversed(self._rects[:i]) if r), None)
        return (anterior.bottom if anterior else self.rect.y + self._alt_tit) + 4
