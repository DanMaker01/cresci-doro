"""Diálogo modal para editar ou criar um registro."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pygame

from . import theme as T
from .widgets import Botao, CampoTexto
from ..models import novo_id, Registro, TIPOS, TIPO_LABEL, MOTIVOS, MOTIVO_LABEL, MOTIVO_DESC


# ---- parsing (também usado nos testes) -------------------------------------------
def parse_data(txt: str) -> Optional[date]:
    txt = txt.strip()
    hoje = date.today()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
        try:
            d = datetime.strptime(txt, fmt).date()
            return d.replace(year=hoje.year) if fmt == "%d/%m" else d
        except ValueError:
            continue
    if txt.isdigit() and len(txt) == 8:
        try:
            return datetime.strptime(txt, "%d%m%Y").date()
        except ValueError:
            return None
    return None


def parse_hora(txt: str) -> Optional[tuple[int, int]]:
    txt = txt.strip()
    if ":" in txt:
        h, _, m = txt.partition(":")
    elif txt.isdigit() and len(txt) in (3, 4):
        h, m = txt[:-2], txt[-2:]
    elif txt.isdigit():
        h, m = txt, "0"
    else:
        return None
    if not (h.isdigit() and (m.isdigit() or m == "")):
        return None
    h, m = int(h), int(m or 0)
    return (h, m) if 0 <= h <= 23 and 0 <= m <= 59 else None


def parse_mmss(txt: str) -> Optional[int]:
    """'25' → 1500 ; '25:30' → 1530 ; '1:05:00' → 3900."""
    partes = txt.strip().split(":")
    if not partes or not all(p.isdigit() for p in partes if p) or len(partes) > 3:
        return None
    nums = [int(p or 0) for p in partes]
    if len(nums) == 1:
        seg = nums[0] * 60
    elif len(nums) == 2:
        seg = nums[0] * 60 + min(nums[1], 59)
    else:
        seg = nums[0] * 3600 + nums[1] * 60 + min(nums[2], 59)
    return seg if seg > 0 else None


def fmt_mmss_campo(seg: int) -> str:
    m, s = divmod(int(seg), 60)
    return f"{m}:{s:02d}"


class DialogoRegistro:
    W, H = 380, 300

    def __init__(self, tela_rect: pygame.Rect, reg: Optional[Registro], dia: date,
                 on_salvar: Callable[[Registro, bool], None], on_fechar: Callable[[], None],
                 sugestao_inicio: Optional[datetime] = None):
        self.rect = pygame.Rect(0, 0, self.W, self.H)
        self.rect.center = tela_rect.center
        self.original = reg
        self.on_salvar = on_salvar
        self.on_fechar = on_fechar

        base = reg or Registro("pomodoro", sugestao_inicio or
                               datetime.combine(dia, datetime.min.time()).replace(hour=9),
                               25 * 60, "manual")
        self.f_tipo = base.estado
        self.f_motivo = base.motivo
        self._construir(base)

    def _construir(self, b: Registro) -> None:
        r = self.rect
        x, w = r.x + 22, r.w - 44
        bw = (w - 12) // 3
        self.b_tipos = [(t, Botao((x + i * (bw + 6), r.y + 52, bw, 28), TIPO_LABEL[t].lower(),
                                  lambda t=t: setattr(self, "f_tipo", t), T.TIPO_COR[t], tam=13,
                                  flat=True, ponto=T.TIPO_COR[t]))
                        for i, t in enumerate(TIPOS)]
        self.c_data = CampoTexto((x + 70, r.y + 96, 110, 30), b.inicio.strftime("%d/%m/%Y"),
                                 permitido="0123456789/", max_len=10, tam=14,
                                 on_commit=lambda t: (lambda d: d.strftime("%d/%m/%Y") if d else None)(parse_data(t)))
        self.c_hora = CampoTexto((x + w - 66, r.y + 96, 66, 30), b.inicio.strftime("%H:%M"),
                                 permitido="0123456789:", max_len=5, tam=14,
                                 on_commit=lambda t: (lambda hm: f"{hm[0]:02d}:{hm[1]:02d}" if hm else None)(parse_hora(t)))
        self.c_dur = CampoTexto((x + 70, r.y + 136, 110, 30), fmt_mmss_campo(b.duracao_s),
                                permitido="0123456789:", max_len=8, tam=14,
                                on_commit=lambda t: (lambda s: fmt_mmss_campo(s) if s else None)(parse_mmss(t)))
        self.campos = [self.c_data, self.c_hora, self.c_dur]
        mw = (w - 18) // 4
        self.b_motivos = [(m, Botao((x + i * (mw + 6), r.y + 196, mw, 26), MOTIVO_LABEL[m],
                                    lambda m=m: setattr(self, "f_motivo", m), tam=12, bold=False,
                                    dica=MOTIVO_DESC[m], flat=True))
                          for i, m in enumerate(MOTIVOS)]
        self.b_cancelar = Botao((r.right - 22 - 200, r.bottom - 50, 96, 32), "cancelar", self.on_fechar,
                                tam=12, bold=False, flat=True)
        self.b_salvar = Botao((r.right - 22 - 96, r.bottom - 50, 96, 32), "salvar", self.salvar, T.OK, tam=13)
        self.b_salvar.ativo = True
        self.botoes = [b for _, b in self.b_tipos] + [b for _, b in self.b_motivos] + [self.b_cancelar, self.b_salvar]

    # ---- lógica ------------------------------------------------------------------
    def montar(self) -> Optional[Registro]:
        for c in self.campos:
            if c.foco:
                c.commit()
        d, hm, dur = parse_data(self.c_data.texto), parse_hora(self.c_hora.texto), parse_mmss(self.c_dur.texto)
        self.c_data.erro, self.c_hora.erro, self.c_dur.erro = d is None, hm is None, dur is None
        if d is None or hm is None or dur is None:
            return None
        inicio = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1])
        o = self.original
        if o and o.inicio.replace(second=0) == inicio:
            inicio = o.inicio  # preserva os segundos
        return Registro(self.f_tipo, inicio, dur, self.f_motivo, id=o.id if o else novo_id())

    def salvar(self) -> None:
        reg = self.montar()
        if reg:
            self.on_salvar(reg, self.original is None)
            self.on_fechar()

    # ---- eventos -----------------------------------------------------------------
    def handle(self, ev) -> None:
        """Modal: consome todos os eventos."""
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if not self.rect.collidepoint(ev.pos):
                self.on_fechar()
                return
            alvo = next((c for c in self.campos if c.rect.collidepoint(ev.pos)), None)
            for c in self.campos:
                if c is not alvo and c.foco:
                    c.commit()
            if alvo:
                alvo.focar()
                return
            for b in self.botoes:
                if b.handle(ev):
                    return
        elif ev.type == pygame.KEYDOWN:
            focado = next((c for c in self.campos if c.foco), None)
            if ev.key == pygame.K_TAB:
                i = self.campos.index(focado) if focado else -1
                if focado:
                    focado.commit()
                self.campos[(i + (-1 if ev.mod & pygame.KMOD_SHIFT else 1)) % len(self.campos)].focar()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.salvar()
            elif ev.key == pygame.K_ESCAPE and not focado:
                self.on_fechar()
            elif focado:
                focado.handle_key(ev)

    def update_hover(self, pos) -> None:
        for b in self.botoes:
            b.update_hover(pos)
        for c in self.campos:
            c.update_hover(pos)

    @property
    def cursor(self):
        if any(c.hover for c in self.campos):
            return pygame.SYSTEM_CURSOR_IBEAM
        if any(b.hover for b in self.botoes):
            return pygame.SYSTEM_CURSOR_HAND
        return pygame.SYSTEM_CURSOR_ARROW

    def tooltip(self) -> list:
        b = next((b for b in self.botoes if b.hover and b.dica), None)
        return [(b.dica, T.TEXTO_2, False)] if b else []

    # ---- desenho -----------------------------------------------------------------
    def draw(self, tela) -> None:
        veu = pygame.Surface(tela.get_size(), pygame.SRCALPHA)
        veu.fill((0, 0, 0, 150))
        tela.blit(veu, (0, 0))
        r = self.rect
        pygame.draw.rect(tela, (22, 23, 32), r, border_radius=14)
        pygame.draw.rect(tela, T.BORDA, r, 1, border_radius=14)
        x = r.x + 22
        T.blit_txt(tela, "Editar registro" if self.original else "Novo registro", 16, T.TEXTO,
                   (x, r.y + 18), bold=True)

        for t, b in self.b_tipos:
            b.ativo = t == self.f_tipo
            b.draw(tela)
        T.blit_txt(tela, "data", 12, T.TEXTO_3, (x, self.c_data.rect.centery), "midleft")
        T.blit_txt(tela, "início", 12, T.TEXTO_3, (self.c_hora.rect.x - 10, self.c_hora.rect.centery), "midright")
        T.blit_txt(tela, "duração", 12, T.TEXTO_3, (x, self.c_dur.rect.centery), "midleft")

        d, hm, dur = parse_data(self.c_data.texto), parse_hora(self.c_hora.texto), parse_mmss(self.c_dur.texto)
        if d and hm and dur:
            fim = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1]) + timedelta(seconds=dur)
            T.blit_txt(tela, f"até {fim:%H:%M}", 12, T.TEXTO_3,
                       (self.c_hora.rect.right, self.c_dur.rect.centery), "midright")

        agora = pygame.time.get_ticks()
        for c in self.campos:
            c.cor = T.TIPO_COR[self.f_tipo]
            c.draw(tela, agora)

        T.blit_txt(tela, "fim", 12, T.TEXTO_3, (x, r.y + 178))
        for m, b in self.b_motivos:
            b.ativo = m == self.f_motivo
            b.draw(tela)
        self.b_cancelar.draw(tela)
        self.b_salvar.draw(tela)
