from scrapers.alternativa import _es_gran_la_plata


def test_zona_la_plata():
    assert _es_gran_la_plata('1', {'zona': 'La Plata', 'lat': 0, 'lng': 0})


def test_teatro_bar_cargado_como_olivos():
    assert _es_gran_la_plata('1140', {'zona': 'Olivos', 'lat': 0, 'lng': 0})


def test_coordenadas_dentro_de_la_plata():
    assert _es_gran_la_plata('9', {'zona': 'Otra', 'lat': -34.92, 'lng': -57.95})


def test_olivos_real_queda_afuera():
    assert not _es_gran_la_plata('9', {'zona': 'Olivos', 'lat': -34.51, 'lng': -58.49})


def test_caba_sin_coordenadas_queda_afuera():
    assert not _es_gran_la_plata('9', {'zona': 'Almagro', 'lat': None, 'lng': None})
