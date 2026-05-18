# cfer-importar-analisis

📊 **Reporte en vivo**: <https://framirez-comarb.github.io/cfer-importar-analisis/>

Análisis mensual del uso del botón **"Importar archivos"** del modal de DJ (CM03/CM04) en **CFER web**, y correlación con los deploys del sistema.

Pedido por Gustavo Bodner (Producto/UGT, Comarb) en la Weekly del 11/05/2026 a partir del crecimiento exponencial observado en GA4 entre ago/2025 y feb/2026.

## Métricas (mensuales, por evento)

1. Número de eventos
2. Usuarios activos (`activeUsers`)
3. Eventos por usuario activo (eventos / activeUsers)

## Eventos analizados

| Evento | Cobertura | Descripción |
|---|---|---|
| `EDM_importar_excel_o_xml` | ~99,99% del volumen | Botón de importar en CM03 (incluye el legacy del modal viejo). Es el del pico de feb/2026. |
| `EDM_CM04_importar_archivo_datos` | Muy bajo (recién lanzado) | Específico del nuevo flujo CM04. Primer mes con datos: abril/2026. |

## Property GA4

ID: `373855714` (CFER web — hostname `sifereweb.comarb.gob.ar`). Mismo service account que el resto de los proyectos COMARB.

## Estructura

```
.
├── README.md
├── requirements.txt
├── .env.example          # template; copiar a .env
├── deploys.csv           # bitácora de despliegues (manual desde Drive)
├── src/
│   ├── ga4_client.py     # cliente GA4 (consulta mensual por evento)
│   ├── deploys.py        # lectura de deploys.csv
│   ├── grafico.py        # construcción del Plotly + export
│   └── main.py           # orquestador
└── output/               # gitignored — generado por el script
    ├── uso_importar.html
    ├── uso_importar.png
    └── datos_mensuales.csv
```

## Uso

```bash
# 1. Setup (una sola vez)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# 2. Configurar credenciales
cp .env.example .env
# Editar .env con el path al JSON del service account de GA4

# 3. Editar deploys.csv con la bitácora real de despliegues

# 4. Correr
python -m src.main
```

Outputs en `output/`:
- `index.html` — los 3 gráficos (mensual + CM04 diario + Excel diario)
- `uso_importar.png` — versión estática del gráfico mensual
- `uso_cm04_diario.png` — versión estática del diario de CM04
- `uso_excel_diario.png` — versión estática del diario de Excel
- `datos_mensuales.csv` — tabla mensual de respaldo

## Publicación vía GitHub Pages

El reporte se publica automáticamente en
<https://framirez-comarb.github.io/cfer-importar-analisis/> a partir del
`output/index.html` que regenera el workflow.

Repo público para que Pages pueda servirlo con plan Free. La data del reporte
son agregados mensuales/diarios (eventos y usuarios totales), sin CUITs ni
datos personales. Las credenciales del service account viven solo en GitHub
Secrets (`SERVICE_ACCOUNT_JSON`), nunca en el repo.

## Automatización

GitHub Actions (`.github/workflows/refresh.yml`) corre el script de lunes a
viernes a las **8:00 hora Argentina (UTC-3)** y commitea los outputs
regenerados al repo. También se puede disparar manualmente desde la pestaña
Actions con `workflow_dispatch`.

## Fuente de deploys

`deploys.csv` con cabecera `fecha,titulo,descripcion`. El archivo se mantiene a mano por ahora porque el repo del CFER web todavía no está accesible vía GitLab API (pendiente de migración a la cuenta Enterprise de Comarb).

Cuando el repo esté disponible vía API, sumar lectura automática como fuente complementaria en `src/deploys.py`.

## Notas de la primera revisión (2026-05-15)

- Los números coinciden con la consola GA4 que vio Gustavo (abril/2026: 90.775 eventos / 13.479 usuarios / 6,73 ev/usuario).
- **`activeUsers == totalUsers`** en todos los meses del período — no hay diferencia que reportar.
- **Aclaración importante**: el pico de "17.000" en feb/2026 mencionado en la Weekly corresponde a **usuarios** (`activeUsers = 17.377`), **no a eventos** (los eventos fueron 138.455 ese mes). En el informe final dejar explícito para evitar confusión.
- La **ratio eventos/usuario cae** de ~12 (jun-oct 2025) a ~6-8 (nov 2025 en adelante). Compatible con la hipótesis de que el nuevo modal (deploy de nov/2025) bajó la fricción → más usuarios distintos lo usan, cada uno con menos clicks redundantes.
