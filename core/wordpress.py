"""Conexión con WordPress: crea eventos vía The Events Calendar REST API."""
import os
from datetime import datetime, timedelta

import requests

WP_URL = os.environ.get('WP_URL', 'https://movete.info').rstrip('/')
AUTH = (os.environ.get('WP_USER', ''), os.environ.get('WP_APP_PASSWORD', ''))
TEC_EVENTS = f'{WP_URL}/wp-json/tribe/events/v1/events'
TEC_CATS = f'{WP_URL}/wp-json/tribe/events/v1/categories'
TEC_VENUES = f'{WP_URL}/wp-json/tribe/events/v1/venues'

_cat_cache: dict = {}
_venue_cache: dict = {}

HEADERS = {'User-Agent': 'MoVeTe-Scraper/1.0 (+https://movete.info)'}


def verificar_conexion() -> bool:
    """Chequea que la API responda y la autenticación funcione."""
    try:
        r = requests.get(f'{WP_URL}/wp-json/wp/v2/users/me',
                         auth=AUTH, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            print(f"✅ Autenticado como: {r.json().get('name', '?')}")
            return True
        print(f'❌ Auth falló: HTTP {r.status_code} — {r.text[:200]}')
        return False
    except requests.RequestException as e:
        print(f'❌ Error de conexión: {e}')
        return False


def _categoria_id(slug: str):
    if slug in _cat_cache:
        return _cat_cache[slug]
    try:
        r = requests.get(TEC_CATS, params={'search': slug},
                         auth=AUTH, headers=HEADERS, timeout=20)
        data = r.json() if r.status_code == 200 else {}
        for cat in data.get('categories', []):
            if cat.get('slug') == slug:
                _cat_cache[slug] = cat['id']
                return cat['id']
    except requests.RequestException:
        pass
    _cat_cache[slug] = None
    return None


def _venue_id(nombre: str, direccion: str):
    if not nombre:
        return None
    if nombre in _venue_cache:
        return _venue_cache[nombre]
    try:
        r = requests.get(TEC_VENUES, params={'search': nombre, 'per_page': 5},
                         auth=AUTH, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            for v in r.json().get('venues', []):
                if v.get('venue', '').lower() == nombre.lower():
                    _venue_cache[nombre] = v['id']
                    return v['id']
        # Crear venue nuevo
        r = requests.post(TEC_VENUES, auth=AUTH, headers=HEADERS, timeout=20, json={
            'venue': nombre,
            'address': direccion,
            'city': 'La Plata',
            'country': 'Argentina',
        })
        if r.status_code in (200, 201):
            vid = r.json().get('id')
            _venue_cache[nombre] = vid
            return vid
    except requests.RequestException:
        pass
    _venue_cache[nombre] = None
    return None


def ya_existe(ev: dict) -> bool:
    try:
        r = requests.get(TEC_EVENTS, auth=AUTH, headers=HEADERS, timeout=20, params={
            'search': ev['titulo'][:50],
            'start_date': ev['fecha'][:10],
            'per_page': 5,
        })
        if r.status_code != 200:
            return False
        for existente in r.json().get('events', []):
            if existente.get('title', '').strip().lower() == ev['titulo'].strip().lower():
                return True
        return False
    except requests.RequestException:
        return False


def crear_evento(ev: dict, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"  [DRY] {ev['fecha'][:16]} | {ev['titulo']} @ {ev['lugar']} [{ev['categoria']}] ({ev['fuente']})")
        return True

    inicio = datetime.strptime(ev['fecha'], '%Y-%m-%d %H:%M:%S')
    fin = inicio + timedelta(hours=2)
    cat_id = _categoria_id(ev['categoria'])
    venue_id = _venue_id(ev['lugar'], ev.get('direccion', ''))

 payload = {
        'title': ev['titulo'],
        'start_date': ev['fecha'],
        'end_date': fin.strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'publish',
    }
    if ev.get('url'):
        payload['description'] = f"Fuente: {ev['url']}"
    if cat_id:
        payload['categories'] = [cat_id]
    if venue_id:
        payload['venue'] = venue_id

    try:
        r = requests.post(TEC_EVENTS, auth=AUTH, headers=HEADERS,
                          timeout=30, json=payload)
        if r.status_code in (200, 201):
            print(f"  ✓ {ev['titulo']} ({ev['fecha'][:10]}) ID:{r.json().get('id')}")
            return True
        print(f"  ✗ {ev['titulo']} — HTTP {r.status_code}: {r.text[:150]}")
        return False
    except requests.RequestException as e:
        print(f"  ✗ {ev['titulo']} — {e}")
        return False
