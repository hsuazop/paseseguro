# Residencia Segura

- Nombre y nombre corto: **Residencia Segura**.
- Dominio público: `https://residencialsegura.com` (el dominio lleva «residencial»).
- Android conserva `com.paseseguro.app` y su firma para actualizar instalaciones existentes.
- Símbolo: escudo blanco con marca de verificación celeste sobre fondo azul.
- Azul principal: `#153b63`; azul oscuro: `#0d2947`.
- Azul del portal: `#075aa6`; acento: `#2d7fb8`; fondo: `#f4f7fb`.
- Inicio: `/`, con el acceso y redirección por rol existentes de Django.
- Presentación instalada: `standalone`, con orientación libre.

El manifiesto público está en `/manifest.webmanifest`. Tanto el acceso como
las pantallas administrativas y el portal del residente lo incluyen. Los
íconos PNG de 192 y 512 píxeles, el adaptable de Android de 512 píxeles y los
íconos de navegador y Apple están en `core/static/core/brand/`.

El símbolo cabe en la zona segura circular del ícono adaptable. El SVG es la
fuente editable; `node scripts/build-app-icons.cjs` regenera los PNG con `sharp`.
Los PNG ya están generados: el servidor Django no necesita Node ni sharp.

Al abrir la aplicación, un usuario sin sesión inicia sesión. Los residentes
entran a su cuenta, los guardias al control de acceso y los tesoreros a
tesorería. Administradores y superadministradores entran al control mensual.

La aplicación usa conexión a Django. Esta preparación define su identidad y
comportamiento de inicio; la APK y su firma se generan en una etapa posterior,
cuando el dominio HTTPS y la identidad estén publicados.
