"""MoVeTe Scraper — orquestador principal.

Junta eventos de todas las fuentes, normaliza, deduplica,
filtra futuros y los sube a WordPress (The Events Calendar).
"""
import os
import sys
from datetime import date

from core.normalizar import deduplicar, es_futuro
from core import wordpress

from scrapers import livepass, teatro_metro, coliseo, opera, eventbrite, eldia, _0221

DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'


def main() -> int:
    print('======= MoVeTe Scraper =======')
    print(f"Fecha: {date.today().isoformat()} | Modo: {'DRY RUN' if DRY_RUN else 'PRODUCCIÓN'}")

    if not DRY_RUN and not wordpress.verificar_conexion():
        print('Abortando: sin conexión a WordPress.')
        return 1

    es_viernes = date.today().weekday() == 4

    print('\n--- Scrapeando fuentes ---')
    todos = []
    fuentes = [livepass, teatro_metro, coliseo, opera, eventbrite]
    if es_viernes:
        fuentes += [eldia, _0221]

    for fuente in fuentes:
        try:
            todos.extend(fuente.scrape())
        except Exception as e:  # noqa: BLE001 — una fuente caída no frena el resto
            print(f'  ⚠️ {fuente.__name__}: falló — {e}')

    print(f'\nTotal bruto: {len(todos)}')
    eventos = deduplicar([e for e in todos if es_futuro(e.get('fecha', ''))])
    print(f'Futuros y únicos: {len(eventos)}')

    print('\n--- Subiendo a WordPress ---')
    nuevos = dupes = errores = 0
    for ev in eventos:
        if not ev['titulo'] or not ev['fecha']:
            continue
        if not DRY_RUN and wordpress.ya_existe(ev):
            dupes += 1
            continue
        if wordpress.crear_evento(ev, dry_run=DRY_RUN):
            nuevos += 1
        else:
            errores += 1

    print('\n======= RESULTADO =======')
    print(f'Nuevos: {nuevos} | Duplicados: {dupes} | Errores: {errores}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
