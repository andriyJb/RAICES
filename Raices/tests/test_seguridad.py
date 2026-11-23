from seguridad import LimitadorFallos, LimitadorVentana


def test_limitador_bloquea_al_pasar_el_limite_y_separa_por_clave():
    lim = LimitadorVentana(limite=2, ventana=60)
    assert lim.permitir("a") and lim.permitir("a")
    assert not lim.permitir("a")
    assert lim.permitir("b")


def test_limitador_de_fallos_bloquea_y_se_reinicia_con_exito():
    lim = LimitadorFallos(maximo=3, bloqueo=60)
    for _ in range(3):
        assert not lim.bloqueado("x")
        lim.fallo("x")
    assert lim.bloqueado("x") and not lim.bloqueado("y")
    lim.exito("x")
    assert not lim.bloqueado("x")


def test_el_bloqueo_vence():
    lim = LimitadorFallos(maximo=1, bloqueo=0)
    lim.fallo("x")
    assert not lim.bloqueado("x")


def test_url_de_base_de_datos_con_socket_de_cloud_sql(monkeypatch):
    from config import _url_base_datos
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p@ss")
    monkeypatch.setenv("DB_HOST", "/cloudsql/p:r:i")
    assert _url_base_datos() == "mysql+pymysql://u:p%40ss@/raices?unix_socket=/cloudsql/p:r:i&charset=utf8mb4"
    monkeypatch.setenv("DB_HOST", "localhost")
    assert "@localhost:3306/raices" in _url_base_datos()
