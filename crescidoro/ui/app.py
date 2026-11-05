"""Janela principal: timer em cima, histórico (barras / linha / mapa) embaixo."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Optional

import pygame

from . import theme as T
from .chart import Grafico
from .dialog import DialogoRegistro, parse_mmss, fmt_mmss_campo
from .heatmap import Heatmap
from .widgets import Botao, CampoTexto, MenuPopup, desenhar_tooltip
from ..models import Registro, TIPOS, TIPO_LABEL, MOTIVO_DESC
from ..paths import resource_path, data_path
from ..stats import fmt_mmss, fmt_dur, sequencia_atual, DIAS_SEMANA
from ..storage import HistoryStore, SettingsStore, SessionCheckpoint
from ..timer import Timer

W, H = 1040, 760
ARQ_HIST = "historico_pomodoro.json"
ARQ_CONFIG = "config_tempos.json"
ARQ_SESSAO = "sessao_em_andamento.json"
CX = W // 2
Y_HIST = 380          # início da área de histórico


class App:
    def __init__(self):
        pygame.init()
        T.reset_cache()
        self._carregar_icone()
        self.tela = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Crescidoro")
        pygame.key.set_repeat(350, 35)
        self.clock = pygame.time.Clock()
        self.som = self._carregar_som()

        self.cfg_store = SettingsStore(data_path(ARQ_CONFIG))
        self.s = self.cfg_store.settings
        self.hist = HistoryStore(data_path(ARQ_HIST))
        self.checkpoint = SessionCheckpoint(data_path(ARQ_SESSAO))
        self.timer = Timer(self.s, on_registro=self._on_registro, on_natural=self._on_natural)

        self.menu: Optional[MenuPopup] = None
        self.dialogo: Optional[DialogoRegistro] = None
        self.vista = "mapa" if self.s.grafico_modo == "mapa" else "grafico"
        self.status_msg = ""
        self.status_ate = 0
        self._ultimo_checkpoint = 0
        self._hoje = date.today()
        self._titulo = ""
        self._cur = None

        recuperado = self.checkpoint.recover()
        if recuperado:
            self.hist.add(recuperado)
            self.status(f"sessão anterior recuperada: {TIPO_LABEL[recuperado.estado].lower()} "
                        f"de {fmt_dur(recuperado.duracao_s)} (fechado)", 6000)

        self._construir_ui()
        self.hist.on_change = self._on_hist_change
        self._on_hist_change()

    # =====================================================================
    # recursos
    # =====================================================================
    @staticmethod
    def _carregar_icone():
        try:
            p = resource_path("icon.ico")
            if os.path.exists(p):
                pygame.display.set_icon(pygame.image.load(p))
        except Exception:
            pass

    @staticmethod
    def _carregar_som():
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            p = resource_path("sucesso.mp3")
            return pygame.mixer.Sound(p) if os.path.exists(p) else None
        except Exception:
            return None

    # =====================================================================
    # construção da UI
    # =====================================================================
    def _construir_ui(self):
        # ---- abas de modo, cada uma com sua duração editável (MM:SS) -------
        self.abas: dict[str, Botao] = {}
        self.campos_dur: dict[str, CampoTexto] = {}
        larg, gap = 124, 10
        x0 = CX - (3 * larg + 2 * gap) // 2
        for i, t in enumerate(TIPOS):
            x = x0 + i * (larg + gap)
            self.abas[t] = Botao((x, 58, larg, 32), TIPO_LABEL[t].lower(),
                                 lambda t=t: self._trocar_modo(t), T.TIPO_COR[t], tam=13,
                                 dica=f"tecla {i + 1}", flat=True, ponto=T.TIPO_COR[t])
            self.campos_dur[t] = CampoTexto((x + 22, 92, larg - 44, 24), permitido="0123456789:",
                                            max_len=6, tam=13, cor=T.TIPO_COR[t], flat=True,
                                            on_commit=lambda txt, t=t: self._commit_dur(t, txt))

        # ---- controles ------------------------------------------------------
        self.b_play = Botao((CX - 124, 262, 150, 42), "iniciar", self._toggle, tam=15, dica="espaço")
        self.b_fim = Botao((CX + 34, 262, 90, 42), "finalizar", self.timer.finalizar, tam=12,
                           bold=False, flat=True, dica="encerra agora e salva como 'pausado'  (F)")

        # ---- opções: crescidoro + ciclo ----------------------------------------
        y = 326
        self.b_cresc = Botao((CX - 232, y, 112, 26), "crescidoro", self._toggle_cresc, T.CRESCIDORO,
                             tam=12, flat=True, ponto=T.CRESCIDORO,
                             dica="aumenta o pomodoro a cada pomodoro concluído  (C)")
        self.c_pct = CampoTexto((CX - 104, y, 44, 26), str(self.s.crescidoro_percentual), max_len=3,
                                tam=12, cor=T.CRESCIDORO, flat=True, on_commit=self._commit_pct)
        self.c_ciclo = CampoTexto((CX + 140, y, 34, 26), str(self.s.ciclo_long), max_len=2, tam=12,
                                  cor=T.TIPO_COR["long_break"], flat=True, on_commit=self._commit_ciclo)

        # ---- barra de ferramentas do histórico ---------------------------------
        ty = Y_HIST + 6
        x = 24
        self.b_vistas = {}
        for nome, w in (("barras", 62), ("linha", 54), ("mapa", 54)):
            self.b_vistas[nome] = Botao((x, ty, w, 26), nome, lambda n=nome: self._set_vista(n),
                                        tam=12, bold=False, flat=True)
            x += w + 2
        x += 18
        self.b_14d = Botao((x, ty, 44, 26), "14d", lambda: self._set_periodo("14d"), tam=12, bold=False,
                           flat=True, dica="janela de 14 dias (role para o passado)")
        self.b_total = Botao((x + 46, ty, 52, 26), "total", lambda: self._set_periodo("total"), tam=12,
                             bold=False, flat=True, dica="todo o histórico")
        x += 98 + 18
        self.chips: dict[str, Botao] = {}
        for t, w in (("pomodoro", 82), ("break", 64), ("long_break", 58)):
            self.chips[t] = Botao((x, ty, w, 26), TIPO_LABEL[t].lower(), lambda t=t: self._toggle_tipo(t),
                                  T.TIPO_COR[t], tam=12, bold=False, flat=True, ponto=T.TIPO_COR[t])
            x += w + 2
        self.b_novo = Botao((W - 24 - 92, ty, 92, 26), "+ registro", self._novo_registro, tam=12,
                            bold=False, flat=True, dica="adicionar registro manual  (N)")
        self.b_undo = Botao((W - 24 - 92 - 80, ty, 76, 26), "desfazer", self._undo, tam=12, bold=False,
                            flat=True, dica="Ctrl+Z")

        r_area = pygame.Rect(24, Y_HIST + 52, W - 48, H - Y_HIST - 52 - 20)
        self.grafico = Grafico(r_area, on_click_registro=self._menu_registro, on_click_dia=self._menu_dia)
        self.grafico.modo = self.s.grafico_modo if self.s.grafico_modo in ("barras", "linha") else "barras"
        self.grafico.periodo = self.s.grafico_periodo
        self.grafico.tipos = list(self.s.grafico_tipos)
        self.heat = Heatmap(r_area, on_click_dia=self._click_heat)

        self.botoes = [*self.abas.values(), self.b_play, self.b_fim, self.b_cresc,
                       *self.b_vistas.values(), self.b_14d, self.b_total, *self.chips.values(),
                       self.b_novo, self.b_undo]
        self.campos = [*self.campos_dur.values(), self.c_pct, self.c_ciclo]
        self._sync_campos_dur()

    # =====================================================================
    # domínio
    # =====================================================================
    def _on_registro(self, reg: Registro):
        self.checkpoint.clear()
        self.hist.add(reg)
        if reg.motivo != "natural":
            self.status(f"{TIPO_LABEL[reg.estado].lower()} de {fmt_dur(reg.duracao_s)} salvo como '{reg.motivo}'")

    def _on_natural(self, tipo: str):
        if self.som:
            try:
                self.som.play()
            except Exception:
                pass
        if tipo == "pomodoro" and self.s.crescidoro_ativo:
            self.status(f"pomodoro concluído — próximo: {fmt_mmss(self.s.pomodoro)}", 5000)
        else:
            self.status(f"{TIPO_LABEL[tipo].lower()} concluído", 4000)
        self._sync_campos_dur()
        self._salvar_cfg()

    def _on_hist_change(self):
        hoje = date.today()
        self.grafico.set_dados(self.hist.registros, hoje)
        self.heat.set_dados(self.hist.registros, hoje)
        if self.grafico.sel_registro_id and not self.hist.get(self.grafico.sel_registro_id):
            self.grafico.sel_registro_id = None

    # ---- menus e diálogo -----------------------------------------------------
    def _menu_registro(self, reg: Registro, pos):
        cor = T.TIPO_COR[reg.estado]
        titulo = [(f"{TIPO_LABEL[reg.estado].lower()}  ·  {fmt_dur(reg.duracao_s)}", T.clarear(cor, 0.2), True),
                  (f"{reg.inicio:%d/%m  %H:%M} – {reg.fim:%H:%M}", T.TEXTO_2, False),
                  (f"fim {reg.motivo}", T.TEXTO_3, False)]
        itens = [("editar…", lambda: self._abrir_dialogo(reg), None),
                 ("duplicar", lambda: self._duplicar(reg), None),
                 None,
                 ("novo registro neste dia", lambda: self._abrir_dialogo(None, reg.dia), None),
                 None,
                 ("remover", lambda: self._remover(reg), T.PERIGO)]
        self.menu = MenuPopup(pos, itens, titulo)

    def _menu_dia(self, d: date, pos):
        regs = [r for r in self.hist.registros if r.dia == d]
        titulo = [(f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m/%Y}", T.TEXTO, True)]
        tot = {t: sum(r.duracao_s for r in regs if r.estado == t) for t in TIPOS}
        resumo = "  ".join(f"{TIPO_LABEL[t].lower()} {fmt_dur(v)}" for t, v in tot.items() if v)
        titulo.append((resumo or "sem registros", T.TEXTO_3, False))
        self.menu = MenuPopup(pos, [("novo registro…", lambda: self._abrir_dialogo(None, d), None)], titulo)

    def _abrir_dialogo(self, reg: Optional[Registro], dia: Optional[date] = None):
        dia = dia or (reg.dia if reg else date.today())
        sugestao = None
        if reg is None:
            regs = [r for r in self.hist.registros if r.dia == dia]
            if regs:
                sugestao = max(r.fim for r in regs).replace(microsecond=0)
            elif dia == date.today():
                sugestao = (datetime.now() - timedelta(minutes=25)).replace(second=0, microsecond=0)
            self.grafico.sel_dia = dia
        self.dialogo = DialogoRegistro(self.tela.get_rect(), reg, dia, self._salvar_dialogo,
                                       self._fechar_dialogo, sugestao)

    def _fechar_dialogo(self):
        self.dialogo = None
        self.grafico.limpar_selecao()

    def _salvar_dialogo(self, reg: Registro, novo: bool):
        if novo:
            self.hist.add(reg)
            self.status("registro adicionado  ·  ctrl+z desfaz")
        else:
            self.hist.update(reg)
            self.status("registro atualizado  ·  ctrl+z desfaz")
        self.grafico.focar_dia(reg.dia)

    def _duplicar(self, reg: Registro):
        copia = Registro(reg.estado, reg.fim, reg.duracao_s, "manual")
        self.hist.add(copia)
        self.status("registro duplicado  ·  ctrl+z desfaz")

    def _remover(self, reg: Registro):
        self.hist.remove(reg.id)
        self.status("registro removido  ·  ctrl+z desfaz", 5000)

    def _click_heat(self, d: date):
        self._set_vista(self.grafico.modo)
        if self.grafico.periodo != "14d":
            self.grafico.set_periodo("14d")
        self.grafico.focar_dia(d)
        self.grafico.sel_dia = d
        self.grafico.sel_registro_id = None

    def _novo_registro(self):
        self._abrir_dialogo(None, date.today())

    def _undo(self):
        self.status("alteração desfeita" if self.hist.undo() else "nada para desfazer")

    # ---- timer / config ----------------------------------------------------------
    def _toggle(self):
        self.timer.toggle()

    def _trocar_modo(self, t: str):
        if t != self.timer.estado or self.timer.em_andamento:
            self.timer.trocar(t)

    def _toggle_cresc(self):
        self.s.crescidoro_ativo = not self.s.crescidoro_ativo
        self._salvar_cfg()
        self.status("crescidoro ligado" if self.s.crescidoro_ativo else "crescidoro desligado")

    def _commit_dur(self, tipo: str, txt: str) -> Optional[str]:
        seg = parse_mmss(txt)
        if not seg:
            return None
        self.s.set_duracao(tipo, seg)
        self.timer.duracao_alterada(tipo)
        self._salvar_cfg()
        return fmt_mmss_campo(self.s.duracao(tipo))

    def _commit_pct(self, txt: str) -> Optional[str]:
        if not txt.isdigit() or not 1 <= int(txt) <= 200:
            return None
        self.s.crescidoro_percentual = int(txt)
        self._salvar_cfg()
        return str(int(txt))

    def _commit_ciclo(self, txt: str) -> Optional[str]:
        if not txt.isdigit():
            return None
        self.s.ciclo_long = min(int(txt), 20)
        self._salvar_cfg()
        return str(self.s.ciclo_long)

    def _sync_campos_dur(self):
        for t, c in self.campos_dur.items():
            c.set(fmt_mmss_campo(self.s.duracao(t)))

    def _salvar_cfg(self):
        self.s.grafico_modo = "mapa" if self.vista == "mapa" else self.grafico.modo
        self.s.grafico_periodo = self.grafico.periodo
        self.s.grafico_tipos = list(self.grafico.tipos)
        try:
            self.cfg_store.save()
        except OSError as e:
            self.status(f"erro ao salvar config: {e}")

    # ---- histórico ---------------------------------------------------------------
    def _set_vista(self, nome):
        if nome == "mapa":
            self.vista = "mapa"
        else:
            self.vista = "grafico"
            self.grafico.modo = nome
        self._salvar_cfg()

    def _set_periodo(self, p):
        self.grafico.set_periodo(p)
        if self.vista == "mapa":
            self.vista = "grafico"
        self._salvar_cfg()

    def _toggle_tipo(self, t):
        tipos = self.grafico.tipos
        if t in tipos:
            if len(tipos) > 1:
                tipos.remove(t)
        else:
            tipos.append(t)
            tipos.sort(key=TIPOS.index)
        self._salvar_cfg()

    def status(self, msg: str, ms: int = 3500):
        self.status_msg = msg
        self.status_ate = pygame.time.get_ticks() + ms

    # =====================================================================
    # loop
    # =====================================================================
    def run(self):
        rodando = True
        while rodando:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    rodando = False
                else:
                    self._evento(ev)
            self._tick()
            self._desenhar()
            pygame.display.flip()
            self.clock.tick(60)
        self.sair()

    def sair(self):
        for c in self.campos:
            c.commit()
        self.timer.fechar()
        self.checkpoint.clear()
        self._salvar_cfg()
        pygame.quit()

    def _tick(self):
        self.timer.tick()
        agora = pygame.time.get_ticks()
        if self.timer.em_andamento and agora - self._ultimo_checkpoint > 10_000:
            reg = self.timer.registro_parcial("fechado")
            if reg:
                self.checkpoint.write(reg)
            self._ultimo_checkpoint = agora
        if date.today() != self._hoje:
            self._hoje = date.today()
            self._on_hist_change()
        titulo = "Crescidoro"
        if self.timer.em_andamento:
            pausa = "" if self.timer.rodando else "⏸ "
            titulo = f"{pausa}{fmt_mmss(self.timer.restante)} · {TIPO_LABEL[self.timer.estado].lower()} — Crescidoro"
        if titulo != self._titulo:
            pygame.display.set_caption(titulo)
            self._titulo = titulo

    def _evento(self, ev):
        # camadas modais primeiro
        if self.dialogo:
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.dialogo.handle(ev)
            return
        if self.menu:
            res = self.menu.handle(ev)
            if res in ("fechar", "acionado"):
                self.menu = None
                if not self.dialogo:
                    self.grafico.limpar_selecao()
                # clique fora do menu segue para o que estiver embaixo
                # (ex.: clicar direto em outro registro abre o menu dele)
                if not (res == "fechar" and ev.type == pygame.MOUSEBUTTONDOWN):
                    return
            elif res == "consumido":
                return

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            alvo = next((c for c in self.campos if c.rect.collidepoint(ev.pos)), None)
            for c in self.campos:
                if c is not alvo and c.foco:
                    c.commit()
            if alvo:
                alvo.focar()
                return

        if ev.type == pygame.KEYDOWN:
            focado = next((c for c in self.campos if c.foco), None)
            if focado:
                if ev.key == pygame.K_TAB:
                    i = self.campos.index(focado)
                    focado.commit()
                    self.campos[(i + (-1 if ev.mod & pygame.KMOD_SHIFT else 1)) % len(self.campos)].focar()
                else:
                    focado.handle_key(ev)
                return
            self._atalho(ev)
            return

        if self.vista == "grafico" and self.grafico.handle(ev):
            return
        if self.vista == "mapa" and self.heat.handle(ev):
            return
        if ev.type == pygame.MOUSEBUTTONDOWN:
            for b in self.botoes:
                if b.handle(ev):
                    return

    def _atalho(self, ev):
        ctrl = ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        k = ev.key
        if ctrl and k == pygame.K_z:
            self._undo()
        elif k == pygame.K_SPACE:
            self._toggle()
        elif k == pygame.K_f:
            self.timer.finalizar()
        elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
            self._trocar_modo(TIPOS[k - pygame.K_1])
        elif k == pygame.K_LEFT:
            self.grafico.rolar_dias(-7 if ev.mod & pygame.KMOD_SHIFT else -1)
        elif k == pygame.K_RIGHT:
            self.grafico.rolar_dias(7 if ev.mod & pygame.KMOD_SHIFT else 1)
        elif k == pygame.K_HOME:
            self.grafico.ir_para_inicio()
        elif k == pygame.K_END:
            self.grafico.ir_para_fim()
        elif k == pygame.K_n:
            self._novo_registro()
        elif k == pygame.K_c:
            self._toggle_cresc()
        elif k == pygame.K_m:
            self._set_vista("mapa" if self.vista != "mapa" else self.grafico.modo)

    # =====================================================================
    # desenho
    # =====================================================================
    def _desenhar(self):
        tela = self.tela
        estado = self.timer.estado
        cor = T.TIPO_COR[estado]
        tela.fill(T.mix(T.BG, cor, 0.035))

        mouse = pygame.mouse.get_pos()
        bloqueado = self.menu is not None or self.dialogo is not None
        for b in self.botoes:
            b.update_hover(mouse if not bloqueado else (-1, -1))
        for c in self.campos:
            c.update_hover(mouse if not bloqueado else (-1, -1))
        self.grafico.update_hover(mouse, bloqueado or self.vista != "grafico")
        self.heat.update_hover(mouse if not bloqueado and self.vista == "mapa" else (-1, -1))

        self._desenhar_topo(tela)
        self._desenhar_timer(tela)
        self._desenhar_historico(tela)
        self._desenhar_status(tela)

        tip = []
        if not bloqueado:
            tip = (self.grafico.tooltip() if self.vista == "grafico" else self.heat.tooltip())
            if not tip:
                b = next((b for b in self.botoes if b.hover and b.dica), None)
                tip = [(b.dica, T.TEXTO_2, False)] if b else []
        if self.menu:
            self.menu.draw(tela)
        if self.dialogo:
            self.dialogo.update_hover(mouse)
            self.dialogo.draw(tela)
            tip = self.dialogo.tooltip()
        if tip:
            desenhar_tooltip(tela, tip, mouse)
        self._cursor()

    def _cursor(self):
        try:
            if self.dialogo:
                cur = self.dialogo.cursor
            elif self.menu:
                cur = pygame.SYSTEM_CURSOR_HAND if self.menu.cursor_mao else pygame.SYSTEM_CURSOR_ARROW
            elif any(c.hover for c in self.campos):
                cur = pygame.SYSTEM_CURSOR_IBEAM
            elif any(b.hover for b in self.botoes) or \
                    (self.vista == "grafico" and self.grafico.cursor_mao) or \
                    (self.vista == "mapa" and self.heat.cursor_mao):
                cur = pygame.SYSTEM_CURSOR_HAND
            else:
                cur = pygame.SYSTEM_CURSOR_ARROW
            if cur != self._cur:
                pygame.mouse.set_cursor(cur)
                self._cur = cur
        except Exception:
            pass

    def _desenhar_topo(self, tela):
        T.blit_txt(tela, "crescidoro", 15, T.TEXTO_2, (24, 18), bold=True)
        hoje = date.today()
        regs = [r for r in self.hist.registros if r.dia == hoje]
        foco = sum(r.duracao_s for r in regs if r.estado == "pomodoro")
        n = sum(1 for r in regs if r.estado == "pomodoro" and r.motivo == "natural")
        seq = sequencia_atual(self.hist.registros, hoje)
        partes = [f"hoje {fmt_dur(foco) if foco else '0m'} de foco", f"{n} completo{'s' if n != 1 else ''}"]
        if seq:
            partes.append(f"{seq} dia{'s' if seq != 1 else ''} seguidos")
        T.blit_txt(tela, "  ·  ".join(partes), 12, T.TEXTO_3, (W - 24, 26), "midright")

    def _desenhar_timer(self, tela):
        estado = self.timer.estado
        cor = T.TIPO_COR[estado]
        agora = pygame.time.get_ticks()
        for t, b in self.abas.items():
            b.ativo = t == estado
            b.draw(tela)
            c = self.campos_dur[t]
            c.cor_texto = T.TEXTO_2 if t == estado else T.TEXTO_3
            c.draw(tela, agora)

        T.blit_txt(tela, fmt_mmss(self.timer.restante), 96, T.TEXTO, (CX, 186), "center", bold=True)
        bar = pygame.Rect(CX - 150, 240, 300, 4)
        pygame.draw.rect(tela, T.GRID, bar, border_radius=2)
        if self.timer.progresso > 0:
            pr = bar.copy()
            pr.w = max(4, int(bar.w * self.timer.progresso))
            pygame.draw.rect(tela, cor, pr, border_radius=2)
        # ciclo até o long break
        n = self.s.ciclo_long
        if n > 0:
            feitos = min(self.timer.pomodoros_no_ciclo, n)
            x = bar.right + 14
            for i in range(n):
                c = T.TIPO_COR["pomodoro"] if i < feitos else T.GRID
                pygame.draw.circle(tela, c, (x + i * 10, bar.centery), 3)
        if self.timer.inicio:
            T.blit_txt(tela, f"desde {self.timer.inicio:%H:%M}", 11, T.TEXTO_3,
                       (bar.x - 14, bar.centery), "midright")

        self.b_play.texto = "pausar" if self.timer.rodando else ("continuar" if self.timer.em_andamento else "iniciar")
        self.b_play.cor = cor
        self.b_play.ativo = True
        self.b_fim.habilitado = self.timer.em_andamento
        self.b_play.draw(tela)
        self.b_fim.draw(tela)

        # opções
        self.b_cresc.ativo = self.s.crescidoro_ativo
        self.b_cresc.draw(tela)
        cc = T.CRESCIDORO if self.s.crescidoro_ativo else T.TEXTO_3
        self.c_pct.cor_texto = cc
        T.blit_txt(tela, "+", 12, cc, (self.c_pct.rect.x - 2, self.c_pct.rect.centery), "midright")
        self.c_pct.draw(tela, agora)
        T.blit_txt(tela, "%", 12, cc, (self.c_pct.rect.right + 2, self.c_pct.rect.centery), "midleft")
        if self.s.crescidoro_ativo:
            prox = round(self.s.pomodoro * (1 + self.s.crescidoro_percentual / 100))
            T.blit_txt(tela, f"→ {fmt_mmss(prox)}", 12, T.CRESCIDORO,
                       (self.c_pct.rect.right + 22, self.c_pct.rect.centery), "midleft")
        T.blit_txt(tela, "long a cada", 12, T.TEXTO_3, (self.c_ciclo.rect.x - 4, self.c_ciclo.rect.centery), "midright")
        self.c_ciclo.draw(tela, agora)
        T.blit_txt(tela, "pomos", 12, T.TEXTO_3, (self.c_ciclo.rect.right + 4, self.c_ciclo.rect.centery), "midleft")

    def _desenhar_historico(self, tela):
        pygame.draw.line(tela, T.GRID, (24, Y_HIST - 8), (W - 24, Y_HIST - 8))
        for nome, b in self.b_vistas.items():
            b.ativo = (self.vista == "mapa") if nome == "mapa" else (self.vista == "grafico" and self.grafico.modo == nome)
        mapa = self.vista == "mapa"
        self.b_14d.ativo = not mapa and self.grafico.periodo == "14d"
        self.b_total.ativo = not mapa and self.grafico.periodo == "total"
        for t, b in self.chips.items():
            b.ativo = t in self.grafico.tipos
            b.habilitado = not mapa
        self.b_undo.habilitado = self.hist.pode_desfazer
        for b in self.botoes[len(self.abas) + 3:]:
            b.draw(tela)

        y2 = Y_HIST + 42
        if mapa:
            T.blit_txt(tela, "foco (pomodoro) no último ano  ·  clique num dia para abri-lo no gráfico",
                       12, T.TEXTO_3, (24, y2), "midleft")
            self.heat.draw(tela)
            return
        T.blit_txt(tela, self.grafico.faixa_visivel(), 12, T.TEXTO_3, (24, y2), "midleft")
        vis = self.grafico.visiveis()
        x = W - 24
        for t in reversed(self.grafico.tipos):
            tot = sum(d.por_tipo()[t] for d in vis)
            s = T.blit_txt(tela, fmt_dur(tot), 12, T.TIPO_COR[t], (x, y2), "midright")
            x = s.left - 16
        self.grafico.draw(tela)

    def _desenhar_status(self, tela):
        if self.status_msg and pygame.time.get_ticks() < self.status_ate:
            s = T.render(self.status_msg, 12, T.TEXTO)
            rect = s.get_rect(midbottom=(CX, H - 10)).inflate(24, 12)
            pygame.draw.rect(tela, (24, 26, 36), rect, border_radius=8)
            tela.blit(s, s.get_rect(center=rect.center))


def run():
    App().run()
