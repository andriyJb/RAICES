"""Compara la base de datos REAL con los modelos (models.py): detecta tablas y columnas que faltan.

`db.create_all()` crea las tablas que no existen, pero NO agrega columnas nuevas a tablas ya creadas
(por eso aparecía «Unknown column … 1054» tras actualizar el proyecto). Esta función lo detecta y lo explica.
"""
from sqlalchemy import inspect


def diferencias(engine, metadata):
    """Devuelve (tablas_que_faltan, columnas_que_faltan); las columnas como «tabla.columna»."""
    inspector = inspect(engine)
    existentes = set(inspector.get_table_names())
    sin_tabla, sin_columna = [], []
    for nombre, tabla in metadata.tables.items():
        if nombre not in existentes:
            sin_tabla.append(nombre)
            continue
        columnas = {c["name"] for c in inspector.get_columns(nombre)}
        sin_columna += [f"{nombre}.{c.name}" for c in tabla.columns if c.name not in columnas]
    return sin_tabla, sin_columna


def informe(engine, metadata):
    """Texto para la consola. Cadena vacía si todo coincide."""
    sin_tabla, sin_columna = diferencias(engine, metadata)
    if not sin_tabla and not sin_columna:
        return ""
    lineas = ["La base de datos NO coincide con los modelos:"]
    lineas += [f"  - falta la tabla: {t}" for t in sin_tabla]
    lineas += [f"  - falta la columna: {c}" for c in sin_columna]
    lineas.append("Solución (hay una copia de seguridad hecha): ejecuta docs/mysql/migracion_desde_v1.sql "
                  "o, si la base no tiene datos que conservar, recréala con docs/mysql/schema_completo.sql. "
                  "Detalles en el README.")
    return "\n".join(lineas)
