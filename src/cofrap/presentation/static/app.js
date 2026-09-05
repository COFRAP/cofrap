"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const tokenInput = document.getElementById("delivery-token");
  if (tokenInput) {
    const token = window.location.hash.slice(1);
    window.history.replaceState(null, "", window.location.pathname);
    if (/^[A-Za-z0-9_-]{43}$/.test(token)) {
      tokenInput.value = token;
      document.getElementById("delivery-button").disabled = false;
      document.getElementById("delivery-help").textContent =
        "Ce lien ne permet qu’une seule récupération.";
    }
  }
});

document.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.xhr.getResponseHeader("HX-Retarget") === "#feedback") {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

document.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target.id === "flow") {
    document.getElementById("flow").focus({ preventScroll: true });
  }
});

function showNetworkError() {
  const feedback = document.getElementById("feedback");
  if (feedback) {
    feedback.textContent =
      "Le serveur est momentanément indisponible. Vérifiez votre connexion puis réessayez.";
  }
}
document.addEventListener("htmx:sendError", showNetworkError);
document.addEventListener("htmx:responseError", showNetworkError);

window.addEventListener("pagehide", () => {
  document.querySelectorAll("[data-secret]").forEach((element) => {
    if (element instanceof HTMLInputElement) element.value = "";
    else element.replaceChildren();
  });
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) window.location.reload();
});
