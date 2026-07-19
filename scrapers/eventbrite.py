"""Eventbrite — La Plata, datos desde JSON-LD (schema.org).

Se usa la búsqueda de /performances/ (lo cultural: teatro, música, stand up).
La de /events/ trae mucho evento fuera de foco (cursos, negocios), por eso no
se incluye. Eventbrite ahora envuelve los eventos en un ItemList JSON-LD, así
que hay que recorrerlo en profundidad (antes el scraper miraba solo el nivel
superior y por eso devolvía 0).
"""
import json

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, es_la_plata, es_futuro

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-AR,es;q=0.9',
}
URLS = [
    'https://www.eventbrite.com.ar/d/argentina--la-plata/performances/',
]


def _normalizar_iso(fecha_iso: str) -> str:
    if not fecha_iso:
        return ''
    f = fecha_iso.replace('T', ' ')[:19]
    if len(f) == 10:
        f += ' 21:00:00'
    return f


def _iter_events(data) -> list:
    """Recorre el JSON-LD y junta todos los @type=Event, aunque estén anidados
    dentro de un ItemList (itemListElement -> item) o de un @graph."""
    encontrados: list[dict] = []

    def es_event(tipo) -> bool:
        return tipo == 'Event' or (isinstance(tipo, list) and 'Event' in tipo)

    def walk(o) -> None:
        if isinstance(o, dict):
            if es_event(o.get('@type')):
                encontrados.append(o)
            for clave in ('itemListElement', '@graph', 'item'):
                if clave in o:
                    walk(o[clave])
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    return encontrados


def scrape() -> list:
    eventos = []
    vistos = set()
    for url in URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code != 200:
                print(f'  eventbrite: HTTP {r.status_code} en {url}')
                continue
        except requests.RequestException as e:
            print(f'  eventbrite: error {e}')
            continue

        soup = BeautifulSoup(r.text, 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
            except (json.JSONDecodeError, TypeError):
                continue
            for item in _iter_events(data):
                titulo = item.get('name', '')
                fecha = _normalizar_iso(item.get('startDate', ''))
                loc = item.get('location', {})
                lugar = loc.get('name', '') if isinstance(loc, dict) else str(loc)
                addr = loc.get('address', {}) if isinstance(loc, dict) else {}
                ciudad = addr.get('addressLocality', '') if isinstance(addr, dict) else ''
                calle = addr.get('streetAddress', '') if isinstance(addr, dict) else ''
                if not titulo or not fecha:
                    continue
                # La búsqueda de Eventbrite mezcla CABA y otras ciudades. Se
                # filtra por la ciudad (addressLocality), que viene limpia, para
                # quedarnos con el Gran La Plata (incluye City Bell, Gonnet, etc.).
                # No se usa el texto completo porque incluye la provincia
                # "Buenos Aires" y haría que el filtro descarte de más.
                if not es_la_plata(ciudad):
                    continue
                if not es_futuro(fecha):
                    continue
                clave = (titulo.lower().strip(), fecha[:10])
                if clave in vistos:
                    continue
                vistos.add(clave)
                eventos.append(evento(
                    titulo, fecha, lugar, direccion=calle,
                    url=item.get('url', ''), fuente='eventbrite'))
    print(f'  eventbrite: {len(eventos)} eventos')
    return eventos
