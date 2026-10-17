# Copias de seguridad de Sóller Ara

## Creación y descarga

El flujo **Còpia de seguretat de Sóller Ara** crea una copia cada sábado a las 05:37 UTC (07:37 en verano y 06:37 en invierno en Mallorca). GitHub puede retrasar las ejecuciones programadas. También se puede iniciar desde Actions → Còpia de seguretat de Sóller Ara → Run workflow → main → Run workflow.

https://github.com/soller-ara/soller-ara/actions/workflows/backup.yml

Al terminar, abrir la ejecución y descargar el archivo de la sección Artifacts o el enlace de su resumen. Las copias se conservan 90 días; una descarga guardada en un disco externo permite conservarlas independientemente de GitHub. Una copia almacenada solo en el mismo servicio no protege frente a la pérdida de acceso a ese servicio.

El flujo solo lee el repositorio y guarda un archivo de Actions. No publica noticias, no contacta con Meta, no modifica datos, secretos ni la programación de las fuentes. Los archivos temporales se crean fuera de la carpeta del sitio.

## Contenido y verificación

- `soller-ara.bundle`: historial y referencias Git anunciadas por el servidor, incluidas ramas y etiquetas.
- `archivos-actuales.zip`: archivos versionados de la rama predeterminada en el momento de la copia, incluidos datos publicados, fuentes, reglas sociales, automatizaciones y código del Worker.
- `referencias.txt` y `commit.txt`: referencias y versión exacta guardada.
- `repositorio.json`: metadatos del repositorio que permite leer el token automático; no es una exportación de todos los ajustes de GitHub.
- `manifiesto.json`: fecha, ejecución, alcance y resultado de verificación.
- `SHA256SUMS.txt`: sumas de comprobación de los archivos.

Antes de subirla, el flujo verifica el bundle, lo recupera en un repositorio Git vacío, compara todas las referencias y HEAD, comprueba los objetos con `git fsck` y genera un archivo desde la versión recuperada. Esto valida la recuperación del repositorio; no prueba una reinstalación completa de GitHub Pages, Cloudflare y Meta.

## Recuperación local sin cambiar producción

Instalar Git y descomprimir la descarga. Desde esa carpeta:

```bash
git clone soller-ara.bundle Soller-Ara-recuperada
cd Soller-Ara-recuperada
git fsck --full
```

Para recuperar también todas las referencias en un repositorio espejo independiente:

```bash
git clone --mirror soller-ara.bundle Soller-Ara-recuperada.git
git --git-dir=Soller-Ara-recuperada.git fsck --full
```

Restaurar primero en un repositorio nuevo. Después configurar Pages, permisos y entornos, y comprobar el sitio y la administración antes de habilitar las automatizaciones. Mantener desactivados los envíos sociales hasta verificar la continuidad de `data/social_publish_log.json` y el estado real de Meta: restaurar un registro antiguo puede provocar repeticiones.

## Datos externos que necesitan una copia separada

Esta es una copia del repositorio, no una copia completa de las cuentas de servicio. No contiene:

- Valores de secretos de GitHub Actions ni secretos del Worker. No se exportan ni se imprimen en este flujo.
- Ajustes privados de GitHub: Pages, Actions, permisos, protecciones, entornos, variables y acceso a secretos. Guardar un inventario separado de estos ajustes.
- Configuración activa de Cloudflare: Worker, variables, secretos, rutas y Web Analytics. El código y `worker/wrangler.toml` están en los archivos, pero no representan necesariamente todos los cambios realizados desde el panel.
- Configuración de la aplicación de Meta, permisos, cuentas vinculadas, identificadores y credenciales de publicación.
- Conversaciones de incidencias y pull requests, registros y artefactos de otras ejecuciones, estadísticas históricas alojadas por terceros, ni archivos fuera de Git.
- Objetos externos de Git LFS o repositorios de submódulos si se introducen en el futuro. En ese caso se debe ampliar este procedimiento.

La configuración versionada del Worker enumera `ADMIN_PASSWORD`, `SESSION_SECRET` y `GITHUB_TOKEN`, y los ajustes opcionales `CF_ANALYTICS_ACCOUNT_ID` y `CF_ANALYTICS_API_TOKEN`. Las automatizaciones sociales utilizan los secretos Meta referenciados en `.github/workflows/`. Esto es un inventario de nombres necesarios, no una confirmación de sus valores o de todos los ajustes activos del servicio.

Guardar las credenciales originales y los datos de recuperación de las cuentas en un gestor de contraseñas, separado del repositorio y de los artefactos. Si no se conservan, documentar cómo regenerarlas. No es necesario cambiarlas para crear una copia del código.
