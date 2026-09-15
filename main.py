"""MoVeTe Scraper — orquestador principal.

Junta eventos de todas las fuentes, normaliza, deduplica, filtra futuros
y escribe un archivo estático eventos.json que consume movete-espectaculos.

Modelo estático:
- NO sube a WordPress.
- NO usa FTP.
- El JSON es la única salida.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date, datetime

from core.normalizar import deduplicar, es_futuro

from scrapers import (
    livepass,
    teatro_metro,
    coliseo,
    opera,
    eventbrite,
    eldia,
    _0221,
    genda,
    alternativa,
    comunidad,
    plateauno,
    passline,
    teatrobar,
)

# Dónde se escribe el JSON. Configurable por env para CI/CD.
SALIDA = os.environ.get("SALIDA_JSON", "eventos.json")
CACHE_DIR = os.environ.get("MOVETE_CACHE_DIR", "")

# Fuentes troncales: las que sostienen el grueso de la cartelera. Si una de
# estas no scrapea en vivo, la edición sale a medias aunque el respaldo la
# tape. En las corridas del 27/08 y 03/09 de 2026 genda dio 0 dos semanas
# seguidas y nadie se enteró: el ::warning:: queda en la pestaña Actions, la
# corrida termina en verde y GitHub solo manda mail cuando algo FALLA.
FUENTES_TRONCALES = ("genda", "livepass", "alternativa")

# Archivo de alerta. main.py NO corta la corrida (si cortara, no se publicaría
# la edición): deja el aviso acá y el workflow, ya publicado el sitio, falla
# en el último paso para que salga el mail.
ALERTA = os.environ.get("MOVETE_ALERTA", "_alerta.txt")


def _cache_fuente(nombre: str) -> str:
    return os.path.join(CACHE_DIR, f"{nombre}.json")


def _cargar_cache(nombre: str) -> tuple[list[dict], str]:
    """Devuelve (eventos futuros del respaldo, fecha del evento mas nuevo).

    La fecha sirve para distinguir un respaldo util de uno vencido: si la fuente
    cae y nadie mira, el respaldo se va vaciando solo y la cartelera se achica
    en silencio. Eso fue exactamente lo que paso con genda en agosto de 2026.
    """
    if not CACHE_DIR:
        return [], ""
    try:
        with open(_cache_fuente(nombre), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return [], ""
    if not isinstance(data, list):
        return [], ""
    fechas = [str(ev.get("fecha", "")) for ev in data if isinstance(ev, dict)]
    mas_nueva = max(fechas)[:10] if fechas else ""
    futuros = [ev for ev in data if isinstance(ev, dict) and es_futuro(ev.get("fecha", ""))]
    return futuros, mas_nueva


def _guardar_cache(nombre: str, eventos: list[dict]) -> None:
    if not CACHE_DIR or not eventos:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_fuente(nombre), "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f" [AVISO] {nombre}: no se pudo guardar respaldo - {e}")


SALUD_PATH = "_salud.json"
# Si una corrida trae menos de este porcentaje de la anterior, algo se rompio.
UMBRAL_CAIDA = 0.65


def _leer_salud() -> dict:
    if not CACHE_DIR:
        return {}
    try:
        with open(os.path.join(CACHE_DIR, SALUD_PATH), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _guardar_salud(total: int, por_fuente: dict[str, int]) -> None:
    if not CACHE_DIR:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, SALUD_PATH), "w", encoding="utf-8") as f:
            json.dump(
                {"fecha": date.today().isoformat(), "total": total, "por_fuente": por_fuente},
                f, ensure_ascii=False, indent=2,
            )
    except OSError as e:
        print(f" [AVISO] no se pudo guardar {SALUD_PATH} - {e}")


def main() -> int:
    print("======= MoVeTe Scraper =======")
    print(f"Fecha: {date.today().isoformat()}")

    # El Dia y 0221 solo publican los viernes. Corren si es viernes o si el
    # workflow lo fuerza con FORZAR_PERIODISTICAS=1 (util para pruebas manuales).
    correr_periodisticas = (
        date.today().weekday() == 4
        or os.environ.get("FORZAR_PERIODISTICAS") == "1"
    )
    print("\n--- Scrapeando fuentes ---")

    todos: list[dict] = []

    # Fuentes base. Una fuente caída no debe frenar al resto.
    fuentes = [
        genda,
        livepass,
        alternativa,
        teatro_metro,
        coliseo,
        opera,
        eventbrite,
        plateauno,
        passline,
        teatrobar,
    ]

    # Eventos cargados por la comunidad: solo si hay planilla configurada.
    if os.environ.get("MOVETE_EVENTOS_CSV", "").strip():
        fuentes.append(comunidad)

    # Fuentes más periodísticas: se pueden correr menos seguido.
    if correr_periodisticas:
        fuentes += [eldia, _0221]

    conteo_fuente: dict[str, int] = {}
    # ok = la fuente respondio con eventos | cache = se uso el respaldo |
    # vencida = la fuente no trajo nada y el respaldo ya no tiene futuros
    estado_fuente: dict[str, str] = {}

    def _usar_respaldo(nombre: str) -> list[dict]:
        respaldo, mas_nueva = _cargar_cache(nombre)
        if respaldo:
            estado_fuente[nombre] = "cache"
            print(f" [CACHE] {nombre}: se usan {len(respaldo)} eventos del último respaldo "
                  f"(el más nuevo es del {mas_nueva})")
            return respaldo
        estado_fuente[nombre] = "vencida"
        if mas_nueva:
            print(f" [VENCIDA] {nombre}: el respaldo existe pero su último evento es del "
                  f"{mas_nueva}; ya no aporta nada")
        return []

    for fuente in fuentes:
        nombre = fuente.__name__.split(".")[-1]
        try:
            res = fuente.scrape()
            if not isinstance(res, list):
                print(f" [AVISO] {nombre}: devolvió {type(res).__name__}, se ignora")
                res = []
            if res:
                estado_fuente[nombre] = "ok"
                _guardar_cache(nombre, res)
            else:
                res = _usar_respaldo(nombre)
            todos.extend(res)
            conteo_fuente[nombre] = len(res)
            print(f" [OK] {nombre}: {len(res)} eventos")
        except Exception as e:  # noqa: BLE001
            print(f" [AVISO] {nombre}: falló - {e}")
            res = _usar_respaldo(nombre)
            todos.extend(res)
            conteo_fuente[nombre] = len(res)

    print(f"\nTotal bruto: {len(todos)}")

    eventos = []
    for evento in todos:
        if not isinstance(evento, dict):
            continue
        if not es_futuro(evento.get("fecha", "")):
            continue
        if not evento.get("titulo") or not evento.get("fecha"):
            continue
        eventos.append(evento)

    eventos = deduplicar(eventos)
    eventos.sort(key=lambda e: e.get("fecha", ""))

    print(f"Futuros y únicos: {len(eventos)}")

    salida = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "total": len(eventos),
        "por_fuente": conteo_fuente,
        "por_categoria": dict(Counter(e.get("categoria", "otros") for e in eventos)),
        "eventos": eventos,
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("\n======= RESULTADO =======")
    print(f"Escrito: {SALIDA} ({len(eventos)} eventos)")
    print(f"Por fuente: {conteo_fuente}")
    print(f'Por categoría: {salida["por_categoria"]}')

    # ---- Salud de la corrida -------------------------------------------
    # El modo de falla que importa no es que una fuente se caiga: es que se
    # caiga y el respaldo lo tape hasta vaciarse. Por eso se avisa en tres
    # niveles y se compara el total contra la corrida anterior.
    print("\n--- Salud de fuentes ---")
    etiquetas = {"ok": "OK", "cache": "RESPALDO", "vencida": "SIN DATOS"}
    for nombre, cantidad in conteo_fuente.items():
        estado = estado_fuente.get(nombre, "vencida")
        print(f" {nombre:14} {cantidad:4} eventos   {etiquetas[estado]}")

    vencidas = [n for n, e in estado_fuente.items() if e == "vencida"]
    con_respaldo = [n for n, e in estado_fuente.items() if e == "cache"]

    if vencidas:
        print(f"::warning::Fuentes sin eventos ni respaldo válido (revisar scraper): "
              f"{', '.join(vencidas)}")
    if con_respaldo:
        print(f"::warning::Fuentes que hoy dependen del respaldo (se van a vaciar solas "
              f"si no se arreglan): {', '.join(con_respaldo)}")

    # ---- Alertas que tienen que salir del repo --------------------------
    alertas: list[str] = []

    troncales_caidas = [n for n in FUENTES_TRONCALES
                        if estado_fuente.get(n, "vencida") != "ok"]
    if troncales_caidas:
        como = {"cache": "usando respaldo", "vencida": "sin datos"}
        detalle = ", ".join(
            f"{n} ({conteo_fuente.get(n, 0)} eventos, "
            f"{como.get(estado_fuente.get(n), 'sin datos')})"
            for n in troncales_caidas)
        alertas.append(f"Fuente troncal sin scrapear en vivo: {detalle}")

    salud_previa = _leer_salud()
    total_previo = int(salud_previa.get("total") or 0)
    if total_previo and len(eventos) < total_previo * UMBRAL_CAIDA:
        caida = 100 - round(len(eventos) / total_previo * 100)
        msg = (f"La cartelera cayó {caida}% respecto de la corrida del "
               f"{salud_previa.get('fecha', '?')} ({total_previo} → {len(eventos)} eventos)")
        print(f"::warning::{msg}")
        alertas.append(msg)

    _guardar_salud(len(eventos), conteo_fuente)

    if alertas:
        texto = ("La cartelera de MoVeTe salió incompleta:\n\n"
                 + "\n".join(f"  - {a}" for a in alertas)
                 + f"\n\nTotal publicado: {len(eventos)} eventos."
                 + "\nPor fuente: "
                 + ", ".join(f"{n}={c}" for n, c in conteo_fuente.items())
                 + "\n")
        try:
            with open(ALERTA, "w", encoding="utf-8") as f:
                f.write(texto)
            print(f"\n[ALERTA] escrita en {ALERTA}; el workflow va a fallar "
                  f"al final para que llegue el mail.")
        except OSError as e:
            print(f" [AVISO] no se pudo escribir {ALERTA} - {e}")
    else:
        # Si quedó una alerta de la corrida anterior en el runner, se limpia.
        try:
            os.remove(ALERTA)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
