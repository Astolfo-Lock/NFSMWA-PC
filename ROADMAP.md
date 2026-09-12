# Roadmap de NFSMWA-PC

El objetivo es ejecutar la versión Android x86 de *Need for Speed: Most Wanted* como un proceso Win32 mediante una capa de compatibilidad, sin Android, emuladores, WSL ni máquinas virtuales.

## Estado general

La experiencia principal sin conexión está completa y permite jugar, guardar progreso y utilizar teclado, ratón o mando. Los servicios de Internet de la versión Android no forman parte del proyecto.

## Prioridades actuales

1. **Sincronización vertical real.** Revisar la ruta de presentación y ofrecer un VSync fiable, verificable y correctamente sincronizado con la frecuencia del monitor.
2. **Navegación completa con mando.** Corregir el inicio de las carreras y la selección de vehículos para que no sea necesario cambiar al ratón o al teclado cuando el modo mando está activo.
3. **Soporte para volantes.** Incorporar detección, configuración, calibración de ejes, pedales y asignación de botones. Esta función está en preparación.

## Hitos completados

- Cargador ELF32 para las cinco bibliotecas x86 originales y sus dependencias cruzadas.
- Capa de compatibilidad Bionic/POSIX, JNI y ciclo de vida Android sobre Win32.
- Adaptación SIMD en memoria sin modificar permanentemente el binario original.
- OpenGL ES 2 mediante ANGLE y Direct3D 11.
- Montaje del OBB, menús, carreras, HUD, físicas y contenido local del juego.
- Audio FMOD con salida PCM en Windows.
- Lectura, escritura y recarga del progreso local.
- Modos ventana, sin bordes y pantalla completa exclusiva.
- Resolución, calidad, MSAA y límite de FPS configurables.
- Entrada mediante teclado y ratón convertido a superficie táctil virtual.
- Soporte de mandos XInput y SDL2/HID con traducción MOGA.
- Sticks y gatillos analógicos, zona muerta y reasignación de botones.
- Launcher e importador con interfaz PyQt6.
- Importación segura del APK y OBB desde una copia legal, por ADB o desde archivos locales.

## Fuera de alcance

- Compras dentro de la aplicación.
- Servicios, telemetría y funciones dependientes de servidores de EA.
- Contenido exclusivo que requiera comunicación con esos servicios.
- Distribución del APK, OBB, bibliotecas `.so`, fuentes o cualquier otro recurso original del juego.

NFSMWA-PC no elimina verificaciones de licencia. Cada usuario debe aportar los archivos de su propia copia legal y no debe redistribuirlos.
