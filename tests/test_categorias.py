import unittest
from datetime import date

from core.normalizar import detectar_categoria
from scrapers.genda import _mapear_categoria, _parsear_dia


class DetectarCategoriaTests(unittest.TestCase):
    def test_casos_reales_que_no_son_teatro(self):
        casos = {
            "Observación astronómica": "actividades",
            "Encuentro ajedrecístico": "actividades",
            "Actividad recreativa - Torneo de rompecabezas": "actividades",
            "Curso de magia": "taller",
            "Sociedad Platense de Stand Up": "stand-up",
            "Muestra del taller del match de improvisación": "impro",
            "Jam de dibujo con modelo vivo": "a-plasticas",
            "Argentina en pantalla grande": "cine",
            "Memoria, rock y resistencia": "musica",
        }
        for titulo, categoria in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(detectar_categoria(titulo), categoria)

    def test_desconocido_va_a_otros(self):
        self.assertEqual(detectar_categoria("Destino circular"), "otros")

    def test_una_fuente_puede_aportar_un_default(self):
        self.assertEqual(
            detectar_categoria("La cantante calva", default="teatro"),
            "teatro",
        )

    def test_categoria_de_genda_tiene_prioridad_sobre_el_descarte(self):
        self.assertEqual(_mapear_categoria("Teatro", "La Nona"), "teatro")
        self.assertEqual(
            _mapear_categoria("Actividades", "Observación astronómica", "Planetario"),
            "actividades",
        )
        self.assertEqual(_mapear_categoria("", "Centro de Arte UNLP"), "otros")
        self.assertEqual(_mapear_categoria("", "Un solo latido", "Cine Select"), "cine")

    def test_genda_lee_la_etiqueta_de_cada_tarjeta(self):
        html = """
        <div class="card card-custom">
          <div class="evento-tabs"><span class="badge">Infantil</span></div>
          <span>16:00 hs</span>
          <a data-title="Aladdín y el hechizo de la lámpara"
             data-sitio="Escenario 40"
             onclick="compartirLugar(event, 'https://agendalaplata.ar/evento/aladdin', 'Aladdín')">
          </a>
        </div>
        """
        eventos = _parsear_dia(html, date(2026, 6, 28))
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["categoria"], "infantil")
        self.assertEqual(eventos[0]["url"], "https://agendalaplata.ar/evento/aladdin")


if __name__ == "__main__":
    unittest.main()
