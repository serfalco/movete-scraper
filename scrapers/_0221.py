"""0221.com.ar — agenda del finde (formato '## Sábado 2' + 'HH - Nombre  Lugar')."""
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
LISTADO = 'https://www.0221.com.ar/que-hago'

PATRON_EVENTO = re.compile(
    r'^(\d{1,2})(?:[:.,](\d{2}))?\s*[-–]\s*(.{4,90}?)\s{2,}(.{3,100})$')


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(LISTADO, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f'  0221: HTTP {r.status_code}')
            return []
    except requests.RequestException as e:
        print(f'  0221: error {e}')
        return []

    m = re.search(
        r'href="(https://www\.0221\.com\.ar/que-hago/[^"]*(?:agenda|fin-semana|finde)[^"]*)"',
        r.text)
    if not m:
        print('  0221: nota de agenda no encontrada')
        return []

    try:
        nota = requests.get(m.group(1), headers=HEADERS, timeout=25)
    except requests.RequestException as e:
        print(f'  0221: error nota {e}')
        return []

    soup = BeautifulSoup(nota.text, 'html.parser')
    texto = soup.get_text('\n')

    hoy = date.today()
    dias_a_sabado = (5 - hoy.weekday()) % 7
    sabado = hoy + timedelta(days=dias_a_sabado)
    domingo = sabado + timedelta(days=1)
    dia_actual = sabado

    for linea in texto.split('\n'):
        linea = linea.strip()
        if not linea:
            continue
        if re.match(r'^s[áa]bado\b', linea, re.I):
            dia_actual = sabado
            continue
        if re.match(r'^domingo\b', linea, re.I):
            dia_actual = domingo
            continue
        if re.match(r'^viernes\b', linea, re.I):
            dia_actual = hoy
            continue
        m_ev = PATRON_EVENTO.match(linea)
        if m_ev:
            hora = f"{int(m_ev.group(1)):02d}:{m_ev.group(2) or '00'}"
            fecha = f'{dia_actual.isoformat()} {hora}:00'
            eventos.append(evento(
                m_ev.group(3), fecha, m_ev.group(4),
                url='', fuente='0221'))

    print(f'  0221: {len(eventos)} eventos')
    return eventos
