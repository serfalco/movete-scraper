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


class SinopsisTests(unittest.TestCase):
    def test_corta_en_frase(self):
        from core.sitemap import sinopsis
        t = ("Durante años, un escritor mantuvo su prestigio gracias a un pacto sobrenatural. "
             "Pero el acuerdo deja de funcionar y una de las partes regresa para cobrar lo que le "
             "corresponde. Desde ese momento, cualquiera puede convertirse en presa y todos quedan "
             "obligados a actuar.")
        s = sinopsis(t)
        self.assertTrue(s.startswith("Durante años"))
        self.assertTrue(s.endswith("corresponde."))
        self.assertLessEqual(len(s), 240)

    def test_frase_larga_corta_en_palabra(self):
        from core.sitemap import sinopsis
        s = sinopsis("palabra " * 60)
        self.assertTrue(s.endswith("…"))
        self.assertLessEqual(len(s), 241)

    def test_descarta_textos_de_venta_y_cortos(self):
        from core.sitemap import sinopsis
        self.assertEqual(sinopsis("Función el 21 de noviembre a las 21 hs. Reservá tus entradas."), "")
        self.assertEqual(sinopsis("Show en vivo."), "")
        self.assertEqual(sinopsis("ENTRADAPRECIOGENERALDesde $50.000**los precios publicados en la web "
                                  "no incluyen cargo por servicioMEDIOS DE PAGO HABILITADOS"), "")
        self.assertEqual(sinopsis("una de las caras más reconocidas del humor argentino."),
                         "Una de las caras más reconocidas del humor argentino.")
        self.assertEqual(sinopsis("<p>Una obra sobre la memoria &amp; el olvido en la ciudad de La Plata.</p>"),
                         "Una obra sobre la memoria & el olvido en la ciudad de La Plata.")

    def test_llega_al_evento(self):
        obj = dict(TEATROCERCA["@graph"][0], description="Durante años, un escritor mantuvo su prestigio gracias a un pacto sobrenatural.")
        extra = datos_extra(evento_jsonld(pagina(obj)))
        self.assertEqual(extra["sinopsis"], "Durante años, un escritor mantuvo su prestigio gracias a un pacto sobrenatural.")
