/* Utilidades compartidas: datos de la tienda, WhatsApp, pie de página */
(function () {
  const T = window.TIENDA || {};

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pendiente = (v) => /^\[COMPLETAR/.test(v || "");
  const dato = (v) => (pendiente(v) ? `<span class="todo">${esc(v)}</span>` : esc(v));
  const cop = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });

  // api.whatsapp.com/send en vez de wa.me: la redirección de wa.me daña emojis y algunos símbolos
  const waLink = (texto) => `https://api.whatsapp.com/send?phone=${T.whatsapp}&text=${encodeURIComponent(texto || "")}`;
  const waVisible = () => {
    const n = String(T.whatsapp || "");
    return n.startsWith("57") ? `+57 ${n.slice(2, 5)} ${n.slice(5, 8)} ${n.slice(8)}` : `+${n}`;
  };

  function wireWhatsApp(root = document) {
    root.querySelectorAll("[data-wa]").forEach((a) => {
      a.href = waLink(a.dataset.wa);
      a.target = "_blank";
      a.rel = "noopener";
    });
  }

  function fillStore(root = document) {
    root.querySelectorAll("[data-store]").forEach((el) => {
      const k = el.dataset.store;
      if (!T[k] && k !== "whatsapp") {
        const fila = el.closest("tr, li, [data-opcional]");
        if (fila) fila.remove(); else el.remove();
        return;
      }
      if (k === "whatsapp") el.innerHTML = esc(waVisible());
      else if (k === "medios_pago") el.innerHTML = (T.medios_pago || []).map(esc).join(", ");
      else el.innerHTML = dato(T[k]);
    });
  }

  function renderFooter() {
    const f = document.getElementById("contacto");
    if (!f) return;
    const year = new Date().getFullYear();
    f.innerHTML = `
      <div class="container">
        <div class="footer-grid">
          <div>
            <h4>${esc(T.nombre)}</h4>
            <p style="margin:0 0 10px">${esc(T.eslogan)}. Maquillaje, cabello, cuidado facial y accesorios.</p>
            <ul>
              <li>WhatsApp: <a data-wa="Hola Alemakeup" href="#">${esc(waVisible())}</a></li>
              <li>Correo: ${pendiente(T.email) ? dato(T.email) : `<a href="mailto:${esc(T.email)}">${esc(T.email)}</a>`}</li>
              ${T.instagram ? `<li>Instagram: <a href="https://instagram.com/${esc(T.instagram.replace("@", ""))}" target="_blank" rel="noopener">${esc(T.instagram)}</a></li>` : ""}
              <li>Atención: ${esc(T.horario_atencion)}</li>
            </ul>
            <p class="legal-id">Titular: ${[T.titular, T.documento].filter(Boolean).map(dato).join(" · ")}<br>${[T.direccion, T.ciudad].filter(Boolean).map(dato).join(" · ")}, Colombia</p>
          </div>
          <div>
            <h4>Información</h4>
            <ul>
              <li><a href="terminos.html">Términos y condiciones</a></li>
              <li><a href="terminos.html#envios">Envíos y entregas</a></li>
              <li><a href="terminos.html#garantia">Garantías, cambios y retracto</a></li>
              <li><a href="privacidad.html">Política de tratamiento de datos</a></li>
            </ul>
          </div>
          <div>
            <h4>Ayuda</h4>
            <ul>
              <li><a data-wa="Hola Alemakeup, tengo una petición, queja o reclamo sobre mi pedido:" href="#">Peticiones, quejas y reclamos (PQR)</a></li>
              <li><a href="https://www.sic.gov.co" target="_blank" rel="noopener">Superintendencia de Industria y Comercio</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          <span>© ${year} ${esc(T.nombre)}. Todos los derechos reservados.</span>
          <span>Precios en pesos colombianos (COP).</span>
        </div>
      </div>`;
    wireWhatsApp(f);
  }

  window.AM = { T, esc, cop, waLink, waVisible, wireWhatsApp, fillStore };

  document.addEventListener("DOMContentLoaded", () => {
    renderFooter();
    fillStore();
    wireWhatsApp();
  });
})();
