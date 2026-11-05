"""Testes de fumaça da interface com driver de vídeo 'dummy'."""
import os
from datetime import date, datetime
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from crescidoro.models import Registro  # noqa: E402
from crescidoro.ui.dialog import parse_mmss, parse_hora, parse_data  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CRESCIDORO_DATA", str(tmp_path))
    from crescidoro.ui.app import App
    a = App()
    hoje = date.today()
    for h, tipo in ((9, "pomodoro"), (10, "pomodoro"), (11, "break")):
        a.hist.add(Registro(tipo, datetime.combine(hoje, datetime.min.time()).replace(hour=h), 1500))
    yield a
    pygame.quit()


def frame(a, n=2, pos=(0, 0)):
    with mock.patch("pygame.mouse.get_pos", return_value=pos):
        for _ in range(n):
            a._tick()
            a._desenhar()


def key(a, k, uni="", mod=0):
    a._evento(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=uni, mod=mod))


def click(a, pos, button=1):
    with mock.patch("pygame.mouse.get_pos", return_value=pos):
        a._evento(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))
    frame(a, 1, pos)


def item_menu(a, texto):
    i = next(i for i, it in enumerate(a.menu.itens) if it and it[0].startswith(texto))
    click(a, a.menu._rects[i].center)


def test_tres_barras_por_dia_subdivididas(app):
    frame(app)
    hits = app.grafico._hits_seg
    assert len(hits) == 3
    pomos = [r for r, g in hits if g.estado == "pomodoro"]
    brk = [r for r, g in hits if g.estado == "break"][0]
    # os dois pomodoros formam UMA barra (mesma coluna, empilhados)
    assert pomos[0].x == pomos[1].x and pomos[0].top >= pomos[1].bottom - 2
    # o break é outra barra, ao lado
    assert brk.x > pomos[0].right


def test_cada_registro_abre_menu_proprio(app):
    frame(app)
    for rect, reg in list(app.grafico._hits_seg):
        click(app, rect.center)
        assert app.menu is not None and app.grafico.sel_registro_id == reg.id
        key(app, pygame.K_ESCAPE)
        assert app.menu is None


def test_editar_pelo_menu(app):
    frame(app)
    rect, reg = app.grafico._hits_seg[0]
    click(app, rect.center)
    item_menu(app, "editar")
    d = app.dialogo
    assert d is not None and app.menu is None
    click(app, d.c_dur.rect.center)
    for ch in "40":
        key(app, ord(ch), ch)
    click(app, d.b_tipos[2][1].rect.center)       # muda para long
    key(app, pygame.K_RETURN)
    novo = app.hist.get(reg.id)
    assert novo.duracao_s == 40 * 60 and novo.estado == "long_break"
    assert app.dialogo is None


def test_remover_e_desfazer(app):
    frame(app)
    rect, reg = app.grafico._hits_seg[0]
    click(app, rect.center)
    item_menu(app, "remover")
    assert app.hist.get(reg.id) is None and app.menu is None
    key(app, pygame.K_z, "z", pygame.KMOD_CTRL)
    assert app.hist.get(reg.id) is not None


def test_duplicar(app):
    frame(app)
    rect, reg = app.grafico._hits_seg[0]
    click(app, rect.center)
    item_menu(app, "duplicar")
    assert len(app.hist.registros) == 4
    assert any(r.inicio == reg.fim and r.motivo == "manual" for r in app.hist.registros)


def test_clique_no_dia_vazio_cria_registro(app):
    frame(app)
    col, dia = app.grafico._hits_dia[0]          # dia mais antigo da janela (vazio)
    click(app, (col.centerx, col.y + 5))
    assert app.menu is not None
    item_menu(app, "novo registro")
    assert app.dialogo is not None
    click(app, app.dialogo.b_salvar.rect.center)
    assert any(r.dia == dia.data and r.motivo == "manual" for r in app.hist.registros)


def test_clique_fora_fecha_menu_e_cancelar_dialogo(app):
    frame(app)
    rect, _ = app.grafico._hits_seg[0]
    click(app, rect.center)
    click(app, (5, 5))
    assert app.menu is None
    app._novo_registro()
    click(app, app.dialogo.b_cancelar.rect.center)
    assert app.dialogo is None and len(app.hist.registros) == 3


def test_campo_duracao_mmss_e_fechar_registra(app):
    frame(app)
    c = app.campos_dur["pomodoro"]
    click(app, c.rect.center)
    for ch in "30:15":
        key(app, ord(ch), ch)
    key(app, pygame.K_RETURN)
    assert app.s.pomodoro == 30 * 60 + 15 and c.texto == "30:15"
    app.timer.start()
    app.timer.decorrido = 120
    app.timer.fechar()
    assert [r.duracao_s for r in app.hist.registros if r.motivo == "fechado"] == [120]


def test_vistas_periodos_e_scroll(app):
    app.hist.add(Registro("pomodoro", datetime(2025, 1, 1, 9), 600))
    app._set_vista("barras")
    app._set_periodo("14d")
    frame(app)
    g = app.grafico
    assert abs(g.offset - g.max_offset) < 1 and len(g.visiveis()) == 14
    g.rolar_dias(-30)
    assert g.offset < g.max_offset
    for v in ("linha", "mapa"):
        app._set_vista(v)
        frame(app)
    cel = app.heat._celulas[0][0]
    click(app, cel.center)
    assert app.vista == "grafico"


def test_parsers():
    assert parse_mmss("25") == 1500 and parse_mmss("1:05:00") == 3900 and parse_mmss("0") is None
    assert parse_hora("930") == (9, 30) and parse_hora("25:00") is None
    assert parse_data("01/02/2026") == date(2026, 2, 1)


def test_loop_principal_encerra(app):
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.run()
