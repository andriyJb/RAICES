// Interfaz del traductor. Construye el resultado con textContent (nunca innerHTML)
// para que ningún texto devuelto por el servidor pueda ejecutarse como código.
(function () {
  "use strict";

  const raiz = document.getElementById("traductor");
  if (!raiz) return;

  const formulario = document.getElementById("form-traductor");
  const campo = document.getElementById("texto");
  const contador = document.getElementById("contador");
  const boton = document.getElementById("boton-traducir");
  const zona = document.getElementById("resultado");
  const maximo = Number(raiz.dataset.max);

  const ESTADOS = {
    verificada: { icono: "✓", titulo: "Traducción verificada",
      detalle: "Revisada y aprobada por un hablante competente o respaldada por una fuente lingüística confiable." },
    automatica: { icono: "!", titulo: "Automática · sin verificar", detalle: "" },
    insuficiente: { icono: "i", titulo: "Información insuficiente", detalle: "" },
  };

  function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined) nodo.textContent = texto;
    return nodo;
  }

  function fila(lista, etiqueta, valor) {
    const caja = el("div", "estado__dato");
    caja.append(el("dt", null, etiqueta), el("dd", null, valor));
    lista.append(caja);
  }

  function mostrarError(mensaje) {
    zona.replaceChildren();
    const tarjeta = el("article", "estado estado--error");
    tarjeta.append(el("p", "estado__aviso", mensaje));
    zona.append(tarjeta);
    zona.hidden = false;
  }

  function mostrarResultado(r) {
    const info = ESTADOS[r.estado] || ESTADOS.insuficiente;
    const tarjeta = el("article", "estado estado--" + (ESTADOS[r.estado] ? r.estado : "insuficiente"));

    const cabecera = el("header", "estado__cabecera");
    const icono = el("span", "estado__icono", info.icono);
    icono.setAttribute("aria-hidden", "true");
    cabecera.append(icono, el("h2", "estado__titulo", info.titulo));
    tarjeta.append(cabecera);

    if (r.traduccion) {
      const texto = el("p", "estado__traduccion", r.traduccion);
      texto.lang = r.variante;
      tarjeta.append(texto);
    }
    if (r.alternativas && r.alternativas.length) {
      const otras = el("p", "estado__alternativas", "Otras opciones verificadas: ");
      const lista = el("span", null, r.alternativas.join(" · "));
      lista.lang = r.variante;
      otras.append(lista);
      tarjeta.append(otras);
    }

    if (r.audio_url) {
      // Solo llega audio_url cuando el servidor tiene un archivo aprobado y autorizado.
      const b = el("button", "boton-audio", "▶ Escuchar");
      b.type = "button";
      b.dataset.audio = r.audio_url;
      b.setAttribute("aria-label", "Escuchar la pronunciación");
      tarjeta.append(b);
    }

    const aviso = r.mensaje || info.detalle;
    if (aviso) tarjeta.append(el("p", "estado__aviso", aviso));

    if (r.ejemplos && r.ejemplos.length) {
      const lista = el("ul", "entrada__ejemplos");
      r.ejemplos.forEach(function (x) {
        const li = el("li", null, x.es + " — ");
        const mx = el("span", null, x.mixteco);
        mx.lang = r.variante;
        li.append(mx);
        lista.append(li);
      });
      tarjeta.append(lista);
    }

    const datos = el("dl", "estado__datos");
    fila(datos, "Idioma de origen", "Español");
    fila(datos, "Idioma de destino", "Mixteco");
    fila(datos, "Variante", raiz.dataset.varianteNombre + " (" + r.variante + ")");
    if (r.categoria) fila(datos, "Categoría", r.categoria);
    if (r.procedencia) fila(datos, "Procedencia", r.procedencia);
    tarjeta.append(datos);

    zona.replaceChildren(tarjeta);
    zona.hidden = false;
  }

  function actualizarContador() {
    contador.textContent = campo.value.length + " / " + maximo;
  }
  campo.addEventListener("input", actualizarContador);
  actualizarContador();

  formulario.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    const texto = campo.value.trim();
    if (!texto) {
      mostrarError("Escribe una palabra, frase u oración.");
      campo.focus();
      return;
    }

    boton.disabled = true;
    boton.textContent = "Traduciendo…";
    try {
      const respuesta = await fetch(raiz.dataset.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": raiz.dataset.csrf },
        body: JSON.stringify({ texto: texto, variante: raiz.dataset.variante }),
      });
      let datos = null;
      try { datos = await respuesta.json(); } catch (e) { /* respuesta sin JSON */ }
      if (!respuesta.ok) {
        mostrarError((datos && datos.error) || "No se pudo traducir. Inténtalo de nuevo.");
      } else {
        mostrarResultado(datos);
      }
    } catch (e) {
      mostrarError("No hay conexión con el servidor. Revisa tu red e inténtalo de nuevo.");
    } finally {
      boton.disabled = false;
      boton.textContent = "Traducir";
    }
  });
})();
