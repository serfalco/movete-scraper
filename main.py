"""MoVeTe Scraper.

Orquestador principal: junta eventos de todas las fuentes, normaliza,
deduplica, filtra futuros y escribe un JSON estático.

Modelo actual:
- NO sube a WordPress.
- NO usa FTP.
- La única salida oficial es eventos.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from core.normalizar import deduplicar, es_futuro
from scrapers import (
    _0221,
    alternativa,
    coliseo,
    eldia,
    eventbrite,
    genda,
    livepass,
    opera,
    teatro_metro,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera eventos.json para MoVeTe")
    parser.add_argument(
        "--output",
        default="eventos.json",
        help="Ruta de salida del JSON. Default: eventos.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Corre scrapers y muestra resumen, pero no escribe archivo.",
    )
    return parser.parse_args()


def fuentes_para_hoy(hoy: date):
    """Fuentes activas.

    El Día y 0221 se dejan como refuerzo de viernes, como en la demo original.
    La edición fuerte de MoVeTe corre jueves.
    """
    fuentes = [genda, livepass, alternativa, teatro_metro, coliseo, opera, eventbrite]
    es_viernes = hoy.weekday() == 4
    if es_viernes:
        fuentes += [eldia, _0221]
    return fuentes


def scrape_all(hoy: date) -> tuple[list[dict], dict[str, int]]:
    todos: list[dict] = []
    conteo_fuente: dict[str, int] = {}

    for fuente in fuentes_para_hoy(hoy):
        nombre = fuente.__name__.split(".")[-1]
        try:
            res = fuente.scrape()
            if not isinstance(res, list):
                raise TypeError(f"{nombre}.scrape() no devolvió una lista")
            todos.extend(res)
            conteo_fuente[nombre] = len(res)
            print(f"✓ {nombre}: {len(res)} eventos")
        except Exception as e:  # noqa: BLE001: una fuente caída no frena el resto
            print(f"⚠️ {nombre}: falló — {e}")
            conteo_fuente[nombre] = 0

    return todos, conteo_fuente


def construir_salida(todos: list[dict], conteo_fuente: dict[str, int]) -> dict:
    eventos = [e for e in todos if es_futuro(e.get("fecha", ""))]
    eventos = deduplicar(eventos)
    eventos = [e for e in eventos if e.get("titulo") and e.get("fecha")]
    eventos.sort(key=lambda e: e["fecha"])

    return {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "total": len(eventos),
        "por_fuente": conteo_fuente,
        "por_categoria": dict(Counter(e.get("categoria", "otros") for e in eventos)),
        "eventos": eventos,
    }


def main() -> int:
    args = parse_args()
    hoy = date.today()

    print("======= MoVeTe Scraper =======")
    print(f"Fecha: {hoy.isoformat()}")
    print("\n--- Scrapeando fuentes ---")

    todos, conteo_fuente = scrape_all(hoy)
    salida = construir_salida(todos, conteo_fuente)

    print("\n======= RESULTADO =======")
    print(f"Total bruto: {len(todos)}")
    print(f"Futuros y únicos: {salida['total']}")
    print(f"Por fuente: {conteo_fuente}")
    print(f"Por categoría: {salida['por_categoria']}")

    if args.dry_run:
        print("\nDry run activo: no se escribe archivo.")
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEscrito: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
