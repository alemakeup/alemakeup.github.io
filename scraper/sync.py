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

    productos = {}
    for n, cat in enumerate(categorias, 1):
        pagina, total_paginas = 1, 1
        while pagina <= total_paginas:
            params = {
                "negocio": negocio, "pagina": pagina, "porPagina": m["por_pagina"],
                "filtro": "", "smart": "false", "ref": "false",
            }
            body = get_json(f"{m['api']}/market/products/{cat['_id']}", params)["body"]
            total_paginas = body.get("pagTotal") or 0
            for p in body.get("data", []):
                productos.setdefault(p["_id"], p)
            pagina += 1
            time.sleep(m["pausa_segundos"])
        print(f"  [{n}/{len(categorias)}] {cat['descripcion']:<35} total: {len(productos)}")
    return list(productos.values())


def precio_venta(p, cfg):
    pc = cfg["precios"]
    costo = p.get("preciomayor") or p.get("precio") or 0
    if costo <= 0:
        return costo, 0
    paso = pc["redondear_a"] or 1
    venta = math.ceil(costo * (1 + pc["margen_porcentaje"] / 100) / paso) * paso
    detal = p.get("precio") or 0
    if pc.get("no_superar_precio_detal_mayorista") and costo < detal < venta:
        venta = detal
    return costo, venta


def grupo_de(categoria_norm, reglas):
    for clave, grupo in reglas:
        if clave in categoria_norm:
            return grupo
    return "Otros"


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


def main():
    ap = argparse.ArgumentParser(description="Sincroniza el catálogo del mayorista.")
    ap.add_argument("--sin-fotos", action="store_true", help="no descargar fotos")
    args = ap.parse_args()

    cfg = cargar_config()
    excluir = [normalizar(x) for x in cfg["categorias"]["excluir_que_contengan"]]
    marcas = [(m, [normalizar(k) if k.strip() == k else " " + normalizar(k) + " " for k in ks])
              for m, ks in cfg.get("marcas", {}).items()]
    reglas = sorted(
        ((normalizar(k), g) for g, claves in cfg["categorias"]["grupos"].items() for k in claves),
        key=lambda x: -len(x[0]),
    )

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

        cats = [c for c in p.get("categories", []) if not c.get("smart")]
        cats = [c for c in cats if not any(x in normalizar(c["descripcion"]) for x in excluir)]
        if cats:
            cat = cats[0]["descripcion"]
            grupo = grupo_de(normalizar(cat), reglas)
            categoria = titulo_bonito(cat)
        else:
            grupo, categoria = "Otros", "Otros"

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
            "producto": p.get("title", "").strip(),
            "categoria": categoria,
            "costo_mayorista": costo,
            "precio_detal_mayorista": p.get("precio") or 0,
            "precio_alemakeup": venta,
            "ganancia": venta - costo,
        })

    orden_grupos = list(cfg["categorias"]["grupos"].keys())
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
    orden = list(cfg["categorias"]["grupos"].keys()) + ["Otros"]
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
    (DIR_DATA / "store.js").write_text(
        "window.TIENDA = " + json.dumps(cfg["tienda"], ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    with open(REPORTE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(reporte[0].keys()) if reporte else ["producto"], delimiter=";")
        w.writeheader()
        w.writerows(sorted(reporte, key=lambda r: r["producto"]))

    caros = sum(1 for r in reporte if r["precio_alemakeup"] > r["precio_detal_mayorista"] > 0)
    print(f"\nListo: {len(productos)} productos publicados.")
    print(f"  Catálogo:  {DIR_DATA / 'products.js'}")
    print(f"  Reporte:   {REPORTE}  (privado, con costos)")
    if caros:
        print(f"  Aviso: {caros} productos quedan más caros que el precio detal del propio mayorista.")
        print("         Puedes activar 'no_superar_precio_detal_mayorista' en config.json.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelado.")
