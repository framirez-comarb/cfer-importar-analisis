"""Orquestador: lee config, consulta GA4, carga deploys, genera grafico y CSV.

Uso:
    python -m src.main
"""
import io
import os
import sys
from pathlib import Path

# Forzar UTF-8 en stdout/stderr (consolas Windows cp1252 no manejan emojis)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv

from src.deploys import cargar_deploys
from src.ga4_client import crear_cliente, metricas_mensuales_por_evento
from src.grafico import construir_grafico, exportar

# Eventos a analizar (el orden importa para que en el grafico CM04 quede sobre Excel)
EVENTOS: list[str] = [
    "EDM_importar_excel_o_xml",
    "EDM_CM04_importar_archivo_datos",
]


def _exigir(env: str) -> str:
    val = os.environ.get(env)
    if not val:
        print(f"❌ Falta variable de entorno {env}. Copiar .env.example a .env y completarla.")
        sys.exit(1)
    return val


def main() -> None:
    load_dotenv()
    property_id = _exigir("GA4_PROPERTY_ID")
    creds_path = _exigir("GA4_SA_PATH")
    desde = os.environ.get("FECHA_DESDE") or "2025-06-01"
    hasta = os.environ.get("FECHA_HASTA") or "today"

    if not Path(creds_path).is_file():
        print(f"❌ GA4_SA_PATH apunta a un path que no existe: {creds_path}")
        sys.exit(1)

    print(f"🔌 Conectando a GA4 property {property_id}")
    client = crear_cliente(creds_path)

    todas: list = []
    for ev in EVENTOS:
        print(f"\n📊 Consultando {ev}  ({desde} → {hasta})")
        metricas = metricas_mensuales_por_evento(client, property_id, ev, desde, hasta)
        if not metricas:
            print(f"   (sin filas en el periodo)")
            continue
        todas.extend(metricas)
        for m in metricas:
            print(
                f"   {m.mes}   ev={m.eventos:>7,}   users={m.usuarios_activos:>6,}"
                f"   ev/user={m.eventos_por_usuario:>6.2f}"
            )

    # Diferencia activeUsers vs totalUsers (lo pidio el prompt)
    print("\n🔍 Diferencia activeUsers vs totalUsers (mes a mes):")
    diferentes = [m for m in todas if m.usuarios_activos != m.usuarios_total]
    if not diferentes:
        print("   Ninguna — coinciden en todos los meses.")
    else:
        for m in diferentes:
            print(
                f"   {m.mes} ({m.evento}): active={m.usuarios_activos} vs total={m.usuarios_total}"
            )

    # ── Deploys ──
    deploys_csv = Path("deploys.csv")
    print(f"\n📋 Leyendo deploys desde {deploys_csv}")
    deploys = cargar_deploys(deploys_csv)
    print(f"   {len(deploys)} deploys cargados.")
    for d in deploys:
        print(f"     {d.fecha.isoformat()} — {d.titulo}")

    # ── CSV de salida ──
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    df_out = pd.DataFrame(
        [
            {
                "mes": m.mes,
                "evento": m.evento,
                "eventos": m.eventos,
                "usuarios": m.usuarios_activos,
                "eventos_por_usuario": round(m.eventos_por_usuario, 2),
            }
            for m in todas
        ]
    ).sort_values(["mes", "evento"])
    csv_path = out_dir / "datos_mensuales.csv"
    df_out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 {csv_path}")

    # ── Grafico ──
    print("📈 Construyendo grafico...")
    fig = construir_grafico(
        todas,
        deploys,
        titulo="Uso del botón <b>'Importar archivos'</b> en CFER web (mensual)",
    )
    html_path = out_dir / "uso_importar.html"
    png_path = out_dir / "uso_importar.png"
    exportar(fig, html_path, png_path)
    print(f"🎨 {html_path}")
    print(f"🖼️  {png_path}")
    print("\n✅ Listo. Abrir el HTML en el browser para revisar el grafico interactivo.")


if __name__ == "__main__":
    main()
