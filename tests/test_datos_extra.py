"""Precio, disponibilidad y elenco del JSON-LD de las fuentes (para Google)."""
import json
import unittest

from core.normalizar import deduplicar, evento
from core.sitemap import datos_extra, evento_jsonld


def pagina(obj):
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


TEATROCERCA = {"@context": "https://schema.org", "@graph": [{
    "@type": "TheaterEvent", "name": "¡Actúen!",
    "startDate": "2026-11-21T21:00:00-03:00",
    "location": {"@type": "Place", "name": "Teatro Abierto",
                 "address": {"streetAddress": "Calle 2 N° 1", "addressLocality": "La Plata"}},
    "performer": [{"@type": "Person", "name": "Letizia Bloisi"},
                  {"@type": "Person", "name": "Geraldine Vivier."},
                  {"@type": "Person", "name": "Letizia Bloisi"}],
    "offers": {"@type": "Offer", "availability": "https://schema.org/InStock",
               "price": "30000", "priceCurrency": "ARS"}}]}


class DatosExtraTests(unittest.TestCase):
    def test_teatrocerca(self):
        d = evento_jsonld(pagina(TEATROCERCA))
        self.assertEqual(datos_extra(d), {
            "precio": 30000, "moneda": "ARS", "disponibilidad": "disponible",
            "elenco": ["Letizia Bloisi", "Geraldine Vivier"]})

    def test_precio_cero_no_es_gratis(self):
        """Livepass pone 0 en shows pagos sin venta abierta."""
        obj = {"@type": "Event", "name": "X", "startDate": "2026-12-01T20:00",
               "offers": {"price": 0, "priceCurrency": "ARS"}}
        self.assertNotIn("precio", datos_extra(evento_jsonld(pagina(obj))))

    def test_varias_ofertas_toma_la_mas_barata(self):
        obj = {"@type": "Event", "name": "X", "startDate": "2026-12-01T20:00",
               "offers": [{"price": "5000"}, {"price": "3500"}, {"price": 0, "availability": "SoldOut"}]}
        extra = datos_extra(evento_jsonld(pagina(obj)))
        self.assertEqual(extra["precio"], 3500)
        self.assertEqual(extra["moneda"], "ARS")
        self.assertEqual(extra["disponibilidad"], "agotado")

    def test_sin_offers_no_inventa(self):
        obj = {"@type": "Event", "name": "X", "startDate": "2026-12-01T20:00",
               "offers": {"price": "consultar"}}
        self.assertEqual(datos_extra(evento_jsonld(pagina(obj))), {})

    def test_evento_lleva_extra_y_dedup_lo_completa(self):
        sin = evento("Actúen", "2026-11-21 21:00:00", "Teatro Abierto", fuente="genda")
        con = evento("Actúen", "2026-11-21 21:00:00", "Teatro Abierto", fuente="teatrocerca",
                     extra={"precio": 30000, "moneda": "ARS"})
        (unico,) = deduplicar([sin, con])
        self.assertEqual(unico["fuente"], "genda")
        self.assertEqual(unico["precio"], 30000)


if __name__ == "__main__":
    unittest.main()
