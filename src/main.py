"""Orquestador: lee config, consulta GA4, carga deploys, genera grafico y CSV.

Uso:
    python -m src.main
"""
import io
import os
import sys
from datetime import date
from pathlib import Path

# Forzar UTF-8 en stdout/stderr (consolas Windows cp1252 no manejan emojis)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv

from src.deploys import cargar_deploys
from src.ga4_client import (
    crear_cliente,
    metricas_diarias_por_evento,
    metricas_mensuales_por_evento,
)
from src.grafico import combinar_html, construir_grafico, construir_grafico_diario, exportar

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

    # ── Grafico mensual ──
    print("📈 Construyendo grafico mensual...")
    fig_mensual = construir_grafico(
        todas,
        deploys,
        titulo="Uso del botón <b>'Importar archivos'</b> en CFER web (mensual)",
    )
    png_mensual = out_dir / "uso_importar.png"
    exportar(fig_mensual, out_dir / "_uso_importar_mensual.html", png_mensual)
    # exportar() arriba escribe un HTML temporal para reusar la logica; lo
    # eliminamos porque vamos a generar el HTML combinado con combinar_html().
    (out_dir / "_uso_importar_mensual.html").unlink(missing_ok=True)
    print(f"🖼️  {png_mensual}")

    # ── Graficos diarios del mes corriente (uno por evento) ──
    # Re-consulta GA4 (data fresh) acotada al mes actual para mostrar el
    # crecimiento dia a dia.
    hoy = date.today()
    desde_mes = f"{hoy.year:04d}-{hoy.month:02d}-01"
    hasta_mes = hoy.isoformat()

    # Color y opciones por evento. Los volumenes de Excel son ~5-7k/dia, las
    # etiquetas en las barras saturan; las desactivo solo para ese caso.
    config_diaria = [
        {
            "evento": "EDM_CM04_importar_archivo_datos",
            "color": "#dc3912",
            "etiquetas": True,
            "png_nombre": "uso_cm04_diario.png",
        },
        {
            "evento": "EDM_importar_excel_o_xml",
            "color": "#3366cc",
            "etiquetas": False,
            "png_nombre": "uso_excel_diario.png",
        },
    ]
    figuras_diarias: list = []
    for cfg in config_diaria:
        ev = cfg["evento"]
        print(f"\n📊 Re-consultando {ev} diario ({desde_mes} → {hasta_mes})")
        diarios = metricas_diarias_por_evento(client, property_id, ev, desde_mes, hasta_mes)
        total_eventos_mes = sum(m.eventos for m in diarios)
        if diarios:
            for m in diarios:
                print(f"   {m.fecha.isoformat()}  ev={m.eventos:>6,}  users={m.usuarios_activos:>5,}")
            print(f"   Total mes (eventos): {total_eventos_mes:,}")
        else:
            print("   (sin eventos en el mes corriente)")

        fig_d = construir_grafico_diario(
            diarios,
            titulo=(
                f"<b>{ev}</b> — diario {hoy.year}-{hoy.month:02d} "
                f"(total mes: {total_eventos_mes:,} eventos)"
            ),
            color_barras=cfg["color"],
            mostrar_etiquetas=cfg["etiquetas"],
        )
        figuras_diarias.append(fig_d)

        # PNG individual por gráfico diario
        png_path = out_dir / cfg["png_nombre"]
        try:
            fig_d.write_image(str(png_path), width=1400, height=420, scale=2)
            print(f"🖼️  {png_path}")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  No se pudo exportar PNG: {type(e).__name__}: {e}")

    # ── HTML combinado: mensual arriba, CM04 diario al medio, Excel diario abajo ──
    html_path = out_dir / "uso_importar.html"
    combinar_html(
        [fig_mensual, *figuras_diarias],
        titulo_pagina="Uso del botón Importar archivos en CFER web",
        html_path=html_path,
    )
    print(
        f"\n🎨 {html_path} (contiene 3 graficos: mensual + CM04 diario + Excel diario)"
    )
    print("\n✅ Listo. Abrir el HTML en el browser para revisar el grafico interactivo.")


if __name__ == "__main__":
    main()
