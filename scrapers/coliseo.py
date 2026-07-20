"""Teatro Coliseo Podestá — cartelera oficial municipal (Drupal).

El listado /cartelera agrupa por mes pero no muestra el día exacto: la fecha
(y puede haber varias funciones) está en la ficha de cada actividad, en un
Event JSON-LD. Se recorren las fichas para sacar fecha exacta + imagen, así se
levanta toda la agenda (todos los meses), no solo lo del mes en curso.
"""
import json
import re
import time

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, es_futuro, evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
SITIO = 'https://coliseopodesta.laplata.gob.ar'
URL = SITIO + '/cartelera'
DIRECCION = 'Calle 10 entre 46 y 47, La Plata'
MAX_FICHAS = 150  # tope defensivo

# El segmento de la URL (/actividad/<seg>/...) trae la categoría, pero con
# nombres compuestos ('comedia-dramatica', 'infantiles', 'stand-humoristico').
# Se mapea por palabra clave, en orden (la primera que aparece manda).
CAT_KEYWORDS = [
    ('stand', 'stand-up'), ('infantil', 'infantil'), ('danza', 'danza'),
    ('recital', 'musica'), ('tango', 'musica'), ('musica', 'musica'),
    ('opera', 'musica'), ('humor', 'humor'), ('comedia', 'teatro'),
    ('drama', 'teatro'), ('teatro', 'teatro'),
]


def _categoria_de_seg(seg: str) -> str:
    for kw, slug in CAT_KEYWORDS:
        if kw in seg:
            return slug
    return ''


def _fetch(url: str, intentos: int = 3):
    for i in range(intentos):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        if i < intentos - 1:
            time.sleep(4)
    return None


def _actividades(soup: BeautifulSoup) -> dict:
    """href -> {img, categoria} de cada actividad del listado (sin duplicar)."""
    items = {}
    for a in soup.find_all('a', href=re.compile(r'/actividad/')):
        href = a.get('href', '')
        if not href or href in items:
            continue
        img = a.find('img')
        img_src = (img.get('src') or img.get('data-src') or '').strip() if img else ''
        seg = href.split('/actividad/')[-1].split('/')[0].lower()
        items[href] = {'img': img_src, 'categoria': _categoria_de_seg(seg)}
    return items


def _evento_jsonld(html: str):
    """Devuelve (nombre, [startDates]) del Event JSON-LD de la ficha."""
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(s.get_text())
        except (ValueError, TypeError):
            continue
        for node in data.get('@graph', [data]) if isinstance(data, dict) else []:
            if not isinstance(node, dict):
                continue
            if node.get('@type') in ('Event', 'TheaterEvent') or 'startDate' in node:
                sd = node.get('startDate')
                fechas = sd if isinstance(sd, list) else [sd] if sd else []
                return node.get('name', '').strip(), [str(f) for f in fechas]
    return '', []


def scrape() -> list:
    r = _fetch(URL)
    if not r:
        print('  coliseo: cartelera inaccesible')
        return []

    items = _actividades(BeautifulSoup(r.text, 'html.parser'))
    eventos = []
    for href, meta in list(items.items())[:MAX_FICHAS]:
        url_full = href if href.startswith('http') else SITIO + href
        d = _fetch(url_full, intentos=2)
        if not d:
            continue
        nombre, fechas = _evento_jsonld(d.text)
        if not nombre:
            continue
        categoria = meta['categoria'] or detectar_categoria(nombre)
        for sd in fechas:
            fecha = sd.replace('T', ' ')[:19]
            if len(fecha) == 10:
                fecha += ' 20:00:00'
            if not es_futuro(fecha):
                continue
            eventos.append(evento(
                nombre, fecha, 'Teatro Coliseo Podestá',
                categoria=categoria, direccion=DIRECCION,
                url=url_full, fuente='coliseo', imagen=meta['img'],
            ))
        time.sleep(0.3)

    # Dedup por título + día (una obra puede aparecer varias veces en el listado).
    vistos, unicos = set(), []
    for ev in eventos:
        k = ev['titulo'].lower() + ev['fecha'][:10]
        if k not in vistos:
            vistos.add(k)
            unicos.append(ev)
    print(f'  coliseo: {len(unicos)} eventos en {len(items)} actividades')
    return unicos
