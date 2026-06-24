# MoVeTe Scraper

Scraper automático de eventos culturales del Gran La Plata para [movete.info](https://movete.info).

## Cómo funciona

- Corre por GitHub Actions o manualmente.
- Cada archivo en `scrapers/` cubre una fuente.
- `main.py` junta todo, deduplica, filtra eventos futuros y escribe `eventos.json`.
- No publica en WordPress.
- No usa FTP.

## Salida

Archivo principal:

```txt
eventos.json
```

También se puede configurar por variable de entorno:

```txt
SALIDA_JSON=../Movete-info/data/eventos.json
```

## Correr local

```bash
pip install -r requirements.txt
python main.py
```

## Secrets requeridos

Ninguno por ahora.
