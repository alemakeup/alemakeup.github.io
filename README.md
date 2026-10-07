# Alemakeup Cosmetics — tienda web

Catálogo en línea con carrito. Los pedidos llegan por WhatsApp al **+57 322 819 2721**.
Los productos, las fotos y los precios se copian automáticamente del catálogo del mayorista
(Geal Makeup) y se les suma el margen de ganancia.

## Uso diario

**La tienda está publicada en https://alemakeup.github.io**

**Todos los días a las 6:00 a.m.** GitHub actualiza sola la tienda con los productos, precios y fotos del mayorista.
No hace falta tener el computador prendido.

| Quiero… | Hago… |
|---|---|
| Ver la tienda en internet | Abrir https://alemakeup.github.io |
| Ver la tienda en el computador, sin internet | Doble clic en **`Abrir tienda.bat`** |
| Cambiar el % de ganancia, datos de contacto, medios de pago… | Editar `config.json` y luego doble clic en **`Publicar cambios.bat`**; los precios nuevos salen en la próxima actualización (6 a.m.) |
| **Poner precios uno por uno** | Doble clic en **`Excel de precios.bat`** → se abre el Excel → Alexandra llena la columna amarilla **Precio Alexandra** → guardar y cerrar → doble clic en **`Subir precios.bat`** |
| Actualizar el catálogo ya, sin esperar a las 6 a.m. | En GitHub: pestaña **Actions** → **Actualizar y publicar** → **Run workflow** |
| Probar el catálogo en el computador | Doble clic en **`Actualizar catalogo.bat`** (no publica nada) |

Si GitHub no puede leer al mayorista (por ejemplo, porque su página está caída), la tienda sigue mostrando la última versión
y GitHub le envía un correo a la cuenta **alemakeup**.

> El precio publicado se debe respetar por ley. La actualización diaria evita que un cambio de precio del mayorista la haga vender a pérdida.

## config.json

**Precios de Alexandra:** el precio que ella escribe en el Excel manda sobre cualquier regla. Se guarda en
`precios_alexandra.json`, que solo tiene precios de venta. El Excel (`Precios Alemakeup.xlsx`) tiene los costos y **no se publica**.
Si el mayorista sube un costo por encima del precio de Alexandra, ese producto usa la regla del 50 % y el script lo avisa.

**Precios automáticos** (sección `precios`, para todo lo que Alexandra no haya llenado):

- `margen_porcentaje`: ganancia sobre el precio mayorista para toda la tienda (50 = +50 %).
- `redondear_a`: redondea hacia arriba el precio de venta (500 → $17.250 queda en $17.500).
- `por_marca`: reglas especiales para una marca. Ya está configurada:
  - `MILAGROS`: `"modo": "precio_publico"`, se vende al precio público fijo de la marca (igual que en Farmatodo), porque el mayorista no deja margen.
  - Para otra marca con otro margen: `"ATENEA": {"margen_porcentaje": 40}`.
- `por_producto`: precio fijo para un producto puntual. Copia el `id` de `scraper/reporte_precios.csv`: `"<id>": 25000`.

- `categorias.excluir_que_contengan`: categorías del mayorista que no se publican (por ejemplo, promociones).
- `categorias.reglas`: clasifica cada producto por palabras de su nombre (ej. "BROCHA" → Accesorios / Brochas).
  Se revisan en orden y gana la primera que coincide. Las categorías del mayorista solo se usan si el nombre no dice nada,
  porque el mayorista tiene varios productos mal ubicados.
- `categorias.correcciones`: para mover un producto puntual. Copia su `id` de `scraper/reporte_precios.csv` y escribe
  `"<id>": ["Grupo", "Subcategoría"]`, por ejemplo `"65f3b50dfa51540c701ce6ea": ["Maquillaje", "Ojos y cejas"]`.
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

## Dónde está publicada

- Tienda: https://alemakeup.github.io
- Código y actualizaciones: https://github.com/alemakeup/alemakeup.github.io (pestaña **Actions**)
- Para usar un dominio propio (ej. `alemakeup.com.co`): en el repositorio → Settings → Pages → Custom domain.

El repositorio es **público**: cualquiera puede ver el código y `config.json` (incluido el % de ganancia), pero **no** los costos
del mayorista ni las notas internas (`PENDIENTES-LEGALES.md`, `INVIMA-MARCAS.md`), que solo están en el computador.
