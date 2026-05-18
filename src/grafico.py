"""Construccion del grafico interactivo Plotly y export a HTML/PNG."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.deploys import Deploy
from src.ga4_client import MetricaDiaria, MetricaMensual

# Paleta consistente
COLOR_EXCEL = "#3366cc"
COLOR_CM04 = "#dc3912"
COLOR_USERS = "#ff9900"
COLOR_RATIO = "#109618"
COLOR_DEPLOY = "rgba(120, 120, 120, 0.55)"


def _eje_meses(metricas: list[MetricaMensual]) -> list[str]:
    """Devuelve la lista ordenada de meses presentes en los datos (formato YYYY-MM)."""
    return sorted({m.mes for m in metricas})


def construir_grafico(
    metricas: list[MetricaMensual],
    deploys: list[Deploy],
    titulo: str,
) -> go.Figure:
    """Arma el grafico:
      - Barras agrupadas: eventos por mes, una serie por evento.
      - Linea (eje primario): usuarios activos totales (suma de eventos).
      - Linea punteada (eje secundario): eventos / usuario activo (agregado).
      - Marcas verticales: deploys del CSV.
      - Anotaciones: pico feb/2026 y primer mes de CM04.
    """
    df = pd.DataFrame(
        [
            {
                "mes": m.mes,
                "evento": m.evento,
                "eventos": m.eventos,
                "usuarios": m.usuarios_activos,
            }
            for m in metricas
        ]
    )
    meses = _eje_meses(metricas)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # ── Barras agrupadas por evento ──
    eventos_unicos = sorted(df["evento"].unique())
    paleta = {
        "EDM_importar_excel_o_xml": COLOR_EXCEL,
        "EDM_CM04_importar_archivo_datos": COLOR_CM04,
    }
    for ev in eventos_unicos:
        sub = df[df["evento"] == ev].set_index("mes").reindex(meses).fillna(0)
        fig.add_trace(
            go.Bar(
                x=sub.index,
                y=sub["eventos"],
                name=ev,
                marker_color=paleta.get(ev, "#999999"),
                hovertemplate=(
                    f"<b>{ev}</b><br>Mes: %{{x}}<br>Eventos: %{{y:,}}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    # ── Linea: usuarios activos totales por mes (agregados a traves de eventos) ──
    users_por_mes = df.groupby("mes")["usuarios"].sum().reindex(meses).fillna(0)
    fig.add_trace(
        go.Scatter(
            x=users_por_mes.index,
            y=users_por_mes.values,
            mode="lines+markers",
            name="Usuarios activos (suma)",
            line=dict(color=COLOR_USERS, width=3),
            marker=dict(size=8),
            hovertemplate=(
                "<b>Usuarios activos</b><br>Mes: %{x}<br>%{y:,}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    # ── Linea punteada eje secundario: eventos / usuario (agregado) ──
    eventos_por_mes = df.groupby("mes")["eventos"].sum().reindex(meses).fillna(0)
    ratio = (eventos_por_mes / users_por_mes.replace(0, pd.NA)).fillna(0).round(2)
    fig.add_trace(
        go.Scatter(
            x=ratio.index,
            y=ratio.values,
            mode="lines+markers",
            name="Eventos / usuario",
            line=dict(color=COLOR_RATIO, dash="dot", width=2),
            marker=dict(size=6, symbol="diamond"),
            hovertemplate=(
                "<b>Eventos por usuario</b><br>Mes: %{x}<br>%{y:.2f}<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    # ── Marcas verticales de deploys ──
    # Para cada deploy: vline anclada al mes y una anotacion en la zona superior.
    # Las anotaciones se escalonan verticalmente para evitar encimarse cuando
    # hay varios deploys cercanos en el tiempo.
    niveles_y = [1.04, 1.10, 1.16, 1.22]  # rota entre niveles
    deploys_visibles = [
        d for d in deploys
        if f"{d.fecha.year:04d}-{d.fecha.month:02d}" in meses
    ]
    for i, d in enumerate(deploys_visibles):
        mes_deploy = f"{d.fecha.year:04d}-{d.fecha.month:02d}"
        y_lvl = niveles_y[i % len(niveles_y)]
        fig.add_vline(
            x=mes_deploy,
            line_dash="dash",
            line_color=COLOR_DEPLOY,
            line_width=2,
        )
        fig.add_annotation(
            x=mes_deploy,
            y=y_lvl,
            yref="paper",
            text=f"📌 {d.titulo}",
            showarrow=False,
            font=dict(size=9, color="#555"),
            xanchor="left",
            yanchor="middle",
            hovertext=f"{d.fecha.isoformat()} — {d.descripcion}",
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc",
            borderwidth=1,
            borderpad=2,
        )

    # ── Anotaciones destacadas ──
    pico_feb = df[
        (df["evento"] == "EDM_importar_excel_o_xml") & (df["mes"] == "2026-02")
    ]
    if not pico_feb.empty:
        fig.add_annotation(
            x="2026-02",
            y=int(pico_feb["eventos"].iloc[0]),
            text="🚀 Pico feb/2026",
            showarrow=True,
            arrowhead=2,
            ax=-40,
            ay=-40,
            font=dict(size=12, color=COLOR_EXCEL),
        )

    cm04 = (
        df[df["evento"] == "EDM_CM04_importar_archivo_datos"]
        .sort_values("mes")
        .reset_index(drop=True)
    )
    if not cm04.empty:
        primer_mes = cm04.iloc[0]["mes"]
        primer_ev = int(cm04.iloc[0]["eventos"])
        fig.add_annotation(
            x=primer_mes,
            y=primer_ev,
            text=f"🎉 Lanzamiento CM04 ({primer_mes})",
            showarrow=True,
            arrowhead=2,
            ax=40,
            ay=-50,
            font=dict(size=11, color=COLOR_CM04),
        )

    # ── Layout ──
    # Margin top generoso para dar lugar al titulo + anotaciones escalonadas
    # de deploys (que viven en yref=paper hasta y=1.22).
    fig.update_layout(
        title=dict(
            text=titulo,
            x=0.5,
            xanchor="center",
            y=0.98,
            yanchor="top",
            font=dict(size=16),
        ),
        barmode="group",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,  # legend abajo del eje X (no compite con anotaciones)
            xanchor="left",
            x=0,
        ),
        margin=dict(t=160, b=100, l=70, r=70),
        height=720,
        plot_bgcolor="rgba(245, 245, 245, 0.4)",
    )
    fig.update_xaxes(title="Mes", tickangle=-30)
    fig.update_yaxes(title_text="Eventos / Usuarios", secondary_y=False)
    fig.update_yaxes(
        title_text="Eventos por usuario",
        secondary_y=True,
        showgrid=False,
        rangemode="tozero",
    )
    return fig


def exportar(fig: go.Figure, html_path: Path, png_path: Path) -> None:
    """Persiste el grafico como HTML interactivo y como PNG estatico.

    Si kaleido no esta disponible (o falla), avisa y sigue sin abortar.
    """
    html_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(html_path, include_plotlyjs="cdn")
    try:
        fig.write_image(str(png_path), width=1400, height=720, scale=2)
    except Exception as e:  # noqa: BLE001 — queremos cualquier fallo aca
        print(f"⚠️  No se pudo exportar PNG (necesita kaleido): {type(e).__name__}: {e}")


def construir_grafico_diario(
    metricas: list[MetricaDiaria],
    titulo: str,
    color_barras: str = COLOR_CM04,
    mostrar_etiquetas: bool = True,
) -> go.Figure:
    """Grafico de barras + linea de usuarios para un evento, a granularidad
    diaria. Pensado para ver el mes corriente.

    Args:
        metricas: lista de datos diarios del evento.
        titulo: titulo del grafico.
        color_barras: color de las barras (default rojo CM04).
        mostrar_etiquetas: si True, muestra el valor sobre cada barra. Util
            para volumenes bajos (CM04). Para volumenes altos las etiquetas
            saturan el grafico.
    """
    fig = go.Figure()
    if not metricas:
        fig.update_layout(
            title=dict(text=titulo + " — (sin eventos en el rango)", x=0.5),
            height=300,
        )
        return fig

    df = pd.DataFrame(
        [
            {
                "fecha": m.fecha,
                "eventos": m.eventos,
                "usuarios": m.usuarios_activos,
            }
            for m in metricas
        ]
    )
    fig.add_trace(
        go.Bar(
            x=df["fecha"],
            y=df["eventos"],
            name="Eventos",
            marker_color=color_barras,
            text=df["eventos"] if mostrar_etiquetas else None,
            textposition="outside" if mostrar_etiquetas else "none",
            hovertemplate=(
                "<b>%{x|%Y-%m-%d}</b><br>Eventos: %{y:,}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["fecha"],
            y=df["usuarios"],
            mode="lines+markers",
            name="Usuarios activos",
            line=dict(color=COLOR_USERS, width=2),
            marker=dict(size=8),
            hovertemplate=(
                "<b>%{x|%Y-%m-%d}</b><br>Usuarios: %{y}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center", font=dict(size=15)),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="left",
            x=0,
        ),
        margin=dict(t=70, b=80, l=70, r=70),
        height=420,
        plot_bgcolor="rgba(245, 245, 245, 0.4)",
    )
    fig.update_xaxes(title="Día", tickformat="%d/%m", dtick="D1")
    fig.update_yaxes(title="Eventos / Usuarios", rangemode="tozero")
    return fig


def combinar_html(
    figs: list[go.Figure],
    titulo_pagina: str,
    html_path: Path,
) -> None:
    """Concatena varias figuras Plotly en un solo HTML, una abajo de otra.

    La primera figura incluye plotly.js (vía CDN); las siguientes lo
    referencian para no duplicar el bundle.
    """
    if not figs:
        return
    html_path.parent.mkdir(parents=True, exist_ok=True)
    partes: list[str] = []
    for i, fig in enumerate(figs):
        partes.append(
            fig.to_html(
                full_html=False,
                include_plotlyjs="cdn" if i == 0 else False,
                config={"displayModeBar": True, "responsive": True},
            )
        )

    separador = (
        '<hr style="margin: 36px 60px; border: 0; border-top: 1px solid #ddd;">'
    )
    cuerpo = separador.join(partes)
    documento = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{titulo_pagina}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 12px 0; background: #fafafa; }}
  </style>
</head>
<body>
{cuerpo}
</body>
</html>"""
    html_path.write_text(documento, encoding="utf-8")
