from types import SimpleNamespace as NS

from servicios import esquema


class InspectorFalso:
    def __init__(self, tablas):
        self.tablas = tablas

    def get_table_names(self):
        return list(self.tablas)

    def get_columns(self, nombre):
        return [{"name": c} for c in self.tablas[nombre]]


def _meta(**tablas):
    return NS(tables={n: NS(columns=[NS(name=c) for c in cols]) for n, cols in tablas.items()})


def test_detecta_columna_y_tabla_faltantes_y_explica_la_solucion(monkeypatch):
    real = {"traducciones": ["id", "texto_es"]}                      # BD antigua: sin aportada_por_id ni uso_ia
    monkeypatch.setattr(esquema, "inspect", lambda engine: InspectorFalso(real))
    meta = _meta(traducciones=["id", "texto_es", "aportada_por_id"], uso_ia=["fecha", "llamadas"])
    assert esquema.diferencias(None, meta) == (["uso_ia"], ["traducciones.aportada_por_id"])
    texto = esquema.informe(None, meta)
    assert "traducciones.aportada_por_id" in texto and "migracion_desde_v1.sql" in texto


def test_sin_diferencias_no_hay_informe(monkeypatch):
    monkeypatch.setattr(esquema, "inspect", lambda engine: InspectorFalso({"a": ["x", "y"]}))
    assert esquema.informe(None, _meta(a=["x", "y"])) == ""
