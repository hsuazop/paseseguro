# APK de Pase Seguro

La aplicación Android abre la web publicada mediante una Trusted Web Activity.
El proyecto está en `C:\dev\android\paseseguro`, con paquete
`com.paseseguro.app`, versión actual `1.0.1` y código de versión `2`.
Requiere Android 7 (API 24) o posterior y conexión al servidor.

## Herramientas

Node.js LTS y npm están instalados para el usuario de Windows en
`%LOCALAPPDATA%\Programs\NodeJS`, y Bubblewrap en `%APPDATA%\npm`.
Java 17 y Android SDK están en `%USERPROFILE%\.paseseguro\tools`.
Las ubicaciones exactas quedan registradas en `outputs/node-installation.json`
y `outputs/android-tools.json`.

## Firma

La clave privada está en `%USERPROFILE%\.paseseguro\signing\paseseguro.keystore`.
El alias y las contraseñas están en `signing-info.json`, dentro de esa misma
carpeta restringida. Se conserva una segunda copia de los dos archivos en
la carpeta `PaseSeguro-Firma` de Documentos. Estos archivos son privados y
quedan fuera del repositorio y del servidor de Opalstack.

El certificado público y su huella SHA-256 se pueden distribuir. El sitio sirve
`/.well-known/assetlinks.json` para vincular el paquete con su certificado.

## Compilación y actualizaciones

`scripts/build-android.cjs` compila el proyecto, alinea el APK, lo firma usando
contraseñas entregadas por variables de entorno y verifica su firma. El resultado
queda en `outputs/android/PaseSeguro-1.0.1.apk`, junto con el informe de verificación.
El script no imprime las contraseñas ni las incluye en el APK.

Para futuras versiones:

1. Conservar el mismo paquete y la misma clave de firma.
2. Aumentar `appVersionCode` y actualizar `appVersion` en `twa-manifest.json`.
3. Regenerar con `bubblewrap update --skipVersionUpgrade` y volver a compilar y firmar.
4. Verificar la firma y el funcionamiento en un teléfono Android.

Los cambios habituales de pantallas y operaciones se publican en Django.
Un cambio del contenedor, permisos, ícono, dominio o configuración Android puede
requerir una nueva APK.

La verificación técnica del archivo no sustituye una prueba instalada en un
teléfono. La instalación en un dispositivo se hace desde el APK final o con
`adb install -r app-release-signed.apk` usando las platform-tools del SDK.

## Corrección del cierre al arrancar (1.0.1)

Se reprodujo el cierre de la versión 1.0.0 en un emulador Android 16 con el APK
firmado. El registro mostró `IllegalArgumentException: Component class R.u does
not exist`, identificado en el mapa de R8 como `ManageDataLauncherActivity`.
Android Browser Helper 2.7.4 cambia el estado de ese componente al arrancar,
incluso cuando el acceso opcional a ajustes está desactivado. La plantilla de
Bubblewrap lo omitía del manifiesto en esa configuración.

`scripts/patch-android-project.cjs` lo declara desactivado y no exportado. Se
aplica al generar y antes de compilar, por lo que también permanece protegido
tras regenerar el proyecto. La firma y el paquete se conservan; la versión
1.0.1 se instala como actualización sobre la 1.0.0.

`scripts/test-android-launch.cjs` instala la APK en el emulador de pruebas,
comprueba el arranque y conserva el registro y la captura en `outputs/android`.
