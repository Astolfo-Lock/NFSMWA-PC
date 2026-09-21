from __future__ import annotations


_language = "es"


def set_language(language: str) -> None:
    global _language
    _language = "en" if language == "en" else "es"


def get_language() -> str:
    return _language


def t(spanish: str, english: str) -> str:
    return english if _language == "en" else spanish


# Messages produced by validation/ADB modules are translated at the UI boundary. This
# keeps their exception contracts stable while making every message shown by the app
# follow the selected language.
MESSAGE_PAIRS: tuple[tuple[str, str], ...] = (
    ("Sin detectar", "Not detected"),
    ("En espera", "Waiting"),
    ("Aún no se ha importado nada.", "Nothing has been imported yet."),
    ("Completado", "Completed"),
    ("Archivos locales", "Local files"),
    ("Carpeta del juego", "Game folder"),
    (
        "Ningún dispositivo ADB. Activa la depuración USB y autoriza este equipo.",
        "No ADB device. Enable USB debugging and authorize this computer.",
    ),
    (". Desbloquea el teléfono y acepta la huella RSA.", ". Unlock the phone and accept the RSA fingerprint."),
    ("No se pudo ejecutar adb", "Could not run adb"),
    ("Tiempo agotado al ejecutar", "Timed out while running"),
    ("adb falló con código", "adb failed with code"),
    ("pm path no devolvió el APK de", "pm path did not return the APK for"),
    ("No está instalado", "Not installed"),
    ("Instala Need for Speed Most Wanted 1.3.128 desde tu copia legal.", "Install Need for Speed Most Wanted 1.3.128 from your legally owned copy."),
    ("No se pudo leer la versión del paquete con pm/dumpsys.", "Could not read the package version with pm/dumpsys."),
    (" incompatible. Se requiere ", " is incompatible. Required: "),
    ("Android no permitió leer el OBB por ADB (típico en Android 11+ con almacenamiento con ámbito).", "Android did not allow ADB to read the OBB (common on Android 11+ with scoped storage)."),
    ("Copia estos archivos al PC con el explorador de archivos USB y usa", "Copy these files to the PC with the USB file browser and use"),
    ("APK de", "APK from"),
    ("OBB de", "OBB from"),
    ("Extrayendo el APK en un directorio temporal", "Extracting the APK to a temporary directory"),
    ("Extrayendo bibliotecas x86 y fuentes permitidas", "Extracting allowed x86 libraries and fonts"),
    ("Copiando el OBB intacto (sin descomprimir)", "Copying the intact OBB (without extracting it)"),
    ("Instalando archivos con respaldo de copias existentes", "Installing files while backing up existing copies"),
    ("Calculando SHA-256 de", "Calculating SHA-256 for"),
    ("El APK no incluye", "The APK does not include"),
    ("Solo aparece la variante armeabi-v7a, que este port no puede usar.", "Only the armeabi-v7a variant is present, which this port cannot use."),
    ("Se esperaba", "Expected"),
    ("El OBB debe llamarse", "The OBB must be named"),
    ("Recibido", "Received"),
    ("El OBB no contiene los datos published.1x y published.2x requeridos.", "The OBB does not contain the required published.1x and published.2x data."),
    ("CRC inválido en", "invalid CRC in"),
    (" en el archivo ZIP.", " in the ZIP file."),
    ("No parece la raíz del port nativo", "This does not appear to be the native port root"),
    ("Abre manualmente la carpeta del juego", "Open the game folder manually"),
    ("Operación cancelada.", "Operation cancelled."),
    ("Compilación cancelada.", "Build cancelled."),
    ("Acción desconocida:", "Unknown action:"),
    ("No se encontró", "Could not find"),
    ("No existe el", "The following file does not exist:"),
    ("está incompleto o vacío", "is incomplete or empty"),
    ("no es un ZIP válido (corrupto o incompleto)", "is not a valid ZIP (corrupt or incomplete)"),
    ("El APK está incompleto", "The APK is incomplete"),
    ("faltan fuentes", "fonts are missing"),
    ("Aún falta para jugar", "Still required to play"),
    ("falta", "missing"),
    ("es ARM, no x86. Se rechaza la arquitectura incorrecta.", "is ARM, not x86. The wrong architecture was rejected."),
    ("no es una biblioteca ELF x86", "is not an x86 ELF library"),
    ("máquina", "machine"),
    ("está vacío o truncado", "is empty or truncated"),
    ("El APK contiene una ruta ZIP insegura", "The APK contains an unsafe ZIP path"),
    ("El OBB contiene una ruta ZIP insegura", "The OBB contains an unsafe ZIP path"),
    ("El APK no contiene AndroidManifest.xml.", "The APK does not contain AndroidManifest.xml."),
    ("Versión incompatible", "Incompatible version"),
    ("Se requiere", "Required"),
    ("Paquete incompatible", "Incompatible package"),
    ("No se pudo confirmar", "Could not verify"),
    ("El OBB está corrupto", "The OBB is corrupt"),
    ("Ruta ZIP rechazada", "Rejected ZIP path"),
    ("Ruta ZIP fuera del destino", "ZIP path outside destination"),
    ("Falta", "Missing"),
    ("No se pudo extraer", "Could not extract"),
    ("Ningún dispositivo ADB", "No ADB device"),
    ("Ningún dispositivo", "No device"),
    ("No autorizado", "Unauthorized"),
    ("Desbloquea el teléfono y acepta la huella RSA.", "Unlock the phone and accept the RSA fingerprint."),
    ("No está instalado", "Not installed"),
    ("en el teléfono", "on the phone"),
    ("¿El juego está instalado?", "Is the game installed?"),
    ("No se pudo leer la versión del paquete", "Could not read the package version"),
    ("Se encontró la versión", "Found version"),
    ("pero este port requiere", "but this port requires"),
    ("Android no permitió leer el OBB por ADB", "Android did not allow ADB to read the OBB"),
    ("El importador no modifica el teléfono.", "The importer does not modify the phone."),
    ("Seleccionar archivos locales", "Select local files"),
    ("Transferencia ADB cancelada.", "ADB transfer cancelled."),
    ("Tiempo agotado al copiar", "Timed out while copying"),
    ("No se pudo copiar", "Could not copy"),
    ("El teléfono está unauthorized.", "The phone is unauthorized."),
    ("Desbloquéalo y acepta el diálogo", "Unlock it and accept the prompt"),
    ("¿Permitir depuración USB?", "Allow USB debugging?"),
    ("El dispositivo está offline.", "The device is offline."),
    ("Reconecta el cable USB y vuelve a detectar.", "Reconnect the USB cable and detect it again."),
    ("Estado ADB no usable", "Unusable ADB state"),
    ("Detectando dispositivos ADB", "Detecting ADB devices"),
    ("Validando APK y OBB", "Validating APK and OBB"),
    ("Paquete", "Package"),
    ("confirmado", "verified"),
    ("El OBB incluye", "The OBB includes"),
    ("Instalando recursos validados", "Installing validated assets"),
    ("Consultando paquete instalado", "Checking installed package"),
    ("APK remoto", "Remote APK"),
    ("OBB remoto", "Remote OBB"),
    ("Copiando APK desde el teléfono (solo lectura)", "Copying APK from phone (read-only)"),
    ("Copiando OBB intacto desde el teléfono (solo lectura)", "Copying intact OBB from phone (read-only)"),
    ("Android bloqueó la copia del OBB.", "Android blocked the OBB copy."),
    ("Paquete completo listo para jugar.", "Complete package ready to play."),
    ("Recursos originales importados correctamente.", "Original assets imported successfully."),
    ("Puedes ejecutar", "You can run"),
    ("si tienes el entorno de compilación.", "if you have the build environment."),
    ("Manifiesto", "Manifest"),
    ("Respaldo", "Backup"),
    ("Ejecutando", "Running"),
    ("Compilando", "Building"),
    ("Lanzando", "Launching"),
    ("terminó con código", "finished with code"),
    ("terminó correctamente.", "finished successfully."),
    ("Compilación lista", "Build complete"),
)


def translate_message(message: str, language: str | None = None) -> str:
    target = language or _language
    if target == "en":
        pairs = MESSAGE_PAIRS
    else:
        pairs = tuple((english, spanish) for spanish, english in MESSAGE_PAIRS)
    result = message
    for source, destination in pairs:
        result = result.replace(source, destination)
    return result
