"""Cores, fontes (com cache) e helpers de desenho."""
from __future__ import annotations

import pygame

# ---- paleta ----------------------------------------------------------------
BG = (14, 15, 21)
PANEL = (24, 26, 36)
PANEL_2 = (32, 35, 48)
BORDA = (48, 52, 70)
GRID = (38, 41, 56)
TEXTO = (255, 255, 255)
TEXTO_2 = (200, 200, 200)
TEXTO_3 = (150, 150, 150)
TEXTO_4 = (120, 120, 120)
DESTAQUE = (255, 200, 90)
PERIGO = (220, 70, 70)
OK = (80, 190, 120)
CRESCIDORO = (214, 140, 50)
HOVER_COL = (30, 32, 44)

TIPO_COR = {
    "pomodoro": (226, 84, 84),
    "break": (84, 132, 232),
    "long_break": (76, 186, 112),
}
TIPO_FUNDO = {  # tom do fundo do topo conforme o modo atual
    "pomodoro": (58, 22, 26),
    "break": (22, 30, 62),
    "long_break": (20, 52, 34),
}


def mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def clarear(c, t=0.25):
    return mix(c, (255, 255, 255), t)


def escurecer(c, t=0.35):
    return mix(c, (0, 0, 0), t)


# ---- fontes ------------------------------------------------------------------
_FONTES: dict = {}
_FAMILIA = "segoeui,helveticaneue,dejavusans,arial"


def fonte(tam: int, bold: bool = False) -> pygame.font.Font:
    key = (tam, bold)
    f = _FONTES.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont(_FAMILIA, tam, bold=bold)
        except Exception:
            f = pygame.font.Font(None, tam + 4)
        _FONTES[key] = f
    return f


_TXT_CACHE: dict = {}


def render(txt: str, tam: int, cor, bold: bool = False) -> pygame.Surface:
    key = (txt, tam, cor, bold)
    s = _TXT_CACHE.get(key)
    if s is None:
        if len(_TXT_CACHE) > 3000:
            _TXT_CACHE.clear()
        s = fonte(tam, bold).render(txt, True, cor)
        _TXT_CACHE[key] = s
    return s


def blit_txt(tela, txt, tam, cor, pos, anchor="topleft", bold=False) -> pygame.Rect:
    s = render(txt, tam, cor, bold)
    r = s.get_rect(**{anchor: pos})
    tela.blit(s, r)
    return r


def reset_cache() -> None:
    """Fontes ficam inválidas após pygame.quit(); limpar ao (re)iniciar."""
    _FONTES.clear()
    _TXT_CACHE.clear()


def painel(tela, rect, cor=PANEL, raio=10, borda=BORDA):
    pygame.draw.rect(tela, cor, rect, border_radius=raio)
    if borda:
        pygame.draw.rect(tela, borda, rect, 1, border_radius=raio)
