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
CACHE_DIR = os.environ.get("MOVETE_CACHE_DIR", "")


def _cache_fuente(nombre: str) -> str:
    return os.path.join(CACHE_DIR, f"{nombre}.json")


def _cargar_cache(nombre: str) -> list[dict]:
    if not CACHE_DIR:
        return []
    try:
        with open(_cache_fuente(nombre), encoding="utf-8") as f:
            data = json.load(f)
        return [ev for ev in data if isinstance(ev, dict) and es_futuro(ev.get("fecha", ""))]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _guardar_cache(nombre: str, eventos: list[dict]) -> None:
    if not CACHE_DIR or not eventos:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_fuente(nombre), "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f" [AVISO] {nombre}: no se pudo guardar respaldo - {e}")


def main() -> int:
    print("======= MoVeTe Scraper =======")
    print(f"Fecha: {date.today().isoformat()}")

    # El Dia y 0221 solo publican los viernes. Corren si es viernes o si el
    # workflow lo fuerza con FORZAR_PERIODISTICAS=1 (util para pruebas manuales).
    correr_periodisticas = (
        date.today().weekday() == 4
        or os.environ.get("FORZAR_PERIODISTICAS") == "1"
    )
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
    if correr_periodisticas:
        fuentes += [eldia, _0221]

    conteo_fuente: dict[str, int] = {}

    for fuente in fuentes:
        nombre = fuente.__name__.split(".")[-1]
        try:
            res = fuente.scrape()
            if not isinstance(res, list):
                print(f" [AVISO] {nombre}: devolvió {type(res).__name__}, se ignora")
                res = []
            if res:
                _guardar_cache(nombre, res)
            else:
                respaldo = _cargar_cache(nombre)
                if respaldo:
                    res = respaldo
                    print(f" [CACHE] {nombre}: se usan {len(res)} eventos del último respaldo válido")
            todos.extend(res)
            conteo_fuente[nombre] = len(res)
            print(f" [OK] {nombre}: {len(res)} eventos")
        except Exception as e:  # noqa: BLE001
            print(f" [AVISO] {nombre}: falló - {e}")
            res = _cargar_cache(nombre)
            if res:
                print(f" [CACHE] {nombre}: se usan {len(res)} eventos del último respaldo válido")
                todos.extend(res)
            conteo_fuente[nombre] = len(res)

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
