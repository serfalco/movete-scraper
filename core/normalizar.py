"""Normalización de eventos: fechas, categorías, deduplicación, filtro geográfico."""
from datetime import datetime, date, timedelta
import hashlib
import re
import unicodedata

LOCALIDADES = [
    'la plata', 'laplata', 'ensenada', 'berisso', 'city bell',
    'gonnet', 'villa elisa', 'los hornos', 'tolosa', 'ringuelet',
    'brandsen', 'magdalena', 'punta indio',
]

EXCLUIR = [
    'buenos aires', 'caba', 'cordoba', 'rosario', 'mendoza',
    'quilmes', 'lanus', 'banfield', 'avellaneda', 'wilde',
    'san miguel', 'monte grande', 'ituzaingo', 'villa ballester',
    'palermo', 'belgrano', 'san telmo', 'recoleta',
]

MESES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

CATEGORIAS = {
    'stand up': 'stand-up', 'standup': 'stand-up', 'stand-up': 'stand-up',
    'comedia': 'stand-up', 'humor': 'stand-up',
    'teatro': 'teatro', 'obra': 'teatro', 'dramaturg': 'teatro',
    'impro': 'impro', 'improvisac': 'impro',
    'danza': 'danza', 'ballet': 'danza', 'folklore': 'danza',
    'musica': 'musica', 'recital': 'musica', 'concierto': 'musica',
    'jazz': 'musica', 'tango': 'musica', 'rock': 'musica', 'cumbia': 'musica',
    'orquesta': 'musica', 'banda': 'musica', 'show': 'musica',
    'cine': 'cine', 'film': 'cine', 'pelicula': 'cine',
    'infantil': 'infantil', 'ninos': 'infantil', 'familiar': 'infantil', 'titeres': 'infantil',
    'taller': 'taller', 'workshop': 'taller', 'curso': 'taller', 'seminario': 'taller',
    'expo': 'a-plasticas', 'muestra': 'a-plasticas', 'pintura': 'a-plasticas',
    'fotografia': 'a-plasticas', 'escultura': 'a-plasticas',
}


def _sin_acentos(texto: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def es_la_plata(texto: str) -> bool:
    """True si el texto refiere al Gran La Plata y no a otra ciudad."""
    t = _sin_acentos(texto.lower())
    for x in EXCLUIR:
        if x in t:
            return False
    for loc in LOCALIDADES:
        if loc in t:
            return True
    return False


def detectar_categoria(texto: str, default: str = 'teatro') -> str:
    t = _sin_acentos(texto.lower())
    for kw, slug in CATEGORIAS.items():
        if kw in t:
            return slug
    return default


def ajustar_anio(mes: int, dia: int, hora: str = '21:00') -> str:
    """Arma fecha YYYY-MM-DD HH:MM:SS asumiendo el próximo año si el mes ya pasó."""
    hoy = date.today()
    anio = hoy.year
    try:
        candidata = date(anio, mes, dia)
    except ValueError:
        return ''
    if candidata < hoy - timedelta(days=2):
        candidata = date(anio + 1, mes, dia)
    return f'{candidata.isoformat()} {hora}:00'


def es_futuro(fecha: str) -> bool:
    if not fecha:
        return False
    try:
        dt = datetime.strptime(fecha[:10], '%Y-%m-%d').date()
        return dt >= date.today()
    except ValueError:
        return False


def limpiar_titulo(titulo: str) -> str:
    t = re.sub(r'\s+', ' ', titulo).strip()
    t = t.strip('"\'""''·-– ')
    return t[:120]


def deduplicar(eventos: list) -> list:
    vistos = set()
    resultado = []
    for ev in eventos:
        titulo_norm = re.sub(r'[^a-z0-9]', '', _sin_acentos(ev['titulo'].lower()))
        clave = hashlib.md5((titulo_norm + ev['fecha'][:10]).encode()).hexdigest()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(ev)
    return resultado


def evento(titulo: str, fecha: str, lugar: str, categoria: str = '',
           direccion: str = '', url: str = '', fuente: str = '') -> dict:
    """Constructor estándar de evento."""
    titulo = limpiar_titulo(titulo)
    return {
        'titulo': titulo,
        'fecha': fecha,
        'lugar': lugar.strip()[:100],
        'direccion': direccion.strip()[:150],
        'categoria': categoria or detectar_categoria(titulo),
        'url': url,
        'fuente': fuente,
    }
