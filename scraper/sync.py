"""
Sincroniza el catálogo del mayorista con la página de Alemakeup Cosmetics.

Qué hace:
  1. Lee todos los productos del catálogo mayorista (API pública de la tienda).
  2. Calcula el precio de venta = precio mayorista + margen (config.json).
  3. Descarga las fotos, las reduce y las guarda en site/img/productos/ (formato WebP).
  4. Escribe site/data/products.js y site/data/store.js, que lee la página.
  5. Escribe scraper/reporte_precios.csv (PRIVADO: incluye el costo, no se publica).

Uso:
  python scraper/sync.py               # sincroniza todo
  python scraper/sync.py --sin-fotos   # solo precios/productos, sin descargar fotos
"""

import argparse
import csv
import io
import json
import math
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
import truststore
from PIL import Image

# Usa los certificados de Windows/macOS (algunos servidores no envían la cadena completa)
truststore.inject_into_ssl()

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site"
DIR_IMG = SITE / "img" / "productos"
DIR_DATA = SITE / "data"
REPORTE = RAIZ / "scraper" / "reporte_precios.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlemakeupSync/1.0",
    "Accept": "application/json",
}

sesion = requests.Session()
sesion.headers.update(HEADERS)


def cargar_config():
    with open(RAIZ / "config.json", encoding="utf-8") as f:
        return json.load(f)


def normalizar(texto):
    """Mayúsculas, sin tildes ni emojis, espacios simples."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if c.isascii() and (c.isalnum() or c in " -/&"))
    return re.sub(r"\s+", " ", texto).strip().upper()


def titulo_bonito(texto):
    limpio = re.sub(r"\s+", " ", "".join(c for c in texto if c.isalnum() or c in " -/&,.áéíóúñÁÉÍÓÚÑ")).strip()
    return limpio.capitalize() if limpio.isupper() or limpio.islower() else limpio


def get_json(url, params, intentos=4):
    for i in range(intentos):
        try:
            r = sesion.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if i == intentos - 1:
                raise
            espera = 2 ** i
            print(f"  ! error ({e}); reintentando en {espera}s")
            time.sleep(espera)


def aplanar(categorias):
    for c in categorias:
        yield c
        yield from aplanar(c.get("subcategorias") or [])


def descargar_productos(cfg):
    m = cfg["mayorista"]
    tienda = get_json(f"{m['api']}/market/{m['dominio']}", {})["body"]
    negocio = tienda["infonegocio"]["_id"]
    # Las categorías "smart" (p. ej. Más Vendidos) repiten los mismos productos: se omiten
    categorias = [c for c in aplanar(tienda["categorias"]) if not c.get("smart") and c.get("activo", True)]

    def paginas(ruta, filtro=""):
        pagina, total_paginas = 1, 1
        while pagina <= total_paginas:
            params = {
                "negocio": negocio, "pagina": pagina, "porPagina": m["por_pagina"],
                "filtro": filtro, "smart": "false", "ref": "false",
            }
            body = get_json(f"{m['api']}/market/products/{ruta}", params)["body"]
            total_paginas = body.get("pagTotal") or 0
            yield from body.get("data", [])
            pagina += 1
            time.sleep(m["pausa_segundos"])

    # 1) Por categoría, guardando en cuáles aparece cada producto
    productos = {}
    for n, cat in enumerate(categorias, 1):
        for p in paginas(cat["_id"]):
            productos.setdefault(p["_id"], {**p, "_cats": []})["_cats"].append(cat["descripcion"])
        print(f"  [{n}/{len(categorias)}] {cat['descripcion']:<35} total: {len(productos)}")

    # 2) Con el buscador de la tienda: encuentra productos de categorías ocultas del menú
    antes = len(productos)
    for letra in "aeiou0123456789":
        for p in paginas("all", letra):
            if p["_id"] not in productos:
                ocultas = [c["descripcion"] for c in p.get("categories", []) if not c.get("smart")]
                productos[p["_id"]] = {**p, "_cats": ocultas}
    print(f"  Buscador: {len(productos) - antes} productos más (en categorías ocultas del menú del mayorista)")
    return list(productos.values())


def reglas_de_precio(p, pc):
    """Reglas generales de precio, sobrescritas por las de la marca que aparezca en el nombre."""
    reglas = {"modo": "margen", "margen_porcentaje": pc["margen_porcentaje"], "redondear_a": pc["redondear_a"]}
    nombre = " " + normalizar(p.get("title", "")) + " "
    for marca, ajustes in pc.get("por_marca", {}).items():
        if " " + normalizar(marca) + " " in nombre:
            reglas.update({k: v for k, v in ajustes.items() if not k.startswith("_")})
            break
    return reglas


def precio_venta(p, cfg):
    """Precio de venta según el modo:
    - "margen": costo mayorista + margen_porcentaje (el general).
    - "precio_publico": el precio al detal del mayorista, para marcas con precio fijo al público.
    Un producto puntual se puede fijar a mano en precios.por_producto."""
    pc = cfg["precios"]
    costo = p.get("preciomayor") or p.get("precio") or 0
    if costo <= 0:
        return costo, 0
    manual = pc.get("por_producto", {}).get(p["_id"])
    if manual:
        return costo, int(manual)

    r = reglas_de_precio(p, pc)
    detal = p.get("precio") or 0
    if r["modo"] == "precio_publico" and detal > 0:
        venta = detal
    else:
        venta = costo * (1 + r["margen_porcentaje"] / 100)
    paso = r["redondear_a"] or 1
    return costo, math.ceil(round(venta) / paso) * paso


class Clasificador:
    """Asigna grupo y subcategoría de la tienda a partir del nombre del producto.

    Orden: corrección manual → reglas de accesorios → categoría del mayorista si es solo de maquillaje
    → resto de reglas por palabras → reglas de maquillaje por palabras → categoría del mayorista → "Otros".
    """

    def __init__(self, cfg_cat):
        def prep(reglas):
            return [(r["grupo"], r["sub"], [normalizar(k) if k.strip() == k else " " + normalizar(k) + " " for k in r["palabras"]],
                     [normalizar(k) for k in r.get("requiere", [])]) for r in reglas]
        self.reglas = prep(cfg_cat["reglas"])
        self.reglas_maq = prep(cfg_cat["reglas_maquillaje"])
        self.mapa = sorted(((normalizar(k), tuple(v)) for k, v in cfg_cat["por_categoria_mayorista"].items()),
                           key=lambda x: -len(x[0]))
        self.correcciones = {k: tuple(v) for k, v in cfg_cat.get("correcciones", {}).items()}
        self.mezcladas = [normalizar(x) for x in cfg_cat.get("categorias_mezcladas", [])]

    @staticmethod
    def _buscar(reglas, nombre):
        for grupo, sub, palabras, requiere in reglas:
            if any(k in nombre for k in palabras) and (not requiere or any(k in nombre for k in requiere)):
                return grupo, sub
        return None

    def _mapear(self, cat):
        cn = normalizar(cat)
        return next((destino for clave, destino in self.mapa if clave in cn), None)

    def __call__(self, pid, titulo, cats):
        if pid in self.correcciones:
            return self.correcciones[pid]
        nombre = " " + normalizar(titulo) + " "
        accesorios = [r for r in self.reglas if r[0] == "Accesorios"]
        otras = [r for r in self.reglas if r[0] != "Accesorios"]
        destinos = [d for d in map(self._mapear, cats) if d]
        confiables = [d for c, d in zip(cats, map(self._mapear, cats))
                      if d and not any(x in normalizar(c) for x in self.mezcladas)]
        hallado = self._buscar(accesorios, nombre)
        if hallado:
            return hallado
        # Si el mayorista lo tiene solo en categorías de maquillaje, se respeta (ej. "Corrector sérum")
        if confiables and all(d[0] == "Maquillaje" for d in confiables):
            return confiables[0]
        return (self._buscar(otras, nombre) or self._buscar(self.reglas_maq, nombre)
                or (destinos[0] if destinos else ("Otros", "Otros")))


def procesar_imagen(args):
    url, destino, cfg_img = args
    if destino.exists():
        return True
    try:
        r = sesion.get(url, timeout=40)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        img = img.convert("RGBA") if img.mode in ("P", "LA") else img
        if img.mode == "RGBA":
            fondo = Image.new("RGB", img.size, (255, 255, 255))
            fondo.paste(img, mask=img.split()[3])
            img = fondo
        img = img.convert("RGB")
        ancho = cfg_img["ancho_max_px"]
        if img.width > ancho:
            img = img.resize((ancho, round(img.height * ancho / img.width)), Image.LANCZOS)
        destino.parent.mkdir(parents=True, exist_ok=True)
        img.save(destino, "WEBP", quality=cfg_img["calidad_webp"], method=5)
        return True
    except Exception as e:
        print(f"\n  ! no se pudo descargar {url}: {e}")
        return False


def escribir_tienda(cfg):
    DIR_DATA.mkdir(parents=True, exist_ok=True)
    (DIR_DATA / "store.js").write_text(
        "window.TIENDA = " + json.dumps(cfg["tienda"], ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser(description="Sincroniza el catálogo del mayorista.")
    ap.add_argument("--sin-fotos", action="store_true", help="no descargar fotos")
    ap.add_argument("--solo-tienda", action="store_true", help="solo regenerar datos de la tienda (store.js)")
    args = ap.parse_args()

    cfg = cargar_config()
    if args.solo_tienda:
        escribir_tienda(cfg)
        print("Datos de la tienda actualizados.")
        return
    excluir = [normalizar(x) for x in cfg["categorias"]["excluir_que_contengan"]]
    marcas = [(m, [normalizar(k) if k.strip() == k else " " + normalizar(k) + " " for k in ks])
              for m, ks in cfg.get("marcas", {}).items()]
    clasificar = Clasificador(cfg["categorias"])

    print("1/3 Leyendo catálogo del mayorista...")
    crudos = descargar_productos(cfg)

    print("2/3 Calculando precios...")
    productos, descargas, reporte = [], [], []
    for p in crudos:
        if not p.get("activo", True) or not p.get("showmayor", True):
            continue
        costo, venta = precio_venta(p, cfg)
        if venta <= 0:
            continue

        cats = [c for c in p.get("_cats", []) if not any(x in normalizar(c) for x in excluir)]
        grupo, categoria = clasificar(p["_id"], p.get("title", ""), cats)

        imagenes = []
        for i, nombre in enumerate((p.get("images") or [])[: cfg["imagenes"]["max_por_producto"]]):
            archivo = f"{p['_id']}_{i}.webp"
            imagenes.append(f"img/productos/{archivo}")
            descargas.append((f"{cfg['mayorista']['imagenes_url']}/{nombre}", DIR_IMG / archivo, cfg["imagenes"]))

        variantes = [
            {"nombre": (v.get("name") or "Opción").strip() or "Opción",
             "opciones": [o.strip() for o in v.get("variaciones", []) if o.strip()]}
            for v in p.get("variacion", [])
        ]
        variantes = [v for v in variantes if v["opciones"]]

        nombre_n = " " + normalizar(p.get("title", "")) + " "
        marca = next((m for m, ks in marcas if any(k in nombre_n for k in ks)), "")

        productos.append({
            "id": p["_id"],
            "marca": marca,
            "nombre": re.sub(r"\s+", " ", p.get("title", "")).strip(),
            "precio": venta,
            "grupo": grupo,
            "categoria": categoria,
            "imagenes": imagenes,
            "variantes": variantes,
            "ref": (p.get("inventario") or {}).get("sku", "").strip(),
        })
        reporte.append({
            "id": p["_id"],
            "producto": p.get("title", "").strip(),
            "grupo": grupo,
            "categoria": categoria,
            "categoria_mayorista": " / ".join(titulo_bonito(c) for c in cats),
            "costo_mayorista": costo,
            "precio_detal_mayorista": p.get("precio") or 0,
            "precio_alemakeup": venta,
            "ganancia": venta - costo,
        })

    orden_grupos = cfg["categorias"]["orden_grupos"]
    productos.sort(key=lambda x: (
        orden_grupos.index(x["grupo"]) if x["grupo"] in orden_grupos else len(orden_grupos),
        x["categoria"], x["nombre"].lower(),
    ))

    if not args.sin_fotos:
        print(f"3/3 Descargando fotos ({len(descargas)}; las que ya existen se omiten)...")
        hechos = 0
        with ThreadPoolExecutor(max_workers=cfg["imagenes"]["descargas_simultaneas"]) as ex:
            for ok in ex.map(procesar_imagen, descargas):
                hechos += 1
                if hechos % 25 == 0 or hechos == len(descargas):
                    print(f"  {hechos}/{len(descargas)}", end="\r")
        print()
        validas = {d[1].name for d in descargas}
        for f in DIR_IMG.glob("*.webp"):
            if f.name not in validas:
                f.unlink()
        for prod in productos:
            prod["imagenes"] = [i for i in prod["imagenes"] if (SITE / i).exists()]
    else:
        print("3/3 Fotos omitidas (--sin-fotos)")

    # Agrupar categorías para los filtros de la página
    arbol = {}
    for prod in productos:
        arbol.setdefault(prod["grupo"], set()).add(prod["categoria"])
    orden = cfg["categorias"]["orden_grupos"] + ["Otros"]
    categorias = [{"grupo": g, "subcategorias": sorted(arbol[g])} for g in orden if g in arbol]

    conteo_marcas = {}
    for prod in productos:
        if prod["marca"]:
            conteo_marcas[prod["marca"]] = conteo_marcas.get(prod["marca"], 0) + 1
    lista_marcas = [{"nombre": m, "productos": n}
                    for m, n in sorted(conteo_marcas.items(), key=lambda x: -x[1]) if n >= 3]

    DIR_DATA.mkdir(parents=True, exist_ok=True)
    catalogo = {
        "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "categorias": categorias,
        "marcas": lista_marcas,
        "productos": productos,
    }
    (DIR_DATA / "products.js").write_text(
        "window.CATALOGO = " + json.dumps(catalogo, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    escribir_tienda(cfg)

    with open(REPORTE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(reporte[0].keys()) if reporte else ["producto"], delimiter=";")
        w.writeheader()
        w.writerows(sorted(reporte, key=lambda r: r["producto"]))

    caros = sum(1 for r in reporte if r["precio_alemakeup"] > r["precio_detal_mayorista"] > 0)
    print(f"\nListo: {len(productos)} productos publicados.")
    print(f"  Catálogo:  {DIR_DATA / 'products.js'}")
    print(f"  Reporte:   {REPORTE}  (privado, con costos)")
    if caros:
        print(f"  Nota: {caros} productos quedan más caros que el precio detal del mayorista")
        print("        (por la ganancia mínima o por un ajuste de marca en config.json → precios).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelado.")
