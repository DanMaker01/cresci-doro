"""Painel lateral: lista os registros de um dia e edita/adiciona/remove registros."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pygame

from . import theme as T
from .widgets import Botao, CampoTexto
from ..models import novo_id, Registro, TIPOS, TIPO_LABEL, MOTIVOS, MOTIVO_LABEL, MOTIVO_DESC
from ..stats import fmt_dur, DIAS_SEMANA
from ..storage import HistoryStore


class PainelRegistros:
    ALT_LINHA = 30

    def __init__(self, rect, store: HistoryStore,
                 on_selecionar: Callable[[Optional[Registro]], None],
                 on_status: Callable[[str], None]):
        self.rect = pygame.Rect(rect)
        self.store = store
        self.on_selecionar = on_selecionar   # avisa o gráfico p/ destacar
        self.on_status = on_status

        self.modo = "vazio"                  # "vazio" | "dia" | "form"
        self.dia: Optional[date] = None
        self.reg: Optional[Registro] = None  # original (None = novo)
        self.scroll = 0
        self._linhas: list[tuple[pygame.Rect, Registro]] = []
        self._hover_linha: Optional[str] = None
        self._confirmar_exclusao = False

        # rascunho do formulário
        self.f_tipo = "pomodoro"
        self.f_motivo = "manual"
        self._construir()

    # ---- construção --------------------------------------------------------
    def _construir(self) -> None:
        r = self.rect
        x = r.x + 14
        largura = r.w - 28
        bw = (largura - 12) // 3
        self.b_tipos = []
        for i, t in enumerate(TIPOS):
            b = Botao((x + i * (bw + 6), r.y + 40, bw, 26), TIPO_LABEL[t],
                      lambda t=t: self._set_tipo(t), T.TIPO_COR[t], tam=12)
            self.b_tipos.append((t, b))

        y = r.y + 76
        self.c_data = CampoTexto((x + 60, y, 108, 28), permitido="0123456789/", max_len=10,
                                 on_commit=self._norm_data, placeholder="dd/mm/aaaa", tam=14)
        self.c_hora = CampoTexto((x + largura - 64, y, 64, 28), permitido="0123456789:", max_len=5,
                                 on_commit=self._norm_hora, placeholder="hh:mm", tam=14)
        y = r.y + 110
        self.c_min = CampoTexto((x + 60, y, 50, 28), max_len=3, on_commit=self._norm_int(999), tam=14)
        self.c_seg = CampoTexto((x + 124, y, 44, 28), max_len=2, on_commit=self._norm_int(59), tam=14)

        mw = (largura - 18) // 4
        self.b_motivos = []
        for i, m in enumerate(MOTIVOS):
            b = Botao((x + i * (mw + 6), r.y + 164, mw, 24), MOTIVO_LABEL[m],
                      lambda m=m: self._set_motivo(m), (120, 110, 170), tam=11, dica=MOTIVO_DESC[m])
            self.b_motivos.append((m, b))

        yb = r.bottom - 40
        larg = [78, 84, 64, largura - 78 - 84 - 64 - 18]
        xs = [x]
        for w in larg[:-1]:
            xs.append(xs[-1] + w + 6)
        self.b_salvar = Botao((xs[0], yb, larg[0], 28), "SALVAR", self.salvar, T.OK, tam=12, dica="Enter")
        self.b_excluir = Botao((xs[1], yb, larg[1], 28), "EXCLUIR", self.excluir, T.PERIGO, tam=11,
                               dica="Delete (clique 2x para confirmar)")
        self.b_duplicar = Botao((xs[2], yb, larg[2], 28), "COPIAR", self.duplicar, (110, 110, 140), tam=11,
                                dica="cria uma cópia logo após este registro")
        self.b_voltar = Botao((xs[3], yb, larg[3], 28), "VOLTAR", self.voltar, T.PANEL_2, tam=11, dica="Esc")
        self.b_novo = Botao((r.right - 14 - 92, r.y + 10, 92, 26), "+ NOVO", self.novo_no_dia,
                            (110, 110, 140), tam=12)

        self.campos = [self.c_data, self.c_hora, self.c_min, self.c_seg]

    # ---- normalizadores -------------------------------------------------------
    @staticmethod
    def _norm_int(maximo):
        def f(txt):
            if not txt.isdigit():
                return "0"
            return str(min(int(txt), maximo))
        return f

    @staticmethod
    def _parse_data(txt: str) -> Optional[date]:
        txt = txt.strip()
        hoje = date.today()
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
            try:
                d = datetime.strptime(txt, fmt).date()
                if fmt == "%d/%m":
                    d = d.replace(year=hoje.year)
                return d
            except ValueError:
                continue
        if txt.isdigit() and len(txt) == 8:
            try:
                return datetime.strptime(txt, "%d%m%Y").date()
            except ValueError:
                return None
        return None

    def _norm_data(self, txt):
        d = self._parse_data(txt)
        return d.strftime("%d/%m/%Y") if d else None

    @staticmethod
    def _parse_hora(txt: str):
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
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
        return None

    def _norm_hora(self, txt):
        hm = self._parse_hora(txt)
        return f"{hm[0]:02d}:{hm[1]:02d}" if hm else None

    # ---- API ------------------------------------------------------------------
    def mostrar_dia(self, d: Optional[date]) -> None:
        self._cancelar_campos()
        self.dia = d
        self.reg = None
        self.modo = "dia" if d else "vazio"
        self.scroll = 0
        self._confirmar_exclusao = False

    def editar(self, reg: Optional[Registro]) -> None:
        if reg is None:
            self.mostrar_dia(self.dia)
            return
        self._cancelar_campos()
        self.reg = reg
        self.dia = reg.dia
        self.modo = "form"
        self._confirmar_exclusao = False
        self._carregar(reg)

    def novo(self, d: date, hora: Optional[datetime] = None) -> None:
        self._cancelar_campos()
        self.reg = None
        self.dia = d
        self.modo = "form"
        self._confirmar_exclusao = False
        if hora is None:
            # sugere logo após o último registro do dia, ou 09:00
            regs = [r for r in self.store.registros if r.dia == d]
            hora = max((r.fim for r in regs), default=datetime.combine(d, datetime.min.time()).replace(hour=9))
            if d == date.today() and not regs:
                hora = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=25)
        rascunho = Registro("pomodoro", hora.replace(microsecond=0), 25 * 60, "manual")
        self._carregar(rascunho)

    def novo_no_dia(self) -> None:
        self.novo(self.dia or date.today())

    def _carregar(self, reg: Registro) -> None:
        self.f_tipo = reg.estado
        self.f_motivo = reg.motivo  # 'desconhecido' (legado) é preservado
        self.c_data.set(reg.inicio.strftime("%d/%m/%Y"))
        self.c_hora.set(reg.inicio.strftime("%H:%M"))
        m, s = divmod(reg.duracao_s, 60)
        self.c_min.set(str(m))
        self.c_seg.set(str(s))
        for c in self.campos:
            c.erro = False

    def _set_tipo(self, t):
        self.f_tipo = t

    def _set_motivo(self, m):
        self.f_motivo = m

    def _cancelar_campos(self):
        for c in self.campos:
            if c.foco:
                c.commit()

    def _montar(self) -> Optional[Registro]:
        for c in self.campos:
            if c.foco:
                c.commit()
        d = self._parse_data(self.c_data.texto)
        hm = self._parse_hora(self.c_hora.texto)
        self.c_data.erro = d is None
        self.c_hora.erro = hm is None
        try:
            dur = int(self.c_min.texto or 0) * 60 + int(self.c_seg.texto or 0)
        except ValueError:
            dur = 0
        self.c_min.erro = self.c_seg.erro = dur <= 0
        if d is None or hm is None or dur <= 0:
            self.on_status("Corrija os campos em vermelho")
            return None
        inicio = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1])
        if self.reg and self.reg.inicio.strftime("%Y%m%d%H%M") == inicio.strftime("%Y%m%d%H%M"):
            inicio = self.reg.inicio  # preserva os segundos originais
        return Registro(self.f_tipo, inicio, dur, self.f_motivo,
                        id=self.reg.id if self.reg else novo_id())

    def salvar(self) -> None:
        novo = self._montar()
        if not novo:
            return
        if self.reg:
            self.reg = novo
            self.store.update(novo)
            self.on_status("Registro atualizado  (Ctrl+Z desfaz)")
        else:
            self.store.add(novo)
            self.on_status("Registro adicionado  (Ctrl+Z desfaz)")
        self.reg = novo
        self.dia = novo.dia
        self._carregar(novo)
        self.on_selecionar(novo)

    def excluir(self) -> None:
        if not self.reg:
            self.voltar()
            return
        if not self._confirmar_exclusao:
            self._confirmar_exclusao = True
            return
        alvo = self.reg
        self.reg = None
        self.store.remove(alvo.id)
        self.on_status("Registro excluído  (Ctrl+Z desfaz)")
        d = alvo.dia
        self.on_selecionar(None)
        self.mostrar_dia(d)

    def duplicar(self) -> None:
        if not self.reg:
            return
        copia = Registro(self.reg.estado, self.reg.fim, self.reg.duracao_s, "manual")
        self.store.add(copia)
        self.on_status("Registro copiado  (Ctrl+Z desfaz)")
        self.editar(copia)
        self.on_selecionar(copia)

    def voltar(self) -> None:
        self.on_selecionar(None)
        self.mostrar_dia(self.dia)

    def refresh(self) -> None:
        """Chamado quando o histórico muda por fora (undo, timer)."""
        if self.modo == "form" and self.reg:
            atual = self.store.get(self.reg.id)
            if atual is None:
                self.mostrar_dia(self.dia)
            elif not any(c.foco for c in self.campos):
                self.reg = atual
                self._carregar(atual)

    @property
    def editando_texto(self) -> bool:
        return any(c.foco for c in self.campos)

    # ---- eventos --------------------------------------------------------------
    def _botoes_ativos(self):
        if self.modo == "form":
            bs = [b for _, b in self.b_tipos] + [b for _, b in self.b_motivos]
            bs += [self.b_salvar, self.b_excluir, self.b_voltar]
            if self.reg:
                bs.append(self.b_duplicar)
            return bs
        if self.modo == "dia":
            return [self.b_novo]
        return []

    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            dentro = self.rect.collidepoint(ev.pos)
            if self.modo == "form":
                for c in self.campos:
                    if c.rect.collidepoint(ev.pos):
                        for o in self.campos:
                            if o is not c and o.foco:
                                o.commit()
                        c.focar()
                        return True
                    elif c.foco:
                        c.commit()
            if not dentro:
                return False
            if not (self.b_excluir.rect.collidepoint(ev.pos)):
                self._confirmar_exclusao = False
            for b in self._botoes_ativos():
                if b.handle(ev):
                    return True
            if self.modo == "dia":
                for r, reg in self._linhas:
                    if r.collidepoint(ev.pos):
                        self.editar(reg)
                        self.on_selecionar(reg)
                        return True
            return True

        if ev.type == pygame.MOUSEWHEEL and self.modo == "dia" \
                and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll = max(0, self.scroll - ev.y)
            return True

        if ev.type == pygame.KEYDOWN and self.modo == "form":
            focado = next((c for c in self.campos if c.foco), None)
            if ev.key == pygame.K_TAB:
                idx = self.campos.index(focado) if focado else -1
                if focado:
                    focado.commit()
                passo = -1 if ev.mod & pygame.KMOD_SHIFT else 1
                self.campos[(idx + passo) % len(self.campos)].focar()
                return True
            if focado:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    focado.commit()
                    self.salvar()
                    return True
                return focado.handle_key(ev)
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.salvar()
                return True
            if ev.key == pygame.K_DELETE and self.reg:
                self.excluir()
                return True
            if ev.key == pygame.K_ESCAPE:
                self.voltar()
                return True
        return False

    def update_hover(self, pos) -> None:
        for b in self._botoes_ativos():
            b.update_hover(pos)
        for c in self.campos:
            c.update_hover(pos)
        self._hover_linha = None
        for r, reg in self._linhas:
            if r.collidepoint(pos):
                self._hover_linha = reg.id

    @property
    def cursor_mao(self) -> bool:
        return self._hover_linha is not None or any(b.hover for b in self._botoes_ativos())

    @property
    def cursor_texto(self) -> bool:
        return self.modo == "form" and any(c.hover for c in self.campos)

    # ---- desenho ---------------------------------------------------------------
    def draw(self, tela) -> None:
        T.painel(tela, self.rect)
        r = self.rect
        self._linhas.clear()
        if self.modo == "vazio":
            T.blit_txt(tela, "REGISTROS", 13, T.TEXTO_2, (r.x + 14, r.y + 14), bold=True)
            dicas = ["Clique numa barra para selecionar",
                     "um registro, ou num dia para ver",
                     "todos os registros dele.",
                     "",
                     "Duplo clique num dia: novo registro.",
                     "Ctrl+Z desfaz a última alteração."]
            for i, l in enumerate(dicas):
                T.blit_txt(tela, l, 13, T.TEXTO_3, (r.x + 14, r.y + 48 + i * 20))
            return
        if self.modo == "dia":
            self._draw_dia(tela)
        else:
            self._draw_form(tela)

    def _draw_dia(self, tela) -> None:
        r = self.rect
        d = self.dia
        T.blit_txt(tela, f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m/%Y}", 15, T.TEXTO, (r.x + 14, r.y + 12), bold=True)
        regs = sorted((x for x in self.store.registros if x.dia == d), key=lambda x: x.inicio)
        tot = {t: sum(x.duracao_s for x in regs if x.estado == t) for t in TIPOS}
        xx = r.x + 14
        for t in TIPOS:
            if tot[t]:
                s = T.blit_txt(tela, f"{TIPO_LABEL[t]} {fmt_dur(tot[t])}", 11, T.TIPO_COR[t], (xx, r.y + 34))
                xx = s.right + 10
        self.b_novo.draw(tela)

        y0 = r.y + 56
        if not regs:
            T.blit_txt(tela, "Nenhum registro neste dia.", 13, T.TEXTO_3, (r.x + 14, y0 + 6))
            T.blit_txt(tela, "Use + NOVO para adicionar.", 13, T.TEXTO_3, (r.x + 14, y0 + 26))
            return
        cabem = max(1, (r.bottom - 10 - y0) // self.ALT_LINHA)
        self.scroll = min(self.scroll, max(0, len(regs) - cabem))
        for i, reg in enumerate(regs[self.scroll:self.scroll + cabem]):
            lr = pygame.Rect(r.x + 8, y0 + i * self.ALT_LINHA, r.w - 16, self.ALT_LINHA - 3)
            hov = self._hover_linha == reg.id
            pygame.draw.rect(tela, T.PANEL_2 if not hov else (46, 50, 68), lr, border_radius=6)
            cor = T.TIPO_COR[reg.estado]
            pygame.draw.rect(tela, cor, (lr.x, lr.y, 4, lr.h), border_radius=2)
            T.blit_txt(tela, f"{reg.inicio:%H:%M}–{reg.fim:%H:%M}", 12, T.TEXTO, (lr.x + 12, lr.centery), "midleft")
            T.blit_txt(tela, TIPO_LABEL[reg.estado], 11, cor, (lr.x + 108, lr.centery), "midleft", bold=True)
            T.blit_txt(tela, fmt_dur(reg.duracao_s), 12, T.TEXTO, (lr.x + 200, lr.centery), "midleft")
            T.blit_txt(tela, MOTIVO_LABEL.get(reg.motivo, reg.motivo), 11, T.TEXTO_3,
                       (lr.right - 8, lr.centery), "midright")
            self._linhas.append((lr, reg))
        if len(regs) > cabem:
            T.blit_txt(tela, f"{self.scroll + 1}–{min(len(regs), self.scroll + cabem)} de {len(regs)}  (role)",
                       10, T.TEXTO_3, (r.right - 12, r.bottom - 4), "bottomright")

    def _draw_form(self, tela) -> None:
        r = self.rect
        x = r.x + 14
        titulo = "EDITAR REGISTRO" if self.reg else "NOVO REGISTRO"
        T.blit_txt(tela, titulo, 13, T.TEXTO_2, (x, r.y + 14), bold=True)
        if self.reg:
            T.blit_txt(tela, f"id {self.reg.id[:6]}", 10, T.TEXTO_3, (r.right - 14, r.y + 16), "topright")

        for t, b in self.b_tipos:
            b.ativo = t == self.f_tipo
            b.draw(tela)

        T.blit_txt(tela, "Data", 12, T.TEXTO_2, (x, self.c_data.rect.centery), "midleft")
        T.blit_txt(tela, "Início", 12, T.TEXTO_2, (self.c_hora.rect.x - 8, self.c_hora.rect.centery), "midright")
        T.blit_txt(tela, "Duração", 12, T.TEXTO_2, (x, self.c_min.rect.centery), "midleft")
        T.blit_txt(tela, ":", 15, T.TEXTO_2, ((self.c_min.rect.right + self.c_seg.rect.x) // 2,
                                             self.c_min.rect.centery), "center")

        d = self._parse_data(self.c_data.texto)
        hm = self._parse_hora(self.c_hora.texto)
        try:
            dur = int(self.c_min.texto or 0) * 60 + int(self.c_seg.texto or 0)
        except ValueError:
            dur = 0
        if d and hm and dur > 0:
            fim = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1]) + timedelta(seconds=dur)
            T.blit_txt(tela, f"termina {fim:%H:%M}", 12, T.TEXTO_3,
                       (r.right - 14, self.c_min.rect.centery), "midright")

        agora = pygame.time.get_ticks()
        for c in self.campos:
            c.cor = T.TIPO_COR[self.f_tipo]
            c.draw(tela, agora)

        T.blit_txt(tela, "Motivo do fim", 12, T.TEXTO_2, (x, r.y + 146))
        for m, b in self.b_motivos:
            b.ativo = m == self.f_motivo
            b.draw(tela)
        desc = MOTIVO_DESC.get(self.f_motivo, "")
        if self.f_motivo == "desconhecido":
            desc = "registro antigo, sem motivo — escolha um se quiser"
        T.blit_txt(tela, desc, 11, T.TEXTO_3, (x, r.y + 194))

        self.b_excluir.texto = "CONFIRMA?" if self._confirmar_exclusao else ("EXCLUIR" if self.reg else "DESCARTAR")
        self.b_excluir.ativo = self._confirmar_exclusao
        for b in (self.b_salvar, self.b_excluir, self.b_voltar):
            b.draw(tela)
        if self.reg:
            self.b_duplicar.draw(tela)
