// Reproduce los audios autorizados. El botón solo existe si el servidor entregó una URL de audio.
(function () {
  "use strict";
  let actual = null;
  document.addEventListener("click", function (evento) {
    const boton = evento.target.closest(".boton-audio[data-audio]");
    if (!boton) return;
    if (actual) { actual.pause(); actual = null; }
    const audio = new Audio(boton.dataset.audio);
    actual = audio;
    audio.addEventListener("error", function () {
      boton.textContent = "Audio no disponible";
      boton.disabled = true;
    });
    audio.play().catch(function () { /* el navegador bloqueó la reproducción */ });
  });
})();
