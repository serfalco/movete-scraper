# movete-scraper

Scraper de eventos para MoVeTe.

## Rol del repo

Este repo obtiene, normaliza, deduplica y filtra eventos futuros.

La salida oficial es:

```bash
eventos.json
```

## Importante

Este repo ya no publica en WordPress.

No usa:

- WordPress
- FTP
- Hostinger
- PHP

## Uso local

```bash
pip install -r requirements.txt
python main.py --output eventos.json
```

Dry run:

```bash
python main.py --dry-run
```

## Uso en GitHub Actions

El workflow corre los jueves y deja `eventos.json` como artefacto.

El workflow final del proyecto vive en `Movete-info`, que es el repo publicado por Cloudflare Pages.
