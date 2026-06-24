"""MoVeTe Scraper — orquestador principal.

Junta eventos de todas las fuentes, normaliza, deduplica, filtra futuros
y escribe un archivo estático eventos.json que consume movete-espectaculos.

Modelo estático:
- NO sube a WordPress.
- NO usa FTP.
- El JSON es la única salida.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date, datetime

from core.normalizar import deduplicar, es_futuro

from scrapers import (
    livepass,
    teatro_metro,
    coliseo,
    opera,
    eventbrite,
    eldia,
    _0221,
    genda,
    alternativa,
)

# Dónde se escribe el JSON. Configurable por env para CI/CD.
SALIDA = os.environ.get("SALIDA_JSON", "eventos.json")


def main() -> int:
    print("======= MoVeTe Scraper =======")
    print(f"Fecha: {date.today().isoformat()}")

    es_viernes = date.today().weekday() == 4
    print("\n--- Scrapeando fuentes ---")

    todos: list[dict] = []

    # Fuentes base. Una fuente caída no debe frenar al resto.
    fuentes = [
        genda,
        livepass,
        alternativa,
        teatro_metro,
        coliseo,
        opera,
        eventbrite,
    ]

    # Fuentes más periodísticas: se pueden correr menos seguido.
    if es_viernes:
        fuentes += [eldia, _0221]

    conteo_fuente: dict[str, int] = {}

    for fuente in fuentes:
        nombre = fuente.__name__.split(".")[-1]
        try:
            res = fuente.scrape()
            if not isinstance(res, list):
                print(f" ⚠️ {nombre}: devolvió {type(res).__name__}, se ignora")
                res = []
            todos.extend(res)
            conteo_fuente[nombre] = len(res)
            print(f" ✅ {nombre}: {len(res)} eventos")
        except Exception as e:  # noqa: BLE001
            print(f" ⚠️ {nombre}: falló — {e}")
            conteo_fuente[nombre] = 0

    print(f"\nTotal bruto: {len(todos)}")

    eventos = []
    for evento in todos:
        if not isinstance(evento, dict):
            continue
        if not es_futuro(evento.get("fecha", "")):
            continue
        if not evento.get("titulo") or not evento.get("fecha"):
            continue
        eventos.append(evento)

    eventos = deduplicar(eventos)
    eventos.sort(key=lambda e: e.get("fecha", ""))

    print(f"Futuros y únicos: {len(eventos)}")

    salida = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "total": len(eventos),
        "por_fuente": conteo_fuente,
        "por_categoria": dict(Counter(e.get("categoria", "otros") for e in eventos)),
        "eventos": eventos,
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("\n======= RESULTADO =======")
    print(f"Escrito: {SALIDA} ({len(eventos)} eventos)")
    print(f"Por fuente: {conteo_fuente}")
    print(f'Por categoría: {salida["por_categoria"]}')

    return 0


if __name__ == "__main__":
    sys.exit(main())
