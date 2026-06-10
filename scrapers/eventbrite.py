"""Eventbrite — búsqueda La Plata, datos desde JSON-LD (schema.org/Event)."""
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
    'https://www.eventbrite.com.ar/d/argentina--la-plata/events/',
    'https://www.eventbrite.com.ar/d/argentina--la-plata/performances/',
]


def _normalizar_iso(fecha_iso: str) -> str:
    if not fecha_iso:
        return ''
    f = fecha_iso.replace('T', ' ')[:19]
    if len(f) == 10:
        f += ' 21:00:00'
    return f


def scrape() -> list:
    eventos = []
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
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('@graph', [data])
            else:
                continue
            for item in items:
                if not isinstance(item, dict) or item.get('@type') != 'Event':
                    continue
                titulo = item.get('name', '')
                fecha = _normalizar_iso(item.get('startDate', ''))
                loc = item.get('location', {})
                lugar = loc.get('name', '') if isinstance(loc, dict) else str(loc)
                addr = loc.get('address', {}) if isinstance(loc, dict) else {}
                ciudad = addr.get('addressLocality', '') if isinstance(addr, dict) else ''
                calle = addr.get('streetAddress', '') if isinstance(addr, dict) else ''
                if not titulo or not fecha:
                    continue
                if not es_la_plata(f'{titulo} {lugar} {ciudad} {calle}'):
                    continue
                if not es_futuro(fecha):
                    continue
                eventos.append(evento(
                    titulo, fecha, lugar, direccion=calle,
                    url=item.get('url', ''), fuente='eventbrite'))
    print(f'  eventbrite: {len(eventos)} eventos')
    return eventos
