"""MoVeTe Scraper — orquestador principal.

Junta eventos de todas las fuentes, normaliza, deduplica, filtra futuros
y escribe un archivo estático `eventos.json` que consume movete-espectaculos.

Modelo estático: NO sube a WordPress. El JSON es la única salida.
"""
import json
import os
import sys
from collections import Counter
from datetime import date, datetime

from core.normalizar import deduplicar, es_futuro

from scrapers import (
    livepass, teatro_metro, coliseo, opera,
    eventbrite, eldia, _0221, genda, alternativa,
)

# Dónde se escribe el JSON. Configurable por env para CI/CD.
SALIDA = os.environ.get('SALIDA_JSON', 'eventos.json')


def main() -> int:
    print('======= MoVeTe Scraper =======')
    print(f'Fecha: {date.today().isoformat()}')

    es_viernes = date.today().weekday() == 4

    print('\n--- Scrapeando fuentes ---')
    todos = []
    fuentes = [genda, livepass, alternativa, teatro_metro, coliseo, opera, eventbrite]
    if es_viernes:
        fuentes += [eldia, _0221]

    conteo_fuente = {}
    for fuente in fuentes:
        try:
            res = fuente.scrape()
            todos.extend(res)
            conteo_fuente[fuente.__name__.split('.')[-1]] = len(res)
        except Exception as e:  # noqa: BLE001 — una fuente caída no frena el resto
            print(f'  ⚠️ {fuente.__name__}: falló — {e}')
            conteo_fuente[fuente.__name__.split('.')[-1]] = 0

    print(f'\nTotal bruto: {len(todos)}')

    # Filtrar futuros, deduplicar, ordenar por fecha ascendente
    eventos = deduplicar([e for e in todos if es_futuro(e.get('fecha', ''))])
    eventos = [e for e in eventos if e.get('titulo') and e.get('fecha')]
    eventos.sort(key=lambda e: e['fecha'])
    print(f'Futuros y únicos: {len(eventos)}')

    # Estructura de salida: metadata + eventos
    salida = {
        'generado': datetime.now().isoformat(timespec='seconds'),
        'total': len(eventos),
        'por_fuente': conteo_fuente,
        'por_categoria': dict(Counter(e['categoria'] for e in eventos)),
        'eventos': eventos,
    }

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print('\n======= RESULTADO =======')
    print(f'Escrito: {SALIDA} ({len(eventos)} eventos)')
    print(f'Por fuente: {conteo_fuente}')
    print(f'Por categoría: {salida["por_categoria"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
