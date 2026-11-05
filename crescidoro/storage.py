"""Persistência: histórico (CRUD + desfazer), configurações e sessão em andamento.

Toda escrita é atômica (arquivo temporário + os.replace) para não corromper
o JSON se o app for fechado no meio da gravação.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from .models import Registro, TIPOS

VERSAO_HIST = 2


def _write_json_atomic(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Histórico
# =============================================================================
class HistoryStore:
    """Lista de registros com operações de adicionar/editar/remover e desfazer."""

    MAX_UNDO = 50

    def __init__(self, path: str):
        self.path = path
        self.registros: list[Registro] = []
        self._undo: list[list[Registro]] = []
        self.on_change: Optional[Callable[[], None]] = None
        self.load()

    # ---- IO ----------------------------------------------------------------
    def load(self) -> None:
        if not os.path.exists(self.path):
            self.registros = []
            return
        try:
            raw = _read_json(self.path)
        except (OSError, ValueError):
            # arquivo corrompido: preserva uma cópia e começa vazio
            shutil.copyfile(self.path, self.path + ".corrompido")
            self.registros = []
            return

        if isinstance(raw, list):  # formato v1 → migra, guardando backup
            bak = self.path + ".v1.bak"
            if not os.path.exists(bak):
                shutil.copyfile(self.path, bak)
            itens, migrar = raw, True
        else:
            itens, migrar = raw.get("registros", []), False

        regs = []
        for d in itens:
            try:
                regs.append(Registro.from_json(d))
            except (KeyError, ValueError, TypeError):
                continue
        self.registros = sorted(regs, key=lambda r: r.inicio)
        if migrar:
            self.save()

    def save(self) -> None:
        _write_json_atomic(self.path, {
            "versao": VERSAO_HIST,
            "registros": [r.to_json() for r in self.registros],
        })

    # ---- mutações (todas passam por _commit) ------------------------------
    def _snapshot(self) -> None:
        self._undo.append([r.copia() for r in self.registros])
        del self._undo[:-self.MAX_UNDO]

    def _commit(self) -> None:
        self.registros.sort(key=lambda r: r.inicio)
        self.save()
        if self.on_change:
            self.on_change()

    def add(self, reg: Registro) -> Registro:
        self._snapshot()
        self.registros.append(reg)
        self._commit()
        return reg

    def update(self, reg: Registro) -> bool:
        for i, r in enumerate(self.registros):
            if r.id == reg.id:
                self._snapshot()
                self.registros[i] = reg.copia()
                self._commit()
                return True
        return False

    def remove(self, reg_id: str) -> bool:
        for i, r in enumerate(self.registros):
            if r.id == reg_id:
                self._snapshot()
                del self.registros[i]
                self._commit()
                return True
        return False

    def undo(self) -> bool:
        if not self._undo:
            return False
        self.registros = self._undo.pop()
        self._commit()
        return True

    @property
    def pode_desfazer(self) -> bool:
        return bool(self._undo)

    def get(self, reg_id: str) -> Optional[Registro]:
        return next((r for r in self.registros if r.id == reg_id), None)


# =============================================================================
# Configurações
# =============================================================================
@dataclass
class Settings:
    pomodoro: int = 25 * 60
    break_: int = 5 * 60
    long_break: int = 30 * 60
    crescidoro_ativo: bool = False
    crescidoro_percentual: int = 10
    ciclo_long: int = 4            # long break a cada N pomodoros (0 = nunca)
    grafico_modo: str = "barras"   # "barras" | "linha" | "mapa"
    grafico_periodo: str = "14d"   # "14d" | "total"
    grafico_tipos: list = field(default_factory=lambda: list(TIPOS))

    # O JSON mantém as chaves antigas ("pomodoro", "break", "long_break")
    def duracao(self, tipo: str) -> int:
        return {"pomodoro": self.pomodoro, "break": self.break_,
                "long_break": self.long_break}[tipo]

    def set_duracao(self, tipo: str, seg: int) -> None:
        seg = max(1, min(int(seg), 999 * 60 + 59))
        if tipo == "pomodoro":
            self.pomodoro = seg
        elif tipo == "break":
            self.break_ = seg
        else:
            self.long_break = seg

    def to_json(self) -> dict:
        d = asdict(self)
        d["break"] = d.pop("break_")
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Settings":
        s = cls()
        for k, v in d.items():
            attr = "break_" if k == "break" else k
            if hasattr(s, attr):
                setattr(s, attr, v)
        s.grafico_tipos = [t for t in s.grafico_tipos if t in TIPOS] or list(TIPOS)
        if s.grafico_modo not in ("barras", "linha", "mapa"):
            s.grafico_modo = "barras"
        if s.grafico_periodo not in ("14d", "total"):
            s.grafico_periodo = "14d"
        for t in TIPOS:
            s.set_duracao(t, s.duracao(t))
        return s


class SettingsStore:
    def __init__(self, path: str):
        self.path = path
        self.settings = self.load()

    def load(self) -> Settings:
        try:
            return Settings.from_json(_read_json(self.path))
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self) -> None:
        _write_json_atomic(self.path, self.settings.to_json())


# =============================================================================
# Sessão em andamento (recuperação após crash / fechamento forçado)
# =============================================================================
class SessionCheckpoint:
    def __init__(self, path: str):
        self.path = path

    def write(self, reg: Registro) -> None:
        try:
            _write_json_atomic(self.path, reg.to_json())
        except OSError:
            pass

    def clear(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass

    def recover(self) -> Optional[Registro]:
        """Lê uma sessão que ficou pendente e apaga o arquivo."""
        if not os.path.exists(self.path):
            return None
        try:
            reg = Registro.from_json(_read_json(self.path))
            reg.motivo = "fechado"
        except (OSError, ValueError, KeyError, TypeError):
            reg = None
        self.clear()
        return reg if reg and reg.duracao_s > 0 else None
