import unittest

from scrapers.coliseo import es_noticia


class NoticiasColiseoTests(unittest.TestCase):
    def test_comunicado_de_obras_no_es_show(self):
        self.assertTrue(es_noticia(
            "EL TELÓN BAJA POR UN TIEMPO: COMIENZA LA SEGUNDA ETAPA DE PUESTA EN VALOR DEL COLISEO PODESTÁ"))

    def test_shows_reales_pasan(self):
        for t in ["LAS HIJAS", "La cena de los tontos", "CONNIE BALLARINI STAND UP",
                  'GABRIEL ROLÓN "PALABRA PLENA"', "Elena Roger en concierto"]:
            self.assertFalse(es_noticia(t), t)


if __name__ == "__main__":
    unittest.main()
