"""El Día — agenda de espectáculos del viernes (formato 'Nombre.- A las HH en Lugar')."""
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
SECCION = 'https://www.eldia.com/seccion/espectaculos'

PATRON_EVENTO = re.compile(
    r'^(.{3,90}?)\.-\s*A las (\d{1,2})(?:[:.,](\d{2}))?\s*(?:hs\.?)?,?\s*en\s+(.{3,100}?)[.,]',
    re.I)


def _fechas_finde() -> dict:
    hoy = date.today()
    # El scraper corre el viernes: hoy=viernes
    dias_a_viernes = (4 - hoy.weekday()) % 7
    viernes = hoy + timedelta(days=dias_a_viernes) if hoy.weekday() != 4 else hoy
    return {
        'HOY': viernes, 'VIERNES': viernes,
        'MAÑANA': viernes + timedelta(days=1),
        'SÁBADO': viernes + timedelta(days=1), 'SABADO': viernes + timedelta(days=1),
        'DOMINGO': viernes + timedelta(days=2),
    }


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(SECCION, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f'  eldia: HTTP {r.status_code}')
            return []
    except requests.RequestException as e:
        print(f'  eldia: error {e}')
        return []

    m = re.search(r'href="(https://www\.eldia\.com/nota/[^"]*agenda-espectaculos[^"]*)"',
                  r.text)
    if not m:
        print('  eldia: nota de agenda no encontrada')
        return []

    try:
        nota = requests.get(m.group(1), headers=HEADERS, timeout=25)
    except requests.RequestException as e:
        print(f'  eldia: error nota {e}')
        return []

    soup = BeautifulSoup(nota.text, 'html.parser')
    texto = soup.get_text('\n')
    fechas = _fechas_finde()
    dia_actual = fechas['HOY']

    for linea in texto.split('\n'):
        linea = linea.strip()
        if not linea:
            continue
        # Cambio de día
        encabezado = re.match(r'^[■•\-\s]*([A-ZÁÉÍÓÚÑ]{3,10})\b', linea)
        if encabezado and encabezado.group(1) in fechas:
            dia_actual = fechas[encabezado.group(1)]
            continue
        # Evento
        m_ev = PATRON_EVENTO.match(linea)
        if m_ev:
            hora = f"{int(m_ev.group(2)):02d}:{m_ev.group(3) or '00'}"
            fecha = f'{dia_actual.isoformat()} {hora}:00'
            eventos.append(evento(
                m_ev.group(1), fecha, m_ev.group(4),
                url='', fuente='eldia'))

    print(f'  eldia: {len(eventos)} eventos')
    return eventos
