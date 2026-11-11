"""Eventos de lugares chicos que releva GPT en una Google Sheet.

GPT busca espacios que no cubren las otras fuentes (Berisso, lugares que solo
publican en Instagram o en medios locales) y los carga en una planilla. Esta
fuente la lee como CSV y le aplica los mismos filtros que a la comunidad
(campos mínimos, fecha futura, Gran La Plata, anti-spam, tope por corrida).

La planilla es de lectura pública por link. Se puede apuntar a otra con la
variable MOVETE_PLANILLA_CSV.
"""
import os

import requests

from scrapers.comunidad import HEADERS, _parsear

# La planilla la carga GPT a pedido de Tres (no es pública para escribir),
# así que el tope anti-spam de la comunidad le queda corto.
MAX_PLANILLA = 200

CSV_URL = (os.environ.get("MOVETE_PLANILLA_CSV", "").strip()
           or "https://docs.google.com/spreadsheets/d/"
              "1ezRx_3Q5jwT4zF97l9vaRFzNvEGTcO-lwHVuzzlEHkQ/export?format=csv&gid=0")


def scrape() -> list:
    try:
        r = requests.get(CSV_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        eventos = _parsear(r.text, fuente="planilla", tope=MAX_PLANILLA)
    except requests.RequestException as e:
        print(f"  planilla: error descargando — {e}")
        return []
    print(f"  planilla: {len(eventos)} eventos")
    return eventos
