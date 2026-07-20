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

        for lugar in esp.get('lugares', {}).values():
            if lugar.get('zona', '').strip().lower() not in ZONAS_LP:
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
