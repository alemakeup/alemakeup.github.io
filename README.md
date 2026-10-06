# Alemakeup Cosmetics — tienda web

Catálogo en línea con carrito. Los pedidos llegan por WhatsApp al **+57 322 819 2721**.
Los productos, las fotos y los precios se copian automáticamente del catálogo del mayorista
(Geal Makeup) y se les suma el margen de ganancia.

## Uso diario

| Quiero… | Hago… |
|---|---|
| Ver la tienda | Doble clic en **`Abrir tienda.bat`** |
| Traer productos, precios y fotos nuevos del mayorista | Doble clic en **`Actualizar catalogo.bat`** (tarda 1–3 min; las fotos ya descargadas no se vuelven a bajar) |
| Cambiar el % de ganancia | Editar `margen_porcentaje` en `config.json` y volver a actualizar |
| Cambiar datos de contacto, medios de pago o tiempos de envío | Editar la sección `tienda` de `config.json` y volver a actualizar |

> Actualiza el catálogo **antes de compartir el enlace y al menos una vez por semana**.
> Por ley, el precio publicado se debe respetar, así que el precio de la página no debe quedar por debajo del costo real.

## config.json

- `precios.margen_porcentaje`: ganancia sobre el precio mayorista (50 = +50 %).
- `precios.redondear_a`: redondea hacia arriba el precio de venta (500 → $17.250 queda en $17.500).
- `precios.no_superar_precio_detal_mayorista`: si es `true`, el precio nunca supera el precio al detal del mayorista.
- `categorias.excluir_que_contengan`: categorías del mayorista que no se publican (por ejemplo, promociones).
- `categorias.grupos`: cómo se agrupan las categorías del mayorista en las categorías de la tienda.
- `imagenes.max_por_producto`: fotos por producto (más fotos ocupan más espacio).

## Archivos

```
config.json                 ← configuración (margen, contacto, categorías)
scraper/sync.py             ← script que copia el catálogo del mayorista
scraper/reporte_precios.csv ← PRIVADO: costo, precio de venta y ganancia por producto (abrir con Excel)
site/                       ← la página web (esta carpeta es la que se publica)
  index.html                ← tienda
  terminos.html             ← términos y condiciones
  privacidad.html           ← política de tratamiento de datos
  data/products.js          ← catálogo generado (no editar a mano)
  data/store.js             ← datos de la tienda generados desde config.json
  img/productos/            ← fotos descargadas
```

**Nunca publiques `scraper/reporte_precios.csv`**, porque tiene los costos del mayorista. La página publica solo los precios de venta.

## Requisitos

- Python 3.10 o más reciente. Las librerías (`requests`, `Pillow`, `truststore`) se instalan solas al usar `Actualizar catalogo.bat`,
  o manualmente con `python -m pip install -r requirements.txt`.

## Cómo funciona el script

El mayorista usa la plataforma ClickStore. El script lee las categorías y los productos desde la API pública
que usa su propia página (`elb.soyclickstore.com`), toma el precio **mayorista** (`preciomayor`), calcula el precio de venta
y descarga las fotos en formato WebP reducido. Si el mayorista cambia de plataforma, el script deja de funcionar y hay que adaptarlo.

## Publicar en internet (cuando lo decidan)

La carpeta `site/` es una página estática, así que se puede publicar gratis en Netlify (arrastrar la carpeta en app.netlify.com/drop),
Cloudflare Pages o GitHub Pages. Antes de publicar, completa los datos pendientes en `config.json` (ver `PENDIENTES-LEGALES.md`).
