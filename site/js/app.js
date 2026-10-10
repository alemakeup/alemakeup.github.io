/* Tienda: catálogo, filtros, detalle de producto, carrito y pedido por WhatsApp */
(function () {
  const { T, esc, cop, waLink } = window.AM;
  const C = window.CATALOGO || { productos: [], categorias: [] };
  const PRODUCTOS = C.productos;
  const porId = new Map(PRODUCTOS.map((p) => [p.id, p]));
  const PAGINA = 24;

  const $ = (s, r = document) => r.querySelector(s);
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  PRODUCTOS.forEach((p) => (p._q = norm(`${p.nombre} ${p.categoria} ${p.grupo} ${p.ref}`)));

  const estado = { grupo: "", sub: "", q: "", orden: "relevancia", visibles: PAGINA };

  /* ---------------- Catálogo ---------------- */
  function filtrar() {
    const palabras = norm(estado.q).split(/\s+/).filter(Boolean);
    let lista = PRODUCTOS.filter((p) =>
      (!estado.grupo || p.grupo === estado.grupo) &&
      (!estado.sub || p.categoria === estado.sub) &&
      palabras.every((w) => p._q.includes(w))
    );
    const o = estado.orden;
    if (o === "precio-asc") lista = [...lista].sort((a, b) => a.precio - b.precio);
    else if (o === "precio-desc") lista = [...lista].sort((a, b) => b.precio - a.precio);
    else if (o === "nombre") lista = [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
    else lista = [...lista].sort((a, b) => (b.imagenes.length > 0) - (a.imagenes.length > 0));
    return lista;
  }

  function tarjeta(p) {
    const img = p.imagenes[0]
      ? `<img src="${esc(p.imagenes[0])}" alt="${esc(p.nombre)}" loading="lazy" decoding="async" width="300" height="300">`
      : `<span class="noimg">A</span>`;
    const nOp = p.variantes.length ? p.variantes[0].opciones.length : 0;
    const badge = nOp > 1 ? `<span class="badge">${nOp} opciones</span>` : "";
    return `
      <article class="card">
        <button class="card-img" data-open="${p.id}" aria-label="Ver ${esc(p.nombre)}">${img}${badge}</button>
        <div class="card-body">
          <div class="card-cat">${esc(p.categoria)}</div>
          <h3 class="card-title" data-open="${p.id}">${esc(p.nombre)}</h3>
          <div class="card-foot">
            <span class="price">${cop.format(p.precio)}</span>
            <button class="add-btn" data-quick="${p.id}" aria-label="Agregar ${esc(p.nombre)} al carrito">
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
            </button>
          </div>
        </div>
      </article>`;
  }

  function render() {
    const lista = filtrar();
    const grid = $("#grid");
    grid.innerHTML = lista.length
      ? lista.slice(0, estado.visibles).map(tarjeta).join("")
      : `<div class="empty" style="grid-column:1/-1">No encontramos productos con esa búsqueda. Prueba con otra palabra o <a data-wa="Hola, estoy buscando: ${esc(estado.q)}" href="#">pregúntanos por WhatsApp</a>.</div>`;
    window.AM.wireWhatsApp(grid);
    $("#resultInfo").textContent = `${lista.length} producto${lista.length === 1 ? "" : "s"}${estado.grupo ? " en " + (estado.sub || estado.grupo) : ""}`;
    $("#loadMore").style.display = lista.length > estado.visibles ? "" : "none";
  }

  function renderChips() {
    const grupos = ["", ...C.categorias.map((c) => c.grupo)];
    $("#groupChips").innerHTML = grupos
      .map((g) => `<button class="chip${g === estado.grupo ? " active" : ""}" data-g="${esc(g)}" role="tab" aria-selected="${g === estado.grupo}">${g ? esc(g) : "Todo"}</button>`)
      .join("");
    const cat = C.categorias.find((c) => c.grupo === estado.grupo);
    const subs = cat && cat.subcategorias.length > 1 ? ["", ...cat.subcategorias] : [];
    $("#subChips").innerHTML = subs
      .map((s) => `<button class="chip${s === estado.sub ? " active" : ""}" data-s="${esc(s)}">${s ? esc(s) : "Todas"}</button>`)
      .join("");
    $("#subChips").style.display = subs.length ? "" : "none";
  }

  function irAGrupo(g) {
    Object.assign(estado, { grupo: g, sub: "", visibles: PAGINA });
    renderChips();
    render();
  }

  /* ---------------- Detalle de producto ---------------- */
  let actual = null, cantidad = 1;

  function abrirProducto(id) {
    const p = porId.get(id);
    if (!p) return;
    actual = p;
    cantidad = 1;
    $("#mCat").textContent = p.categoria;
    $("#mTitle").textContent = p.nombre;
    $("#mPrice").textContent = cop.format(p.precio);
    const desc = (p.descripcion || "").trim();
    const larga = desc.length > 280;
    $("#mDescWrap").hidden = !desc;
    $("#mDesc").textContent = desc;
    $("#mDesc").classList.toggle("collapsed", larga);
    $("#mDescMore").hidden = !larga;
    $("#mDescMore").textContent = "Ver más";
    $("#mQty").textContent = "1";
    const img = $("#mImg");
    img.src = p.imagenes[0] || "assets/logo.webp";
    img.alt = p.nombre;
    $("#mThumbs").innerHTML = p.imagenes.length > 1
      ? p.imagenes.map((src, i) => `<button class="${i ? "" : "active"}" data-src="${esc(src)}" aria-label="Foto ${i + 1}"><img src="${esc(src)}" alt="" loading="lazy"></button>`).join("")
      : "";
    $("#mVariants").innerHTML = p.variantes
      .map((v, i) => `
        <div class="field">
          <label for="var${i}">${esc(v.nombre === "Opción" ? "Tono / opción" : v.nombre)}</label>
          <select id="var${i}" data-var="${esc(v.nombre)}">
            <option value="">Elige una opción</option>
            ${v.opciones.map((o) => `<option>${esc(o)}</option>`).join("")}
          </select>
        </div>`)
      .join("");
    abrir("#modal");
  }

  function varianteElegida() {
    const sel = [...document.querySelectorAll("#mVariants select")];
    const faltante = sel.find((s) => !s.value);
    if (faltante) {
      faltante.focus();
      toast("Elige una opción antes de agregar");
      return null;
    }
    return sel.map((s) => (s.dataset.var === "Opción" ? s.value : `${s.dataset.var}: ${s.value}`)).join(" · ");
  }

  /* ---------------- Carrito ---------------- */
  const CLAVE = "alemakeup_carrito_v1";
  let carrito = [];
  try { carrito = JSON.parse(localStorage.getItem(CLAVE) || "[]"); } catch { carrito = []; }
  carrito = carrito.filter((l) => porId.has(l.id));

  const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(carrito)); } catch {} };

  function agregar(id, variante, qty) {
    const l = carrito.find((x) => x.id === id && x.variante === variante);
    if (l) l.qty += qty; else carrito.push({ id, variante, qty });
    guardar();
    renderCarrito();
    toast("Agregado al carrito ♡");
  }

  const subtotal = () => carrito.reduce((s, l) => s + porId.get(l.id).precio * l.qty, 0);

  function renderCarrito() {
    const n = carrito.reduce((s, l) => s + l.qty, 0);
    const badge = $("#cartCount");
    badge.textContent = n;
    badge.dataset.n = n;
    $("#cartTotal").textContent = cop.format(subtotal());
    $("#cartLines").innerHTML = carrito.length
      ? carrito.map((l, i) => {
          const p = porId.get(l.id);
          const img = p.imagenes[0] ? `<img src="${esc(p.imagenes[0])}" alt="">` : `<div class="ph"></div>`;
          return `
            <div class="line">
              ${img}
              <div>
                <h4>${esc(p.nombre)}</h4>
                ${l.variante ? `<div class="var">${esc(l.variante)}</div>` : ""}
                <div class="var">${cop.format(p.precio)} c/u</div>
              </div>
              <div class="line-right">
                <div class="qty"><button data-dec="${i}" aria-label="Menos">−</button><span>${l.qty}</span><button data-inc="${i}" aria-label="Más">+</button></div>
                <button class="link-btn" data-del="${i}">Quitar</button>
              </div>
            </div>`;
        }).join("")
      : `<div class="empty">Tu carrito está vacío.<br><br><button class="btn btn-outline" data-close>Ver productos</button></div>`;
    $("#checkout").style.display = carrito.length ? "" : "none";
    $("#sendOrder").disabled = !carrito.length;
  }

  function enviarPedido() {
    const f = $("#checkout");
    const val = (id) => $(id).value.trim();
    const requeridos = ["#cName", "#cPhone", "#cCity", "#cAddr"];
    const vacio = requeridos.find((id) => !val(id));
    if (vacio) { $(vacio).focus(); toast("Completa tus datos de entrega"); return; }
    if (!/^[\d\s+()-]{7,}$/.test(val("#cPhone"))) { $("#cPhone").focus(); toast("Revisa el número de celular"); return; }
    if (!$("#cConsent").checked) { $("#cConsent").focus(); toast("Debes aceptar los términos y la política de datos"); return; }

    const lineas = carrito.map((l, i) => {
      const p = porId.get(l.id);
      return `${i + 1}. ${p.nombre}${l.variante ? ` (${l.variante})` : ""} x${l.qty} — ${cop.format(p.precio * l.qty)}`;
    });
    const msg = [
      `*NUEVO PEDIDO — ${T.nombre.toUpperCase()}*`,
      "",
      ...lineas,
      "",
      `*Subtotal productos:* ${cop.format(subtotal())}`,
      "_(Envío por confirmar)_",
      "",
      `*Nombre:* ${val("#cName")}`,
      `*Celular:* ${val("#cPhone")}`,
      `*Ciudad:* ${val("#cCity")}`,
      `*Dirección:* ${val("#cAddr")}`,
      `*Pago:* ${val("#cPay")}`,
      val("#cNotes") ? `*Notas:* ${val("#cNotes")}` : "",
      "",
      "[x] Acepto los términos y condiciones y autorizo el tratamiento de mis datos para gestionar este pedido.",
    ].filter((x, i, a) => x !== "" || a[i - 1] !== "").join("\n");

    try { localStorage.setItem("alemakeup_cliente_v1", JSON.stringify({ n: val("#cName"), t: val("#cPhone"), c: val("#cCity"), d: val("#cAddr") })); } catch {}
    window.open(waLink(msg), "_blank", "noopener");
    toast("Abriendo WhatsApp…");
    f.dataset.sent = "1";
  }

  function precargarCliente() {
    try {
      const c = JSON.parse(localStorage.getItem("alemakeup_cliente_v1") || "null");
      if (!c) return;
      $("#cName").value = c.n || ""; $("#cPhone").value = c.t || ""; $("#cCity").value = c.c || ""; $("#cAddr").value = c.d || "";
    } catch {}
  }

  /* ---------------- Capas ---------------- */
  function abrir(sel) {
    $("#overlay").classList.add("open");
    $(sel).classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function cerrar() {
    ["#overlay", "#modal", "#drawer"].forEach((s) => $(s).classList.remove("open"));
    document.body.style.overflow = "";
  }
  let tt;
  function toast(t) {
    const el = $("#toast");
    el.textContent = t;
    el.classList.add("show");
    clearTimeout(tt);
    tt = setTimeout(() => el.classList.remove("show"), 2200);
  }

  /* ---------------- Eventos ---------------- */
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, [data-open], [data-close], [data-group]");
    if (!t) return;
    if (t.dataset.open) return abrirProducto(t.dataset.open);
    if (t.hasAttribute("data-close")) return cerrar();
    if (t.dataset.quick) {
      const p = porId.get(t.dataset.quick);
      return p.variantes.length ? abrirProducto(p.id) : agregar(p.id, "", 1);
    }
    if (t.dataset.group) { irAGrupo(t.dataset.group); return $("#tienda").scrollIntoView({ behavior: "smooth" }); }
    if (t.dataset.g !== undefined) return irAGrupo(t.dataset.g);
    if (t.dataset.s !== undefined) { Object.assign(estado, { sub: t.dataset.s, visibles: PAGINA }); renderChips(); return render(); }
    if (t.dataset.src) {
      $("#mImg").src = t.dataset.src;
      document.querySelectorAll("#mThumbs button").forEach((b) => b.classList.toggle("active", b === t));
      return;
    }
    const i = Number(t.dataset.inc ?? t.dataset.dec ?? t.dataset.del);
    if (t.dataset.inc !== undefined) carrito[i].qty++;
    else if (t.dataset.dec !== undefined) { if (--carrito[i].qty < 1) carrito.splice(i, 1); }
    else if (t.dataset.del !== undefined) carrito.splice(i, 1);
    else return;
    guardar();
    renderCarrito();
  });

  $("#overlay").addEventListener("click", cerrar);
  document.addEventListener("keydown", (e) => e.key === "Escape" && cerrar());
  $("#openCart").addEventListener("click", () => { renderCarrito(); abrir("#drawer"); });
  $("#mMinus").addEventListener("click", () => { cantidad = Math.max(1, cantidad - 1); $("#mQty").textContent = cantidad; });
  $("#mPlus").addEventListener("click", () => { cantidad++; $("#mQty").textContent = cantidad; });
  $("#mDescMore").addEventListener("click", () => {
    const abierta = $("#mDesc").classList.toggle("collapsed") === false;
    $("#mDescMore").textContent = abierta ? "Ver menos" : "Ver más";
  });
  $("#mAdd").addEventListener("click", () => {
    const v = varianteElegida();
    if (v === null) return;
    agregar(actual.id, v, cantidad);
    cerrar();
  });
  $("#sendOrder").addEventListener("click", enviarPedido);

  let deb;
  $("#search").addEventListener("input", (e) => {
    clearTimeout(deb);
    deb = setTimeout(() => { Object.assign(estado, { q: e.target.value, visibles: PAGINA }); render(); }, 150);
  });
  $("#sort").addEventListener("change", (e) => { Object.assign(estado, { orden: e.target.value, visibles: PAGINA }); render(); });
  $("#clearFilters").addEventListener("click", () => {
    $("#search").value = ""; $("#sort").value = "relevancia";
    Object.assign(estado, { grupo: "", sub: "", q: "", orden: "relevancia", visibles: PAGINA });
    renderChips(); render();
  });
  $("#loadMore").addEventListener("click", () => { estado.visibles += PAGINA; render(); });

  /* ---------------- Inicio ---------------- */
  $("#cPay").innerHTML = (T.medios_pago || []).map((m) => `<option>${esc(m)}</option>`).join("");
  if (T.medios_pago) $("#payMethods").textContent = T.medios_pago.join(", ") + ".";
  if (T.tiempo_envio) $("#shipTime").textContent = T.tiempo_envio;
  document.querySelectorAll("[data-count]").forEach((el) => {
    const n = PRODUCTOS.filter((p) => p.grupo === el.dataset.count).length;
    el.textContent = n ? `${n} productos` : "";
  });
  precargarCliente();
  renderChips();
  render();
  renderCarrito();
})();
