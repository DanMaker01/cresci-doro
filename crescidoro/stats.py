"""Agregações do histórico para gráficos e heatmap (puro, sem pygame)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

from .models import Registro, TIPOS


@dataclass
class Dia:
    data: date
    registros: list = field(default_factory=list)  # já ordenados p/ empilhar

    def total(self, tipos: Iterable[str] = TIPOS) -> int:
        tipos = set(tipos)
        return sum(r.duracao_s for r in self.registros if r.estado in tipos)

    def por_tipo(self) -> dict:
        d = {t: 0 for t in TIPOS}
        for r in self.registros:
            d[r.estado] += r.duracao_s
        return d

    def empilhados(self, tipos: Iterable[str]) -> list:
        """Registros visíveis na ordem de empilhamento: agrupados por tipo
        (pomodoro → break → long) e cronológicos dentro de cada grupo."""
        tipos = list(tipos)
        ordem = {t: i for i, t in enumerate(TIPOS)}
        regs = [r for r in self.registros if r.estado in tipos]
        return sorted(regs, key=lambda r: (ordem[r.estado], r.inicio))


def serie_diaria(registros: list[Registro], inicio: date, fim: date) -> list[Dia]:
    """Um Dia por data em [inicio, fim], incluindo dias SEM registro (zerados)."""
    if fim < inicio:
        inicio, fim = fim, inicio
    n = (fim - inicio).days + 1
    dias = [Dia(inicio + timedelta(days=i)) for i in range(n)]
    for r in registros:
        idx = (r.dia - inicio).days
        if 0 <= idx < n:
            dias[idx].registros.append(r)
    return dias


def intervalo_total(registros: list[Registro], hoje: date, minimo: int = 14) -> tuple[date, date]:
    """Do primeiro registro até hoje (pelo menos `minimo` dias)."""
    primeiro = min((r.dia for r in registros), default=hoje)
    primeiro = min(primeiro, hoje - timedelta(days=minimo - 1))
    ultimo = max([hoje] + [r.dia for r in registros])
    return primeiro, ultimo


def inicio_semana(d: date) -> date:
    return d - timedelta(days=d.weekday())  # segunda-feira


def heatmap(registros: list[Registro], hoje: date, semanas: int = 53,
            tipos: Iterable[str] = ("pomodoro",), domingo: bool = True) -> list[list[tuple[date, int]]]:
    """Matriz [linha 0..6][semana 0..semanas-1] → (data, segundos), estilo GitHub.

    A última coluna é a semana atual. Com `domingo=True` as linhas vão de
    domingo (0) a sábado (6); senão, de segunda a domingo.
    """
    ini_sem = hoje - timedelta(days=(hoje.weekday() + 1) % 7 if domingo else hoje.weekday())
    seg0 = ini_sem - timedelta(weeks=semanas - 1)
    fim = seg0 + timedelta(days=7 * semanas - 1)
    tipos = set(tipos)
    totais: dict[date, int] = {}
    for r in registros:
        if r.estado in tipos and seg0 <= r.dia <= fim:
            totais[r.dia] = totais.get(r.dia, 0) + r.duracao_s
    return [[(seg0 + timedelta(weeks=w, days=wd),
              totais.get(seg0 + timedelta(weeks=w, days=wd), 0))
             for w in range(semanas)] for wd in range(7)]


def niveis(valores: Iterable[int]) -> list[int]:
    """Limiares (quartis dos dias com atividade) para os níveis 1..4."""
    v = sorted(x for x in valores if x > 0)
    if not v:
        return [1, 1, 1]
    q = lambda f: v[min(len(v) - 1, int(f * (len(v) - 1)))]  # noqa: E731
    return [q(0.25), q(0.5), q(0.75)]


def nivel(seg: int, limiares: list[int]) -> int:
    if seg <= 0:
        return 0
    return 1 + sum(seg > l for l in limiares)


def maior_sequencia(registros: list[Registro], tipos: Iterable[str] = ("pomodoro",)) -> int:
    tipos = set(tipos)
    dias = sorted({r.dia for r in registros if r.estado in tipos})
    melhor = atual = 0
    ant = None
    for d in dias:
        atual = atual + 1 if ant and (d - ant).days == 1 else 1
        melhor = max(melhor, atual)
        ant = d
    return melhor


def sequencia_atual(registros: list[Registro], hoje: date) -> int:
    """Dias seguidos (até hoje ou ontem) com pelo menos um pomodoro."""
    dias = {r.dia for r in registros if r.estado == "pomodoro"}
    d = hoje if hoje in dias else hoje - timedelta(days=1)
    n = 0
    while d in dias:
        n += 1
        d -= timedelta(days=1)
    return n


# ---- formatação -----------------------------------------------------------
def fmt_mmss(seg: float) -> str:
    seg = max(0, int(seg))
    m, s = divmod(seg, 60)
    return f"{m:02d}:{s:02d}"


def fmt_dur(seg: float) -> str:
    """Formato curto e legível: 45s, 25m, 1h05."""
    seg = max(0, int(round(seg)))
    if seg < 60:
        return f"{seg}s"
    m = seg // 60
    if m < 60:
        return f"{m}m" if seg % 60 == 0 or m >= 10 else f"{m}m{seg % 60:02d}"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}"


DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
DIAS_DOMINGO = ("dom", "seg", "ter", "qua", "qui", "sex", "sáb")
