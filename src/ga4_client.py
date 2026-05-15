"""Cliente GA4 Data API: consulta mensual de un evento (eventos, usuarios, ratio)."""
from typing import NamedTuple

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunReportRequest,
)
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


class MetricaMensual(NamedTuple):
    """Datos mensuales agregados de un evento puntual."""
    mes: str                    # formato "YYYY-MM"
    evento: str
    eventos: int
    usuarios_activos: int       # activeUsers
    usuarios_total: int         # totalUsers
    eventos_por_usuario: float  # ev/activeUsers (0 si no hay usuarios)


def crear_cliente(creds_path: str) -> BetaAnalyticsDataClient:
    """Inicializa el cliente con el JSON del service account."""
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return BetaAnalyticsDataClient(credentials=creds)


def metricas_mensuales_por_evento(
    client: BetaAnalyticsDataClient,
    property_id: str,
    evento: str,
    desde: str,
    hasta: str,
) -> list[MetricaMensual]:
    """Consulta GA4 y devuelve metricas mensuales para un evento.

    Args:
        client: cliente GA4 ya autenticado.
        property_id: ID numerico de la property (string).
        evento: nombre exacto del evento (eventName).
        desde: fecha inicio "YYYY-MM-DD".
        hasta: fecha fin "YYYY-MM-DD" o "today".

    Returns:
        Lista de MetricaMensual ordenada por mes ascendente.
    """
    filt = FilterExpression(
        filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(
                value=evento,
                match_type=Filter.StringFilter.MatchType.EXACT,
            ),
        )
    )
    req = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="yearMonth")],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="activeUsers"),
            Metric(name="totalUsers"),
        ],
        date_ranges=[DateRange(start_date=desde, end_date=hasta)],
        dimension_filter=filt,
        limit=100,
    )
    resp = client.run_report(req)

    filas: list[MetricaMensual] = []
    for row in resp.rows:
        ym = row.dimension_values[0].value  # GA4 devuelve "YYYYMM"
        ev_cnt = int(row.metric_values[0].value)
        au = int(row.metric_values[1].value)
        tu = int(row.metric_values[2].value)
        ratio = (ev_cnt / au) if au else 0.0
        filas.append(
            MetricaMensual(
                mes=f"{ym[:4]}-{ym[4:]}",
                evento=evento,
                eventos=ev_cnt,
                usuarios_activos=au,
                usuarios_total=tu,
                eventos_por_usuario=ratio,
            )
        )
    return sorted(filas, key=lambda r: r.mes)
