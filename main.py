"""MoVeTe Scraper — orquestador principal.

Junta eventos de todas las fuentes, normaliza, deduplica, filtra futuros y
escribe un archivo estático `eventos.json` que consume `movete-espectaculos`.

Modelo estático: NO sube a WordPress. El JSON es la única salida.
"""

from __future__ import annotations

import json
import os
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

# Dónde se escribe el JSON. Configurable por env para CI/CD.
SALIDA = os.environ.get("SALIDA_JSON", "eventos.json")


def _scrapear_fuente(fuente) -> list[dict]:
    """Ejecuta una fuente sin dejar que una caída frene todo."""
    try:
        eventos = fuente.scrape()
        print(f"  ✓ {fuente.__name__.split('.')[-1]}: {len(eventos)} eventos")
        return eventos
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ {fuente.__name__}: falló — {exc}")
        return []


def main() -> int:
    print("======= MoVeTe Scraper =======")
    print(f"Fecha: {date.today().isoformat()}")

    # Fuentes base. El Día y 0221 se suman los viernes porque suelen publicar agenda de finde.
    es_viernes = date.today().weekday() == 4
    fuentes = [genda, livepass, alternativa, teatro_metro, coliseo, opera, eventbrite]
    if es_viernes:
        fuentes += [eldia, _0221]

    print("\n--- Scrapeando fuentes ---")
    todos: list[dict] = []
    conteo_fuente: dict[str, int] = {}

    for fuente in fuentes:
        nombre = fuente.__name__.split(".")[-1]
        eventos_fuente = _scrapear_fuente(fuente)
        todos.extend(eventos_fuente)
        conteo_fuente[nombre] = len(eventos_fuente)

    print(f"\nTotal bruto: {len(todos)}")

    eventos = deduplicar([e for e in todos if es_futuro(e.get("fecha", ""))])
    eventos = [e for e in eventos if e.get("titulo") and e.get("fecha")]
    eventos.sort(key=lambda e: e["fecha"])

    print(f"Futuros y únicos: {len(eventos)}")

    salida = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "total": len(eventos),
        "por_fuente": conteo_fuente,
        "por_categoria": dict(Counter(e.get("categoria", "otros") for e in eventos)),
        "eventos": eventos,
    }

    salida_path = Path(SALIDA)
    salida_path.parent.mkdir(parents=True, exist_ok=True)
    salida_path.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n======= RESULTADO =======")
    print(f"Escrito: {salida_path} ({len(eventos)} eventos)")
    print(f"Por fuente: {conteo_fuente}")
    print(f"Por categoría: {salida['por_categoria']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
