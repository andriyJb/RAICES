"""Compara los proveedores de IA con EL MISMO conjunto de textos e instrucciones.

Uso (desde la carpeta Raices, con las claves en .env):
    python scripts/comparar_modelos.py docs/plantilla_pruebas_ia.csv salida.csv [anthropic openai gemini]

Entrada: CSV con columna «texto_es» (y opcionalmente «tipo»). Las columnas de la salida:
proveedor, modelo, texto_es, traduccion, confianza, pasa_filtro, segundos, error, y las columnas
EN BLANCO que la persona hablante rellena (fidelidad, vocabulario, escritura, coherencia, correccion).

IMPORTANTE
- Este script hace llamadas REALES y consume saldo de tus cuentas de API: pruébalo primero con pocas filas.
- Sin la clave de un proveedor, ese proveedor se omite y se avisa; no se simula nada.
- Los resultados NO demuestran que un modelo traduzca bien la variante: solo la revisión de la persona
  hablante (columnas en blanco) permite concluir algo. Ver docs/plan_pruebas_ia.md.
- Se usa el diccionario VERIFICADO como contexto solo si hay base de datos configurada; si no, se envía sin contexto.
"""
import csv
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "SRC"))

from config import Config  # noqa: E402
from servicios import filtro, ia  # noqa: E402
from servicios.tipos import ErrorProveedor  # noqa: E402

COLUMNAS = ["proveedor", "modelo", "texto_es", "tipo", "traduccion", "confianza", "pasa_filtro", "segundos", "error",
            "fidelidad", "vocabulario", "escritura", "coherencia", "correccion_hablante"]


def main(argumentos):
    if len(argumentos) < 2:
        sys.exit(__doc__)
    entrada, salida, *pedidos = argumentos
    config = {k: getattr(Config, k) for k in dir(Config) if k.isupper()}
    variante = Config.VARIANTES_INICIALES[0]
    nombres = pedidos or list(ia.PROVEEDORES)

    proveedores = {}
    for nombre in nombres:
        try:
            proveedores[nombre] = ia.crear_proveedor({**config, "PROVEEDOR_IA": nombre})
        except ValueError as e:
            print(f"Se omite {nombre}: {e}")
    if not proveedores:
        sys.exit("No hay ningún proveedor con clave configurada.")

    with open(entrada, newline="", encoding="utf-8") as f:
        filas = [fila for fila in csv.DictReader(f) if (fila.get("texto_es") or "").strip()]
    print(f"{len(filas)} textos × {len(proveedores)} proveedores = {len(filas) * len(proveedores)} llamadas reales.")

    with open(salida, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        for nombre, proveedor in proveedores.items():
            for fila in filas:
                texto = fila["texto_es"].strip()
                registro = {"proveedor": nombre, "modelo": proveedor.modelo, "texto_es": texto, "tipo": fila.get("tipo", "")}
                inicio = time.monotonic()
                try:
                    p = proveedor.proponer(texto, variante, [])
                    registro.update(traduccion=p.traduccion or "", confianza=p.confianza,
                                    pasa_filtro=filtro.filtro_respaldo(texto, p, []))
                except ErrorProveedor as e:
                    registro["error"] = str(e)
                registro["segundos"] = round(time.monotonic() - inicio, 2)
                escritor.writerow(registro)
                f.flush()
    print(f"Listo: {salida}. Entrégalo a la persona hablante para que complete las columnas en blanco.")


if __name__ == "__main__":
    main(sys.argv[1:])
