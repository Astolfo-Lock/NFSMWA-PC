# NFSMWA-PC

**NFSMWA-PC** permite ejecutar en Windows la versión Android x86 de *Need for Speed: Most Wanted* mediante una capa de compatibilidad nativa.

Aunque suele describirse como un port, técnicamente no reescribe el juego para PC: `nfsmwa_runtime.exe` carga las bibliotecas x86 originales, adapta las funciones Android/Bionic necesarias a Win32 y traduce OpenGL ES 2 a Direct3D 11 mediante ANGLE. No utiliza Android, emuladores, WSL ni una máquina virtual.

> [!IMPORTANT]
> Este repositorio no contiene el APK, el OBB, las bibliotecas `.so`, las fuentes ni otros recursos originales de Electronic Arts. Para utilizar NFSMWA-PC necesitas una copia legal y compatible de *Need for Speed: Most Wanted* para Android, versión **1.3.128** (`com.ea.games.nfs13_row`). El importador prepara esos archivos localmente desde tu propia copia.

## Estado actual

La experiencia principal del juego está disponible de forma completa sin conexión, incluyendo carreras, progreso, audio, guardado local y los menús del juego.

La capa de compatibilidad no tiene acceso a Internet ni implementa los servicios en línea de la versión Android. Por ello, no funcionan las compras de moneda, el contenido exclusivo dependiente de servidores ni otras funciones vinculadas a los servicios de EA.

### Funciones disponibles

- Ejecución nativa como proceso Win32 x86.
- Renderizado OpenGL ES 2 mediante ANGLE y Direct3D 11.
- Audio del mezclador FMOD original con salida en Windows.
- Lectura del OBB y guardado local del progreso.
- Modos ventana, ventana sin bordes y pantalla completa exclusiva.
- Resolución, calidad gráfica, MSAA y límite de FPS configurables.
- Teclado y ratón, con el ratón traducido a la pantalla táctil virtual.
- Mandos Xbox mediante XInput.
- Mandos PlayStation, Switch y genéricos mediante SDL2/HID.
- Emulación de entrada MOGA, sticks analógicos, gatillos, zona muerta y reasignación de botones.
- Importador gráfico desarrollado con Python y PyQt6.

### Limitaciones conocidas

- La opción de sincronización vertical existe, pero su comportamiento todavía no se considera una implementación de VSync completamente fiable.
- Con el modo mando aún puede ser necesario usar ratón o teclado para iniciar una carrera y seleccionar un vehículo.
- El soporte para volantes está en preparación.
- Las funciones que necesitan Internet o servicios de EA no están disponibles.

Consulta [ROADMAP.md](ROADMAP.md) para conocer el estado de las tareas pendientes.

## Contenido del proyecto

| Carpeta | Función |
| --- | --- |
| `Importer/` | Valida una copia legal del juego y extrae únicamente las bibliotecas x86 y fuentes necesarias; también copia el OBB intacto. |
| `Launcher/` | Interfaz PyQt6 para configurar vídeo, rendimiento y mandos antes de iniciar el juego. |
| `Motor/` | Capa de compatibilidad Win32, ANGLE, SDL2 y archivos auxiliares propios del proyecto. |

Los recursos originales importados se guardan localmente dentro de `Motor/`. Sus extensiones están excluidas mediante `.gitignore` y no deben publicarse ni redistribuirse.


## Requisitos

- Windows con compatibilidad para aplicaciones x86.
- GPU y controladores compatibles con Direct3D 11.
- Una copia legal de *Need for Speed: Most Wanted* para Android **1.3.128**:
  - APK de `com.ea.games.nfs13_row`.
  - `main.1003128.com.ea.games.nfs13_row.obb`.
- Python 3.10 para ejecutar o compilar el importador y el launcher desde el código fuente.
- Un cable USB y ADB son opcionales; también puedes seleccionar el APK y el OBB desde el disco.

## Preparar el juego

Desde PowerShell, crea el entorno del importador:

```powershell
cd Importer
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m asset_importer
```

En el importador:

1. Selecciona la carpeta `Motor` del proyecto como destino.
2. Importa el juego desde un teléfono conectado mediante ADB o selecciona el APK y el OBB guardados en el PC.
3. Espera a que el importador confirme **Paquete completo listo para jugar**.

El teléfono se utiliza solo para lectura mediante `adb pull`. El importador no instala, desinstala ni modifica aplicaciones en el dispositivo. En Android 11 o posterior puede ser necesario copiar manualmente el APK y el OBB al PC debido a las restricciones de acceso a `Android/obb`.

## Ejecutar

Después de preparar `Motor`, puedes iniciar el launcher desde el código fuente:

```powershell
cd Launcher
..\Importer\.venv\Scripts\python.exe launcher.py
```

También puedes compilar los ejecutables localmente con:

```powershell
& '.\Launcher\Compilar launcher.bat'
& '.\Importer\Compilar importer.bat'
```

Los ejecutables resultantes quedan en las carpetas `dist` correspondientes. Esas compilaciones locales no se versionan en Git.

## Controles

El coche acelera automáticamente, igual que en la versión móvil.

| Entrada | Acción |
| --- | --- |
| `A` / Flecha izquierda | Girar progresivamente a la izquierda |
| `D` / Flecha derecha | Girar progresivamente a la derecha |
| `S` / Flecha abajo | Frenar mientras se mantiene pulsado |
| `Shift` + `A`/`D` | Derrapar |
| `Espacio` | Nitro |
| `Escape` | Atrás o pausa |
| Ratón | Tocar, mantener y arrastrar sobre la pantalla virtual |
| `Alt+F4` / cerrar ventana | Cerrar el juego ordenadamente |

Para usar un mando, abre **MANDO** en el launcher. Allí puedes activar el soporte, seleccionar el dispositivo, ajustar la zona muerta y reasignar los botones. La configuración se guarda localmente en `controller.ini`.

## Desarrollo y créditos

- Desarrollo de la capa de compatibilidad, herramientas e integración realizado por **ChatGPT 5.6 Sol**, usando los niveles de razonamiento **High** y **Extra High**.
- **Grok** se encargó de la interfaz visual del launcher.

## Aviso legal

Este es un proyecto independiente y no oficial. No está afiliado, patrocinado ni respaldado por Electronic Arts. *Need for Speed*, *Need for Speed: Most Wanted* y sus recursos pertenecen a sus respectivos propietarios.

NFSMWA-PC no elimina verificaciones de licencia ni distribuye el contenido original del juego. Cada usuario es responsable de utilizar archivos obtenidos de una copia adquirida legalmente.
