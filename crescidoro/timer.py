"""Máquina de estados do timer (sem dependência de pygame — testável)."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

from .models import Registro, TIPOS
from .storage import Settings


class Timer:
    """Conta o tempo de uma sessão e gera Registros quando ela termina.

    Motivos de término:
      natural  – o tempo chegou a zero
      pausado  – usuário encerrou/trocou de modo antes do fim
      fechado  – app fechado com a sessão em andamento
    """

    def __init__(self, settings: Settings,
                 on_registro: Callable[[Registro], None],
                 on_natural: Optional[Callable[[str], None]] = None,
                 clock: Callable[[], float] = time.monotonic,
                 now: Callable[[], datetime] = datetime.now):
        self.s = settings
        self.on_registro = on_registro
        self.on_natural = on_natural
        self._clock = clock
        self._now = now

        self.estado = "pomodoro"
        self.rodando = False
        self.decorrido = 0.0            # segundos efetivamente contados
        self.inicio: Optional[datetime] = None  # 1º start da sessão
        self._ultimo = 0.0
        self.pomodoros_no_ciclo = 0     # para decidir o long break
        self.crescimentos = 0           # nº de vezes que o crescidoro agiu

    # ---- consultas ---------------------------------------------------------
    @property
    def total(self) -> int:
        return self.s.duracao(self.estado)

    @property
    def restante(self) -> float:
        return max(0.0, self.total - self.decorrido)

    @property
    def progresso(self) -> float:
        return min(1.0, self.decorrido / self.total) if self.total else 1.0

    @property
    def em_andamento(self) -> bool:
        return self.decorrido >= 1

    def registro_parcial(self, motivo: str) -> Optional[Registro]:
        if not self.em_andamento or self.inicio is None:
            return None
        return Registro(self.estado, self.inicio, int(self.decorrido), motivo)

    # ---- controle ----------------------------------------------------------
    def start(self) -> None:
        if self.rodando:
            return
        self.rodando = True
        self._ultimo = self._clock()
        if self.inicio is None:
            self.inicio = self._now().replace(microsecond=0)

    def pause(self) -> None:
        if self.rodando:
            self.tick()
            self.rodando = False

    def toggle(self) -> None:
        self.pause() if self.rodando else self.start()

    def tick(self) -> None:
        if not self.rodando:
            return
        agora = self._clock()
        self.decorrido += agora - self._ultimo
        self._ultimo = agora
        if self.decorrido >= self.total:
            self.decorrido = float(self.total)
            self._finalizar("natural")

    def finalizar(self) -> None:
        """Encerra a sessão atual antes do fim (motivo 'pausado')."""
        self.pause()
        if self.em_andamento:
            self._finalizar("pausado")
        else:
            self._resetar(self.estado)

    def trocar(self, tipo: str) -> None:
        """Muda de modo. Se havia progresso, ele é salvo como 'pausado'."""
        assert tipo in TIPOS
        self.pause()
        reg = self.registro_parcial("pausado")
        if reg:
            self.on_registro(reg)
        self._resetar(tipo)

    def fechar(self) -> Optional[Registro]:
        """Chamado ao sair do app."""
        self.pause()
        reg = self.registro_parcial("fechado")
        if reg:
            self.on_registro(reg)
        self._resetar(self.estado)
        return reg

    def duracao_alterada(self, tipo: str) -> None:
        """Após editar a duração: mantém o que já foi contado."""
        if tipo == self.estado and self.decorrido >= self.total:
            self.decorrido = max(0.0, self.total - 1)

    # ---- internos ----------------------------------------------------------
    def _resetar(self, tipo: str) -> None:
        self.estado = tipo
        self.rodando = False
        self.decorrido = 0.0
        self.inicio = None

    def _finalizar(self, motivo: str) -> None:
        reg = self.registro_parcial(motivo)
        terminado = self.estado
        self.rodando = False
        if reg:
            self.on_registro(reg)

        proximo = "pomodoro"
        if terminado == "pomodoro":
            if motivo == "natural":
                self.pomodoros_no_ciclo += 1
                if self.s.crescidoro_ativo:
                    fator = 1 + self.s.crescidoro_percentual / 100
                    self.s.set_duracao("pomodoro", round(self.s.pomodoro * fator))
                    self.crescimentos += 1
            n = self.s.ciclo_long
            if n > 0 and self.pomodoros_no_ciclo >= n:
                proximo = "long_break"
            else:
                proximo = "break"
        elif terminado == "long_break":
            self.pomodoros_no_ciclo = 0

        self._resetar(proximo)
        if motivo == "natural" and self.on_natural:
            self.on_natural(terminado)
