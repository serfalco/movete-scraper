# MoVeTe Scraper

Scraper automático de eventos culturales del Gran La Plata para [movete.info](https://movete.info).

## Cómo funciona
- Corre automáticamente **jueves 07:00** y **viernes 09:00** (hora Argentina) vía GitHub Actions.
- Cada archivo en `scrapers/` cubre una fuente. `main.py` junta todo, deduplica, filtra eventos futuros y los sube a WordPress (The Events Calendar) vía REST API.

## Fuentes
| Fuente | Archivo | Día |
|---|---|---|
| Livepass (Ópera, T. Argentino, Hipódromo, CCNU, Club RE, Atenas) | `scrapers/livepass.py` | Jue + Vie |
| Teatro Metro | `scrapers/teatro_metro.py` | Jue + Vie |
| Coliseo Podestá | `scrapers/coliseo.py` | Jue + Vie |
| Teatro Ópera | `scrapers/opera.py` | Jue + Vie |
| Eventbrite | `scrapers/eventbrite.py` | Jue + Vie |
| El Día (agenda del finde) | `scrapers/eldia.py` | Solo Vie |
| 0221 ¿Qué Hago? | `scrapers/_0221.py` | Solo Vie |

## Correr a mano
Pestaña **Actions** → MoVeTe Scraper → **Run workflow**. Tildá *dry run* para probar sin crear eventos.

## Secrets requeridos
- `WPUSER` — usuario de WordPress
- `WPAPPPASSWORD` — Application Password
