"""Repositorio EN MEMORIA con la misma interfaz que servicios/repositorio.py.

Sirve para probar rutas, cuentas y el motor de traducción sin MySQL. NO prueba las consultas SQL
(eso lo hace test_bd.py con SQLAlchemy real). Los textos en mixteco son marcadores como «[mx:hola]»:
no son datos lingüísticos, solo permiten comprobar el flujo.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from servicios.tipos import CorreoDuplicado, Hallada


class RepoFalso:
    def __init__(self):
        self.usuarios, self.tokens, self.aportes = {}, {}, []
        self.verificadas = {}          # texto_norm -> [Hallada]
        self.vocab = []                # entradas para /ejemplos
        self.audios = {}               # id -> ruta relativa
        self.llamadas_ia, self.tope_alcanzado = 0, False
        self._id = 0

    # -- cuentas
    def _vista(self, u):
        return SimpleNamespace(**{**u, "perfil": dict(u["perfil"])}) if u else None

    def usuario_por_correo(self, correo):
        return self._vista(next((u for u in self.usuarios.values() if u["correo"] == correo), None))

    def usuario_por_id(self, uid):
        return self._vista(self.usuarios.get(uid))

    def crear_usuario(self, nombre, correo, contrasena_hash):
        if self.usuario_por_correo(correo):
            raise CorreoDuplicado(correo)
        self._id += 1
        self.usuarios[self._id] = dict(id=self._id, nombre=nombre, correo=correo, contrasena_hash=contrasena_hash,
                                       rol="usuario", activo=True, creado_en=datetime.now(timezone.utc),
                                       perfil={k: "" for k in ("pronombres", "biografia", "instagram", "facebook",
                                                               "tiktok", "youtube", "sitio_web")})
        return self.usuario_por_id(self._id)

    def actualizar_cuenta(self, uid, datos):
        u = self.usuarios[uid]
        u["nombre"] = datos["nombre"]
        u["perfil"].update({k: v for k, v in datos.items() if k != "nombre"})

    def registrar_acceso(self, uid):
        pass

    def cambiar_contrasena(self, uid, h):
        self.usuarios[uid]["contrasena_hash"] = h
        for t in self.tokens.values():
            if t["uid"] == uid:
                t["usado"] = True

    def asignar_rol(self, correo, rol):
        u = self.usuario_por_correo(correo)
        if u:
            self.usuarios[u.id]["rol"] = rol
        return bool(u)

    # -- recuperación
    def guardar_token(self, uid, h, expira):
        self.tokens[h] = dict(uid=uid, expira=expira, usado=False, creado=datetime.now(timezone.utc))

    def tokens_recientes(self, uid, desde):
        return sum(1 for t in self.tokens.values() if t["uid"] == uid and t["creado"] >= desde)

    def token_vigente(self, h):
        t = self.tokens.get(h)
        return bool(t and not t["usado"] and t["expira"] > datetime.now(timezone.utc))

    def consumir_token(self, h):
        if not self.token_vigente(h):
            return None
        self.tokens[h]["usado"] = True
        return self.tokens[h]["uid"]

    # -- contenido
    def buscar_verificadas(self, norm, codigo):
        return self.verificadas.get(norm, [])

    def buscar_contexto(self, norm, codigo, limite=15):
        return [{"es": k, "mixteco": v[0].texto, "tipo": "palabra"} for k, v in self.verificadas.items()
                if k in norm.split()][:limite]

    def vocabulario(self, codigo, categoria=None, tipo=None, busqueda=None, pagina=1, por_pagina=30):
        e = [x for x in self.vocab if (not categoria or x.get("clave") == categoria) and (not tipo or x["tipo"] == tipo)
             and (not busqueda or busqueda in x["es"])]
        return e[(pagina - 1) * por_pagina: pagina * por_pagina], len(e)

    def categorias_con_conteo(self, codigo):
        return []

    def contar_verificadas(self, codigo):
        return len(self.vocab) + len(self.verificadas)

    def crear_aporte(self, codigo, es, mx, tipo, uid):
        if any(a["es"] == es and a["mixteco"] == mx for a in self.aportes):
            return False
        self.aportes.append(dict(es=es, mixteco=mx, tipo=tipo, uid=uid, estado="pendiente", fecha=None))
        return True

    def mis_aportes(self, uid, limite=20):
        return [a for a in self.aportes if a["uid"] == uid]

    def audio_ruta(self, audio_id):
        return self.audios.get(audio_id)

    def reservar_llamada_ia(self, limite):
        if self.tope_alcanzado or limite <= 0 or self.llamadas_ia >= limite:
            return False
        self.llamadas_ia += 1
        return True


def hallada(texto, **kw):
    return Hallada(texto=texto, **kw)
