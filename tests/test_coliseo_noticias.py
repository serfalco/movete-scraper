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



class SalaCerradaTests(unittest.TestCase):
    def test_coliseo_cerrado_hasta_diciembre(self):
        from core.normalizar import en_sala_cerrada
        for lugar in ("Teatro Coliseo Podestá", "Teatro Municipal Coliseo Podestá",
                      "Teatro y Museo Coliseo Podestá"):
            self.assertTrue(en_sala_cerrada({"lugar": lugar, "fecha": "2026-11-14 20:00:00"}), lugar)
        self.assertFalse(en_sala_cerrada({"lugar": "Teatro Coliseo Podestá", "fecha": "2026-12-08 20:30:00"}))
        self.assertFalse(en_sala_cerrada({"lugar": "Teatro Metro", "fecha": "2026-11-14 20:00:00"}))


if __name__ == "__main__":
    unittest.main()
