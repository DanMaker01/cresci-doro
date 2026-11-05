"""Testes do núcleo (sem interface)."""
import json
from datetime import date, datetime, timedelta

from crescidoro.models import Registro
from crescidoro.stats import (serie_diaria, heatmap, intervalo_total, fmt_dur, sequencia_atual,
                              niveis, nivel, maior_sequencia)
from crescidoro.storage import HistoryStore, Settings, SettingsStore, SessionCheckpoint
from crescidoro.timer import Timer


# ---------------------------------------------------------------- storage
def test_migra_formato_v1(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps([{"estado": "pomodoro", "duracao_s": 1500, "timestamp": "2026-06-30 13:25:00"}]))
    st = HistoryStore(str(p))
    r = st.registros[0]
    assert r.inicio == datetime(2026, 6, 30, 13, 0, 0)       # timestamp antigo = fim
    assert r.motivo == "desconhecido" and r.id
    novo = json.loads(p.read_text())
    assert novo["versao"] == 2 and novo["registros"][0]["id"] == r.id
    assert (tmp_path / "h.json.v1.bak").exists()
    # recarregar mantém o mesmo id
    assert HistoryStore(str(p)).registros[0].id == r.id


def test_crud_e_undo(tmp_path):
    st = HistoryStore(str(tmp_path / "h.json"))
    a = st.add(Registro("pomodoro", datetime(2026, 1, 1, 9), 1500, "natural"))
    b = st.add(Registro("break", datetime(2026, 1, 1, 9, 25), 300, "natural"))
    b2 = b.copia(); b2.duracao_s = 600
    assert st.update(b2) and st.get(b.id).duracao_s == 600
    assert st.remove(a.id) and len(st.registros) == 1
    assert st.undo() and len(st.registros) == 2           # desfaz remoção
    assert st.undo() and st.get(b.id).duracao_s == 300    # desfaz edição
    assert len(HistoryStore(str(tmp_path / "h.json")).registros) == 2


def test_arquivo_corrompido_nao_quebra(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{lixo")
    assert HistoryStore(str(p)).registros == []
    assert (tmp_path / "h.json.corrompido").exists()


def test_settings_compat(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"pomodoro": 600, "break": 300, "long_break": 900}))
    ss = SettingsStore(str(p))
    assert ss.settings.pomodoro == 600 and ss.settings.break_ == 300
    ss.settings.crescidoro_ativo = True
    ss.save()
    d = json.loads(p.read_text())
    assert d["break"] == 300 and d["crescidoro_ativo"] is True


def test_checkpoint(tmp_path):
    cp = SessionCheckpoint(str(tmp_path / "s.json"))
    cp.write(Registro("pomodoro", datetime(2026, 1, 1, 9), 700, "fechado"))
    r = cp.recover()
    assert r.duracao_s == 700 and r.motivo == "fechado"
    assert cp.recover() is None


# ---------------------------------------------------------------- stats
def _r(tipo, d, h, dur):
    return Registro(tipo, datetime.combine(d, datetime.min.time()) + timedelta(hours=h), dur)


def test_serie_inclui_dias_vazios():
    d0 = date(2026, 3, 1)
    regs = [_r("pomodoro", d0, 9, 1500), _r("pomodoro", d0 + timedelta(days=3), 9, 1500)]
    s = serie_diaria(regs, d0, d0 + timedelta(days=4))
    assert [d.total() for d in s] == [1500, 0, 0, 1500, 0]


def test_empilhamento_agrupa_por_tipo():
    d0 = date(2026, 3, 1)
    regs = [_r("break", d0, 10, 300), _r("pomodoro", d0, 11, 1500),
            _r("pomodoro", d0, 9, 1500), _r("long_break", d0, 8, 900)]
    dia = serie_diaria(regs, d0, d0)[0]
    pilha = dia.empilhados(["pomodoro", "break", "long_break"])
    assert [r.estado for r in pilha] == ["pomodoro", "pomodoro", "break", "long_break"]
    assert pilha[0].inicio.hour == 9                       # cronológico no grupo
    assert [r.estado for r in dia.empilhados(["break"])] == ["break"]


def test_intervalo_total_minimo_14():
    hoje = date(2026, 3, 20)
    a, b = intervalo_total([], hoje)
    assert (b - a).days == 13 and b == hoje


def test_heatmap_estilo_github():
    hoje = date(2026, 10, 23)   # sexta
    m = heatmap([_r("pomodoro", hoje, 9, 1500), _r("break", hoje, 10, 300)], hoje)
    assert len(m) == 7 and all(len(l) == 53 for l in m)
    assert m[0][0][0].weekday() == 6                     # linha 0 = domingo
    assert m[5][52] == (hoje, 1500)                      # sexta, última coluna; só pomodoro
    assert m[6][52][0] > hoje                            # sábado ainda no futuro
    m4 = heatmap([], hoje, semanas=4, domingo=False)
    assert len(m4[0]) == 4 and m4[0][0][0].weekday() == 0


def test_niveis_quartis():
    lim = niveis([0, 600, 1200, 1800, 2400, 3000])
    assert nivel(0, lim) == 0 and nivel(600, lim) == 1 and nivel(3000, lim) == 4


def test_maior_sequencia():
    d = date(2026, 1, 1)
    regs = [_r("pomodoro", d + timedelta(days=i), 9, 60) for i in (0, 1, 2, 5, 6)]
    assert maior_sequencia(regs) == 3


def test_sequencia():
    hoje = date(2026, 10, 23)
    regs = [_r("pomodoro", hoje - timedelta(days=i), 9, 60) for i in (1, 2, 3, 5)]
    assert sequencia_atual(regs, hoje) == 3


def test_fmt_dur():
    assert fmt_dur(45) == "45s" and fmt_dur(1500) == "25m" and fmt_dur(3900) == "1h05"


# ---------------------------------------------------------------- timer
class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _timer(**kw):
    s = Settings(pomodoro=100, break_=50, long_break=80, **kw)
    regs, nat = [], []
    rel = Relogio()
    t = Timer(s, regs.append, nat.append, clock=rel, now=lambda: datetime(2026, 1, 1, 9))
    return t, s, regs, nat, rel


def test_fim_natural_e_proximo_modo():
    t, s, regs, nat, rel = _timer()
    t.start(); rel.t = 150; t.tick()
    assert regs[0].motivo == "natural" and regs[0].duracao_s == 100
    assert nat == ["pomodoro"] and t.estado == "break" and not t.rodando


def test_pausa_nao_conta_tempo():
    t, s, regs, nat, rel = _timer()
    t.start(); rel.t = 30; t.pause(); rel.t = 1000; t.start(); rel.t = 1010; t.tick()
    assert int(t.decorrido) == 40


def test_trocar_salva_pausado_e_fechar_salva_fechado():
    t, s, regs, nat, rel = _timer()
    t.start(); rel.t = 30; t.trocar("long_break")
    assert regs[-1].motivo == "pausado" and regs[-1].duracao_s == 30 and t.estado == "long_break"
    t.start(); rel.t = 50; t.fechar()
    assert regs[-1].motivo == "fechado" and regs[-1].estado == "long_break"


def test_finalizar_sem_progresso_nao_registra():
    t, s, regs, nat, rel = _timer()
    t.finalizar()
    assert regs == []


def test_crescidoro_so_cresce_no_natural():
    t, s, regs, nat, rel = _timer(crescidoro_ativo=True, crescidoro_percentual=10)
    t.start(); rel.t = 20; t.finalizar()
    assert s.pomodoro == 100
    t.trocar("pomodoro"); t.start(); rel.t = 200; t.tick()
    assert s.pomodoro == 110 and t.crescimentos == 1


def test_long_break_a_cada_n():
    t, s, regs, nat, rel = _timer(ciclo_long=2)
    for esperado in ("break", "long_break"):
        t.trocar("pomodoro"); t.start(); rel.t += 100; t.tick()
        assert t.estado == esperado
    t.start(); rel.t += 80; t.tick()
    assert t.pomodoros_no_ciclo == 0 and t.estado == "pomodoro"
