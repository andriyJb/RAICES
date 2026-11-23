"""Prueba REAL y controlada de Gemini: hace EXACTAMENTE UNA llamada a la API.

Uso (desde la carpeta Raices, con GEMINI_API_KEY en .env):
    python scripts/probar_gemini.py "hola"

Imprime la propuesta, la confianza y si pasa el filtro. No guarda nada ni usa la base de datos.
Si algo falla, muestra el tipo de error (clave inválida, modelo inexistente, límite…) sin mostrar la clave.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "SRC"))

from config import Config  # noqa: E402
from servicios import filtro, ia  # noqa: E402
from servicios.tipos import ErrorProveedor  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def main():
    texto = " ".join(sys.argv[1:]).strip() or "hola"
    if not Config.GEMINI_API_KEY:
        sys.exit("Falta GEMINI_API_KEY en el archivo .env (carpeta Raices, junto a README.md).")
    proveedor = ia.ProveedorGemini(Config.GEMINI_API_KEY, Config.MODELO_GEMINI,
                                   Config.IA_TIMEOUT_SEGUNDOS, Config.IA_MAX_TOKENS_SALIDA, estricto=Config.IA_ESTRICTO)
    variante = Config.VARIANTES_INICIALES[0]
    print(f"Modelo: {Config.MODELO_GEMINI} · variante: {variante['nombre']} ({variante['codigo']}) · "
          f"modo {'estricto' if Config.IA_ESTRICTO else 'libre'} · 1 llamada real")
    try:
        p = proveedor.proponer(texto, variante, [])
    except ErrorProveedor as e:
        sys.exit(f"Falló la llamada: {e}")
    print(f"Texto:      {texto}\nPropuesta:  {p.traduccion}\nConfianza:  {p.confianza}\nMotivo:     {p.motivo or '-'}")
    if not p.traduccion:
        print("Resultado:  el MODELO no ofreció propuesta (la llamada a la API funcionó). La web mostrará «información insuficiente».")
    else:
        ok, motivo = filtro.evaluar(texto, p, [], Config.IA_ESTRICTO)
        print(f"Filtro:     {'ACEPTADA' if ok else 'RECHAZADA'} ({motivo}) · en la web: "
              f"{'«Automática sin verificar»' if ok else '«información insuficiente»'}")
    print("(Toda propuesta es automática y NO está verificada por un hablante.)")


main()
