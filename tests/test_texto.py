from servicios.texto import normalizar_es, validar_entrada


def test_normalizar_quita_acentos_y_puntuacion():
    assert normalizar_es("¿Cómo   ESTÁS?") == "como estas"


def test_normalizar_conserva_la_enie():
    assert normalizar_es("año") != normalizar_es("ano")


def test_validar_entrada_limpia_espacios_y_caracteres_invisibles():
    texto, error = validar_entrada("  hola​   mundo \x00 ", 50)
    assert error is None
    assert texto == "hola mundo"


def test_validar_entrada_rechaza_vacio_largo_y_tipos_raros():
    assert validar_entrada("   ", 10)[1]
    assert validar_entrada("a" * 11, 10)[1]
    assert validar_entrada(None, 10)[1]
    assert validar_entrada(["hola"], 10)[1]
