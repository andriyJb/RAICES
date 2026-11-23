"""Medidas básicas de seguridad: límites de uso, token anti-CSRF y cabeceras HTTP.

Los contadores viven en memoria del proceso: con varias instancias (Cloud Run puede crear
varias) cada una cuenta por separado. El tope diario de la IA, en cambio, vive en la base de datos.
"""
import hmac
import secrets
import threading
import time
from collections import deque
from urllib.parse import urlparse

from flask import request, session


class LimitadorVentana:
    """Permite como máximo `limite` solicitudes por clave (IP) en `ventana` segundos."""

    def __init__(self, limite, ventana):
        self.limite = limite
        self.ventana = ventana
        self._registros = {}
        self._cerrojo = threading.Lock()

    def permitir(self, clave):
        ahora = time.monotonic()
        with self._cerrojo:
            cola = self._registros.setdefault(clave, deque())
            while cola and ahora - cola[0] > self.ventana:
                cola.popleft()
            if len(cola) >= self.limite:
                return False
            cola.append(ahora)
            if len(self._registros) > 10_000:  # limpieza para que no crezca sin fin
                self._registros = {k: v for k, v in self._registros.items() if v}
            return True


class LimitadorFallos:
    """Bloquea una clave (IP + correo) tras `maximo` fallos seguidos durante `bloqueo` segundos."""

    def __init__(self, maximo, bloqueo):
        self.maximo, self.bloqueo = maximo, bloqueo
        self._fallos = {}      # clave -> (cantidad, instante del último fallo)
        self._cerrojo = threading.Lock()

    def bloqueado(self, clave):
        with self._cerrojo:
            cantidad, ultimo = self._fallos.get(clave, (0, 0))
            if cantidad >= self.maximo and time.monotonic() - ultimo < self.bloqueo:
                return True
            if cantidad >= self.maximo:          # el bloqueo ya venció
                del self._fallos[clave]
            return False

    def fallo(self, clave):
        with self._cerrojo:
            cantidad, _ = self._fallos.get(clave, (0, 0))
            self._fallos[clave] = (cantidad + 1, time.monotonic())
            if len(self._fallos) > 10_000:
                limite = time.monotonic() - self.bloqueo
                self._fallos = {k: v for k, v in self._fallos.items() if v[1] > limite}

    def exito(self, clave):
        with self._cerrojo:
            self._fallos.pop(clave, None)


def token_csrf():
    """Token por sesión. Se devuelve en la cabecera X-CSRF-Token (fetch) o en el campo oculto «csrf» (formularios)."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_valido():
    enviado = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
    esperado = session.get("csrf", "")
    return bool(esperado) and hmac.compare_digest(enviado, esperado)


def origen_valido():
    """Si el navegador indica el origen de la petición, debe ser este mismo sitio."""
    origen = request.headers.get("Origin")
    if not origen:
        return True
    return urlparse(origen).netloc == request.host


CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


def aplicar_cabeceras(respuesta, produccion=False):
    respuesta.headers.setdefault("Content-Security-Policy", CSP)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    respuesta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if produccion:
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return respuesta
