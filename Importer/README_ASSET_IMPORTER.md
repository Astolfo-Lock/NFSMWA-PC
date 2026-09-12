# NFSMW Asset Importer

Programa independiente (Python + PyQt6) que prepara los **recursos originales** de Need for Speed Most Wanted Android **1.3.128** para este port nativo de Windows.

No es un extractor de OBB: **copia el OBB intacto** y, del APK, extrae únicamente las bibliotecas **x86** y las fuentes. El teléfono se usa **solo en lectura** (`adb pull`). Este importador no instala, no desinstala y no modifica nada en el dispositivo.

Cada usuario debe importar los archivos desde **su propia copia legal** del juego. El APK, el OBB, las `.so` y las fuentes originales **no** van dentro del ejecutable ni deben subirse al repositorio.

## Qué instala

| Origen | Destino |
| --- | --- |
| APK (contenido) | `native_analysis/apk/` |
| `lib/x86/*.so` (5 archivos) | `native_prototype/` |
| 6 fuentes Gotham/Hawaii | `native_prototype/fonts/` |
| `main.1003128.com.ea.games.nfs13_row.obb` **sin descomprimir** | `native_prototype/game_data/` |

Paquete: `com.ea.games.nfs13_row`  
Versión exigida: **1.3.128** (`versionCode` 1003128)

Tras importar distingue:

- **Recursos originales importados correctamente** — APK/OBB/`.so`/fuentes listos.
- **Paquete completo listo para jugar** — además están `nfsmwa_runtime.exe`, `libEGL.dll`, `libGLESv2.dll`, `SDL2.dll` y `simd_unaligned_addresses.bin`.

La importación **no depende** de compilar. El botón opcional **Ejecutar build.ps1** regenera el motor si cambiaste `libapp.so`.

## Requisitos

- Windows, Python 3.10 y las dependencias de `requirements.txt` (PyQt6, PyInstaller).
- Copia legal del juego 1.3.128 (APK + OBB).
- Para importar desde el teléfono: `adb.exe` **junto al programa**, en `platform-tools\` del proyecto, o en el PATH. El importador **no** descarga Platform Tools.

## Ejecutar

```powershell
.venv\Scripts\python.exe -m asset_importer
```

Compilar el EXE: doble clic en `Compilar importer.bat` (o `.\build_importer.ps1`).

Si no hay `.venv` en esta carpeta ni arriba, el script crea uno y instala PyQt6/PyInstaller. No usa rutas fijas de un PC concreto.

El ejecutable queda en `dist\NFSMW Asset Importer.exe`.

CLI (útil para pruebas, sin ventana):

```powershell
.venv\Scripts\python.exe -m asset_importer --detect
.venv\Scripts\python.exe -m asset_importer --import-local NeedForSpeedMostWanted.apk main.1003128.com.ea.games.nfs13_row.obb
```

## Conexión USB e importación desde el teléfono

1. En el teléfono: **Ajustes → Acerca del teléfono** y pulsa varias veces **Número de compilación** para activar opciones de desarrollador.
2. **Opciones de desarrollador → Depuración USB**: activada.
3. Conecta el cable USB y elige **Transferencia de archivos / MTP** si el sistema lo pide.
4. Desbloquea la pantalla. Aparece **¿Permitir depuración USB?** — marca «Siempre permitir desde este equipo» y acepta.
5. En el importador pulsa **Detectar teléfono**. Estados posibles:
   - **device**: listo.
   - **unauthorized**: acepta el diálogo RSA en el teléfono.
   - **offline**: reconecta el cable.
   - **ninguno**: revisa el controlador USB y `adb.exe`.
   - **varios**: elige el dispositivo en la lista.
6. Pulsa **Importar desde teléfono**. Se copia el APK (`pm path`) y el OBB `main.1003128.com.ea.games.nfs13_row.obb`.

### Si Android no deja leer el OBB

A partir de Android 11 el almacenamiento con ámbito suele bloquear `/sdcard/Android/obb/` por ADB. El importador lo explica y no intenta trucos sobre el teléfono.

Copia al PC, con el explorador de archivos USB:

- `NeedForSpeedMostWanted.apk` (o el APK del juego)
- `Android/obb/com.ea.games.nfs13_row/main.1003128.com.ea.games.nfs13_row.obb`

Luego usa **Seleccionar archivos locales**. La validación y la instalación son **las mismas** que con ADB.

## Carpeta del juego

Por defecto instala en `native_prototype` de la raíz del port. En la ventana puedes elegir otra ruta (**NFSMWA\\Juego**, **NFSMWA\\Motor** u otra carpeta) y **Mover actual aquí** para pasar el paquete ya importado (`.so`, OBB, fuentes y motor) sin duplicar el OBB. La elección se guarda en `nfsmw_paths.json` para que el launcher la encuentre.

## Importación local

1. **Seleccionar archivos locales**
2. Elige el APK y después el OBB.
3. Se valida, se instala con respaldo de archivos previos y se escribe `native_prototype/asset_import_manifest.json` (hashes SHA-256 informativos; no se exigen hashes conocidos de antemano).

## Seguridad

- Solo se extraen del APK los nombres exactos permitidos (cinco `.so` x86 y seis `.ttf`).
- Las rutas ZIP con `..` o absolutas se rechazan.
- No se usan las bibliotecas `armeabi-v7a`.
- El OBB no se descomprime: el runtime lo monta directamente.
- No se copian partidas, `runtime.log` ni ajustes personales del teléfono.
- Los archivos existentes se respaldan en `importer_backups\` sin borrar directorios completos.

## Pruebas

Las pruebas usan ZIP pequeños simulados. No necesitan el juego real ni un teléfono:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_asset_importer -v
```
