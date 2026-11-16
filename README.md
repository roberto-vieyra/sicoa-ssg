# SICOA-SSG

Control de Oficios, Turnos y Alertas para la Subdirección de Servicios Generales. React + Vite + TypeScript, FastAPI, SQLAlchemy 2.0 y Pydantic v2. Operación local/LAN con SQLite; configuración alternativa para PostgreSQL.

## Inicio en Windows

Requisitos: Python 3.12 y Node.js **22.13 o posterior de la rama 22**. Ejecutar desde la raíz del repositorio:

```powershell
.\scripts\setup.ps1 -LanIp 192.168.1.73
.\scripts\run_lan.ps1 -LanIp 192.168.1.73
```

Sustituya la IP por la del equipo servidor. Abra `http://<IP_LAN>:5173` en los equipos de la misma red. Un solo proceso Uvicorn sirve la consola compilada por Vite y la API en el puerto 5173. Node 22 se utiliza para compilar y validar el frontend. La regla de entrada del firewall para 5173 debe estar autorizada por la institución. Los scripts no cambian el firewall ni desactivan TLS.

Para preparar el traslado en la laptop personal, ejecute desde la raíz:

```powershell
.\scripts\prepare_offline.ps1
git archive --format=zip -o ..\sicoa-ssg-codigo.zip HEAD
```

En la laptop institucional con Python 3.12 y Node 22, extraiga el ZIP en una carpeta nueva y copie dentro la carpeta `vendor`. Para una primera instalación con el histórico, coloque `Base.xlsx` en `data`. Desde esa carpeta ejecute:

```powershell
.\scripts\setup.ps1 -Offline -LanIp 192.168.1.73
.\scripts\run_lan.ps1 -LanIp 192.168.1.73
```

Las dependencias quedan fijadas en `requirements-lock.txt` y `frontend/package-lock.json`. Las fuentes Noto Sans y JetBrains Mono se incluyen en la compilación desde paquetes locales; no hay peticiones a Google Fonts, CDN, imágenes o servicios remotos durante la operación. El emblema SSG es un diseño local generado con Pillow, no una reproducción de un escudo nacional ni de un sello oficial de terceros.

## Cuentas iniciales

La siembra crea únicamente las cuentas ausentes. No cambia contraseñas ni roles existentes.

| Usuario | Contraseña inicial | Rol | Área |
|---|---|---|---|
| admin | SicoaSSG2026! | Administrador | SSG |
| oficialia | Oficialia2026! | Oficialia_Despachador | SSG |
| gai | GerenciaGAI2026! | Responsable_Area | GAI |
| gsa | GerenciaGSA2026! | Responsable_Area | GSA |
| auditor | Auditor2026! | Auditor | Consulta |

Administrador y Oficialía registran, importan, turnan, editan y cargan documentos. Los responsables consultan y atienden exclusivamente su área. Auditor consulta y exporta, sin modificar datos. La bitácora general está disponible para Administrador y Auditor. Todas las lecturas de documentos, reportes y expedientes respetan el mismo alcance por área.

Contraseñas almacenadas con Argon2; JWT firmado con HS256, emisor, audiencia y vencimiento. La clave JWT se toma de `JWT_SECRET` o se genera una sola vez en `data/.jwt_secret`. Preserve ese archivo junto con los datos. El token del navegador vive en `sessionStorage` y se elimina al cerrar sesión.

## Datos y sincronización

Coloque el archivo original como `data/Base.xlsx` o `Base.xlsx` en la raíz. Se importa al arrancar **solo cuando la tabla de oficios está vacía**. También puede usar Importar en la bandeja o `POST /api/oficios/import-excel` con autorización. Se procesa la hoja `CORRESPONDENCIA 2026`, encabezados en la segunda fila.

```powershell
.\scripts\post_pull_sync.ps1 -ForceSqlite -LanIp 192.168.1.73
```

El script conserva variables ajenas a su configuración, respalda `.env`, `frontend/.env.local` y `data/sicoa_ssg.db` en una carpeta con fecha dentro de `data/backups/`. SQLite se respalda con su API de backup, incluyendo datos confirmados del WAL; no se copia una base abierta a ciegas. CORS agrega las IP indicadas y localhost sin borrar orígenes previos. Sin `-ForceSqlite`, conserva la URL de base de datos existente.

`Base.xlsx`, bases, respaldos, documentos, secretos y logs están excluidos de Git. La copia original del Escritorio nunca se modifica.

Decisiones de importación:

- Se omiten las cuatro filas prenumeradas vacías SSG963–SSG966. La secuencia se inicializa con el máximo folio **válido**, de modo que la siguiente alta es SSG963.
- Las seis filas SSG209, SSG559, SSG560, SSG561, SSG566 y SSG583 conservan el texto desplazado como co-destinatario y cargo. No se interpreta como fecha.
- 24 HR se computa como un día hábil. El plazo de 7 días se representa como `FECHA_FIJA` con `plazo_dias_habiles=7`. Una fecha límite explícita tiene prioridad sobre una nota.
- Días hábiles significa lunes a viernes. No se ha supuesto un calendario de feriados. La fecha de referencia proviene de `America/Mexico_City`.
- Los turnos con varias áreas se conservan completos en `responsables_detalle` y quedan bajo coordinación SSG, hasta que Oficialía asigne el área principal.
- Los hipervínculos originales se conservan como referencias históricas; no se descargan ni se sirven rutas arbitrarias del equipo. La interfaz indica que el documento falta hasta que se carga el PDF.
- No se inventa fecha de atención para los nueve oficios históricos marcados como respondidos. La atención histórica y su referencia se conservan.
- SHA-256 identifica archivos ya importados. Una nueva importación conserva los folios existentes, informa duplicados y no sobrescribe cambios operativos.
- El folio SSG es globalmente único, conforme al esquema solicitado. `consecutivo_anual` se lleva por año; el folio global no se reinicia al cambiar de ejercicio.

El reporte de cada importación queda en `import_batches` y es consultable en `/api/oficios/importaciones`. Cada alta importada se registra en auditoría dentro de la misma transacción.

## Concurrencia y persistencia

Cada PUT/PATCH de oficios y funcionarios exige `version`. La escritura ejecuta un `UPDATE ... WHERE id = ... AND version = ...`; solo una solicitud concurrente puede ganar. La otra recibe `409` con el estado actual. Documentos y cierre con acuse también exigen versión. La auditoría y el cambio de datos se confirman juntos. Un conflicto durante la carga elimina únicamente el nuevo archivo no confirmado.

SQLite habilita `journal_mode=WAL`, `foreign_keys=ON` y espera de bloqueo. Los modelos usan tipos comunes, fechas y JSON genérico. El migrador agrega tablas, columnas con valores seguros e índices; no borra ni reemplaza tablas. Ante una columna obligatoria sin valor seguro o datos incompatibles con un índice único, se detiene para revisión en lugar de destruir o inventar datos.

Para PostgreSQL configure en `.env`:

```dotenv
DATABASE_URL=postgresql+pg8000://usuario:clave@127.0.0.1:5432/sicoa_ssg
```

No use `-ForceSqlite` con esa configuración. El cambio de URL selecciona el motor; **no copia automáticamente** datos de una base a otra. La migración de esquema es independiente de la transferencia de datos. Se usa un solo proceso API en el modo portátil; pueden conectarse varios usuarios LAN a ese proceso.

El cliente HTTP saliente central está en `backend/app/core/http_client.py`: `ssl.create_default_context()`, `trust_env=True`, HTTP/2 desactivado y tiempos 3/6/6/3 segundos. La CA corporativa debe estar en el almacén de confianza del sistema o en `SSL_CERT_FILE`/`SSL_CERT_DIR`. Referencias: [HTTPX y SSL](https://www.python-httpx.org/advanced/ssl/), [variables de entorno HTTPX](https://www.python-httpx.org/environment_variables/).

## PDFs y Excel

Los tres generadores verifican exactamente una página con MediaBox y CropBox Carta, sin rotación:

| Documento | Endpoint | Medidas |
|---|---|---|
| Volante de turno | `/api/oficios/{id}/volante-pdf` | 612 × 792 pt |
| Semáforo ejecutivo | `/api/reportes/alertas-pdf` | 792 × 612 pt |
| Hoja de entrega | `/api/reportes/acuse-entrega-pdf?ids=1,2,3` | 792 × 612 pt |

El ejecutivo prioriza 12 pendientes y muestra el número omitido y KPIs por área. La hoja de entrega admite lotes de 10; seleccione los expedientes con las casillas de la bandeja. Para lotes sucesivos la API admite `offset`. Textos que exceden el espacio se identifican con `[...]`; el expediente completo permanece en la aplicación y Excel.

La exportación Excel conserva la estructura institucional, tipos fecha, congelación de encabezados, filtro y colores del semáforo al momento del corte. Es un reporte de consulta; el respaldo de la base es la copia íntegra de co-destinatarios, versiones, auditoría, archivos y estados operativos.

## Validación

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend
Set-Location frontend
npx vitest run --pool=vmThreads
node --test tests/model.test.mjs
npm run typecheck
npm run lint -- --max-warnings=0
npm run build
npx playwright install chromium
```

Las pruebas de importación real requieren `data/Base.xlsx` o `BASE_XLSX_PATH`; fallan explícitamente si falta, no se omiten. Pytest convierte advertencias en errores. Para un entorno con TEMP restringido, use `--basetemp=work/pytest-<identificador-nuevo>` dentro del repositorio.

Para validar la paridad con un PostgreSQL de pruebas, configure `TEST_DATABASE_URL` con el controlador pg8000 y una cuenta con permiso de crear bases. Cada fixture crea y retira su propia base temporal.

Playwright inicia la aplicación compilada en una base temporal e importa `Base.xlsx`. Cierra su servidor al terminar. Desde `frontend`, después de `npm run build`, ejecute:

```powershell
# Opcional, para ejercitar HTTP de la LAN con la IPv4 de este equipo.
$env:E2E_LAN_IP='192.168.1.73'
npm run test:e2e
```

El puerto de prueba predeterminado es 5183 y se puede configurar con `E2E_PORT`. Las capturas, descargas y medidas quedan en `frontend/test-results/`. Para generar por separado los tres PDFs y el Excel con una copia temporal del libro, ejecute `.\.venv\Scripts\python.exe -m scripts.qa_artifacts` desde la raíz. Los archivos quedan en `work/qa/`.

### Resultado de la Fase 1

Las 39 pruebas del backend pasaron tanto en SQLite como con un servidor PostgreSQL. El libro real aportó 962 oficios y seis correcciones de co-destinatarios. Dos sincronizaciones consecutivas conservaron el siguiente folio `SSG963`, los archivos de configuración y la integridad de cada respaldo.

En Windows con Node 22.21.1 pasaron las siete pruebas de Vitest y las tres del modelo. La instalación con `setup.ps1 -Offline` utilizó los 43 paquetes de Python y la caché npm de `vendor`. La compilación y las verificaciones de TypeScript y ESLint terminaron sin advertencias.

Chromium probó el alta, el acuse y las descargas con una conexión HTTP de la LAN. En escritorio, tanto el viewport como el documento midieron 1440 × 900 px. En móvil, ambos midieron 390 px de ancho. Axe completó las comprobaciones de acceso, bandeja y captura en los dos tamaños. Los tres PDF descargados en cada recorrido tenían exactamente una página Carta.

## Estructura

```text
backend/app/core/       configuración, JWT y cliente HTTP
backend/app/db/         modelos, conexiones, migraciones y siembra
backend/app/services/   calendario, importación/exportación, auditoría y PDFs
backend/tests/         pruebas de datos reales, permisos y concurrencia
frontend/src/          consola, formularios, directorio y utilidades
frontend/tests/        modelo y E2E Chromium/axe
scripts/               instalación, LAN, respaldos y preparación offline
data/                  información operativa local, excluida de Git
```
