"""Alternativa Teatral — teatro independiente / alternativo del Gran La Plata.

Usa el endpoint JSON interno del sitio (get-json.php), el mismo que alimenta
la cartelera. Es JSONP con BOM, así que hay que limpiarlo antes de parsear.

Cada espectáculo trae uno o más lugares; cada lugar trae su 'zona' (ciudad) y
sus funciones con 'proxima_fecha'. Filtramos por zona del Gran La Plata y
tomamos la próxima función futura de cada obra.
"""
import json
import re
from datetime import date

import requests

from core.normalizar import detectar_categoria, evento

ENDPOINT = 'https://www.alternativateatral.com/get-json.php'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0',
    'Referer': 'https://www.alternativateatral.com.ar/cartelera.asp',
}

# Zonas (campo 'zona' del JSON) que consideramos Gran La Plata
ZONAS_LP = {
    'la plata', 'ensenada', 'berisso', 'city bell', 'gonnet',
    'villa elisa', 'tolosa', 'los hornos', 'ringuelet',
}

# Salas de La Plata cargadas con otra zona en Alternativa (id del lugar).
# 1140 = El Teatro Bar (calle 43 n° 632), figura como "Olivos".
SALAS_LP_FORZADAS = {'1140'}

# Caja del Gran La Plata (lat, lng). Muchas salas vienen con 0,0, así que
# las coordenadas solo suman salas; nunca descartan una que diga La Plata.
CAJA_LP = (-35.05, -34.80, -58.17, -57.80)


def _es_gran_la_plata(id_lugar, lugar: dict) -> bool:
    if lugar.get('zona', '').strip().lower() in ZONAS_LP:
        return True
    if str(id_lugar) in SALAS_LP_FORZADAS:
        return True
    try:
        lat, lng = float(lugar.get('lat')), float(lugar.get('lng'))
    except (TypeError, ValueError):
        return False
    lat_min, lat_max, lng_min, lng_max = CAJA_LP
    return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max


def _descargar() -> dict:
    """Descarga y parsea el JSONP de la cartelera."""
    r = requests.get(ENDPOINT, params={'t': 'novedades', 'r': 'cartelera'},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    cuerpo = r.text.lstrip('\ufeff')
    m = re.search(r'jsoncallback\((.*)\)\s*$', cuerpo, re.S)
    if not m:
        return {}
    return json.loads(m.group(1).lstrip('\ufeff'))


def scrape() -> list:
    eventos = []
    hoy = date.today().isoformat()

    try:
        data = _descargar()
    except (requests.RequestException, ValueError) as e:
        print(f'  alternativa: error descargando — {e}')
        return eventos

    espectaculos = data.get('espectaculos', {})

    for esp in espectaculos.values():
        titulo = esp.get('titulo', '').strip()
        if not titulo:
            continue
        url_ficha = esp.get('url', '')
        if url_ficha:
            url_ficha = 'https://www.alternativateatral.com.ar/' + url_ficha
        url_entradas = esp.get('url_entradas', '') or url_ficha
        imagen = (esp.get('imagen_ficha') or '').strip()
        if imagen and not imagen.startswith('http'):
            imagen = 'https://' + imagen

        for id_lugar, lugar in esp.get('lugares', {}).items():
            if not _es_gran_la_plata(id_lugar, lugar):
                continue

            sala = lugar.get('nombre', '').strip()
            direccion = lugar.get('direccion', '').strip()
            if direccion:
                direccion = f'{direccion}, La Plata'

            # Próxima función futura de cada sala.
            # 'proxima_fecha' ya viene como 'YYYY-MM-DD HH:MM'.
            mejor = None
            for func in lugar.get('funciones', {}).values():
                fecha = (func.get('proxima_fecha') or '').strip()
                if not fecha or fecha[:10] < hoy:
                    continue
                if mejor is None or fecha < mejor:
                    mejor = fecha

            if not mejor:
                continue

            # Normalizar a 'YYYY-MM-DD HH:MM:SS'
            if len(mejor) == 16:          # 'YYYY-MM-DD HH:MM'
                fecha_norm = f'{mejor}:00'
            elif len(mejor) == 10:        # solo fecha
                fecha_norm = f'{mejor} 21:00:00'
            else:
                fecha_norm = mejor

            eventos.append(evento(
                titulo,
                fecha_norm,
                sala or 'La Plata',
                categoria=detectar_categoria(titulo, default='teatro'),
                direccion=direccion,
                url=url_entradas,
                fuente='alternativa',
                imagen=imagen,
            ))

    print(f'  alternativa: {len(eventos)} eventos')
    return eventos
