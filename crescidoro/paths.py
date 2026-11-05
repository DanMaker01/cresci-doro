"""Resolução de caminhos para recursos empacotados e dados do usuário."""
import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_path(nome: str) -> str:
    """Recursos somente-leitura (som, ícone). Funciona em dev e no PyInstaller."""
    base = getattr(sys, "_MEIPASS", None) or _project_root()
    return os.path.join(base, nome)


def data_dir() -> str:
    """Pasta onde histórico/config são gravados.

    - Executável: ao lado do .exe (os dados sobrevivem entre execuções,
      diferente da pasta temporária _MEIPASS do --onefile).
    - Dev: raiz do projeto.
    Pode ser sobrescrita pela variável de ambiente CRESCIDORO_DATA.
    """
    override = os.environ.get("CRESCIDORO_DATA")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return _project_root()


def data_path(nome: str) -> str:
    return os.path.join(data_dir(), nome)


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
