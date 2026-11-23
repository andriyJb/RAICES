"""Validación de los formularios (funciones puras: no tocan la base de datos).

Cada función devuelve la lista de errores en español (vacía si todo está bien).
Los límites coinciden con las columnas de la base de datos (ver models.py).
"""
import re
import unicodedata

from .texto import limpiar_mixteco

LIMITE_NOMBRE = 80
LIMITE_CORREO = 254
LIMITE_PASSWORD = 128        # tope para que nadie obligue al servidor a procesar contraseñas enormes
LIMITES_PERFIL = {"pronombres": 30, "biografia": 300}
LIMITE_APORTE_ES = 200
LIMITE_APORTE_MIXTECO = 300

PATRON_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# Letras (con tonos), números, espacios, saltillo y signos comunes de puntuación.
PATRON_TEXTO = re.compile(r"[\w\s'\-/.,;:()¿?¡!̀-ͯ]+")

# Redes del perfil: (campo, nombre visible, ejemplo, patrón del enlace).
# El mismo patrón lo usa el navegador en el atributo pattern del formulario.
REDES = [
    ("instagram", "Instagram", "https://instagram.com/tu_usuario", r"https://(www[.])?instagram[.]com/.+"),
    ("facebook", "Facebook", "https://facebook.com/tu_usuario", r"https://(www[.]|m[.])?(facebook|fb)[.]com/.+"),
    ("tiktok", "TikTok", "https://tiktok.com/@tu_usuario", r"https://(www[.])?tiktok[.]com/@.+"),
    ("youtube", "YouTube", "https://youtube.com/@tu_canal", r"https://(www[.])?(youtube[.]com|youtu[.]be)/.+"),
    ("sitio_web", "Sitio web", "https://tu-sitio.com", r"https://\S+[.]\S+"),
]
LIMITE_ENLACE = 255


def limpiar_nombre(valor):
    """'  Ana   López ' → 'Ana López' (Unicode NFC, espacios simples)."""
    return " ".join(unicodedata.normalize("NFC", valor or "").split())


def validar_password(contrasena):
    errores = []
    if len(contrasena) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if len(contrasena) > LIMITE_PASSWORD:
        errores.append(f"La contraseña admite máximo {LIMITE_PASSWORD} caracteres.")
    if not re.search(r"[A-Z]", contrasena):
        errores.append("La contraseña debe incluir una mayúscula.")
    if not re.search(r"[a-z]", contrasena):
        errores.append("La contraseña debe incluir una minúscula.")
    if not re.search(r"\d", contrasena):
        errores.append("La contraseña debe incluir un número.")
    return errores


def validar_registro(nombre, correo, contrasena):
    errores = []
    if not nombre:
        errores.append("Escribe tu nombre completo.")
    elif len(nombre) > LIMITE_NOMBRE:
        errores.append(f"El nombre admite máximo {LIMITE_NOMBRE} caracteres.")
    if not correo:
        errores.append("Escribe tu correo electrónico.")
    elif len(correo) > LIMITE_CORREO or not PATRON_CORREO.match(correo):
        errores.append("Ingresa un correo electrónico con un formato válido.")
    return errores + validar_password(contrasena)


def validar_perfil(formulario):
    """Devuelve (datos_limpios, errores) para el formulario de la cuenta."""
    datos, errores = {}, []

    nombre = limpiar_nombre(formulario.get("nombre"))
    if not nombre:
        errores.append("El nombre no puede quedar vacío.")
    elif len(nombre) > LIMITE_NOMBRE:
        errores.append(f"El nombre admite máximo {LIMITE_NOMBRE} caracteres.")
    datos["nombre"] = nombre

    for campo, limite in LIMITES_PERFIL.items():
        valor = " ".join((formulario.get(campo) or "").split())
        if len(valor) > limite:
            errores.append(f"El campo «{campo}» admite máximo {limite} caracteres.")
        datos[campo] = valor[:limite]

    for campo, etiqueta, ejemplo, patron in REDES:
        valor = (formulario.get(campo) or "").strip()
        if valor and (len(valor) > LIMITE_ENLACE or not re.fullmatch(patron, valor)):
            errores.append(f"El enlace de {etiqueta} no es válido. Ejemplo: {ejemplo}")
            valor = ""
        datos[campo] = valor
    return datos, errores


def validar_aporte(espanol, mixteco):
    """Palabra o frase que aporta un usuario. Devuelve (espanol, mixteco, errores)."""
    espanol = " ".join(unicodedata.normalize("NFC", espanol or "").split())
    mixteco = limpiar_mixteco(mixteco)
    errores = []
    for valor, limite, pedir, nombre in (
        (espanol, LIMITE_APORTE_ES, "la palabra o frase en español", "El texto en español"),
        (mixteco, LIMITE_APORTE_MIXTECO, "la traducción en mixteco", "La traducción en mixteco"),
    ):
        if not valor:
            errores.append(f"Escribe {pedir}.")
        elif len(valor) > limite:
            errores.append(f"{nombre} admite máximo {limite} caracteres.")
        elif not PATRON_TEXTO.fullmatch(valor):
            errores.append(f"{nombre} tiene caracteres que no se pueden guardar.")
    return espanol, mixteco, errores


def tipo_de_texto(texto):
    """Clasifica un texto en español: palabra (1), frase (2-4 palabras) u oración (más)."""
    n = len(texto.split())
    return "palabra" if n <= 1 else ("frase" if n <= 4 else "oracion")
