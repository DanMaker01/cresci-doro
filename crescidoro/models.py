"""Modelos de domínio: tipos de sessão, motivos de término e o registro."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta

# Ordem importa: é a ordem de empilhamento no gráfico e dos botões.
TIPOS = ("pomodoro", "break", "long_break")
TIPO_LABEL = {"pomodoro": "POMODORO", "break": "BREAK", "long_break": "LONG"}

MOTIVOS = ("natural", "pausado", "fechado", "manual")
MOTIVO_LABEL = {
    "natural": "natural",
    "pausado": "pausado",
    "fechado": "fechado",
    "manual": "manual",
    "desconhecido": "?",
}
MOTIVO_DESC = {
    "natural": "tempo chegou ao fim",
    "pausado": "encerrado antes do fim",
    "fechado": "app fechado no meio",
    "manual": "adicionado à mão",
    "desconhecido": "registro antigo",
}

FMT_DT = "%Y-%m-%d %H:%M:%S"


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Registro:
    estado: str
    inicio: datetime
    duracao_s: int
    motivo: str = "natural"
    id: str = field(default_factory=novo_id)

    # ---- derivados -------------------------------------------------------
    @property
    def fim(self) -> datetime:
        return self.inicio + timedelta(seconds=self.duracao_s)

    @property
    def dia(self) -> date:
        return self.inicio.date()

    # ---- (de)serialização -------------------------------------------------
    def to_json(self) -> dict:
        d = asdict(self)
        d["inicio"] = self.inicio.strftime(FMT_DT)
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Registro":
        """Aceita o formato novo e o antigo ({estado, duracao_s, timestamp=fim})."""
        estado = d.get("estado", "pomodoro")
        if estado not in TIPOS:
            estado = "pomodoro"
        dur = max(0, int(d.get("duracao_s", 0)))
        if "inicio" in d:
            inicio = datetime.strptime(d["inicio"], FMT_DT)
        else:  # legado: timestamp era o momento do fim
            fim = datetime.strptime(d["timestamp"], FMT_DT)
            inicio = fim - timedelta(seconds=dur)
        motivo = d.get("motivo") or "desconhecido"
        return cls(estado=estado, inicio=inicio, duracao_s=dur,
                   motivo=motivo, id=d.get("id") or novo_id())

    def copia(self) -> "Registro":
        return Registro(self.estado, self.inicio, self.duracao_s, self.motivo, self.id)
