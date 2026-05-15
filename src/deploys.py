"""Lectura de la bitacora de deploys de CFER web desde un CSV manual.

El CSV se mantiene a mano hasta que el repo de CFER web este disponible via
GitLab API. Cuando ese acceso este, sumar una funcion `cargar_deploys_gitlab`
y orquestar ambas fuentes desde `main.py`.
"""
import csv
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple


class Deploy(NamedTuple):
    """Hito de despliegue. fecha en `date`, titulo y descripcion como strings."""
    fecha: date
    titulo: str
    descripcion: str


def cargar_deploys(csv_path: Path) -> list[Deploy]:
    """Lee deploys.csv (cabecera: fecha,titulo,descripcion).

    - Tolera filas vacias o con fecha invalida (las saltea con warning).
    - Devuelve la lista ordenada por fecha ascendente.
    """
    if not csv_path.exists():
        print(f"⚠️  No se encuentra {csv_path}; deploys vacio.")
        return []

    deploys: list[Deploy] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for nro_fila, row in enumerate(reader, start=2):  # arranca en 2: header es 1
            fecha_str = (row.get("fecha") or "").strip()
            if not fecha_str:
                continue
            try:
                fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                print(f"  ⚠️  Fila {nro_fila}: fecha inválida ({fecha_str!r}), salteada.")
                continue
            deploys.append(
                Deploy(
                    fecha=fecha_dt,
                    titulo=(row.get("titulo") or "").strip(),
                    descripcion=(row.get("descripcion") or "").strip(),
                )
            )
    return sorted(deploys, key=lambda d: d.fecha)
