# Motor

Esta carpeta es el **motor nuestro**, no el juego de EA.

Se **crea compilando** el código C de `native_runtime\win32_host` (el `build.ps1` de la raíz del port). El resultado es `nfsmwa_runtime.exe` más ANGLE/SDL2.

No van aquí:

- `*.so` (bibliotecas originales del APK)
- el `.obb` (datos del juego)
- las fuentes `.ttf`

Esos los pone el **Asset Importer** en `native_prototype` (o en `NFSMWA\Juego` si eliges esa carpeta). Ahí conviven motor + `.so` + OBB para jugar.

## Cómo se crea (en tu PC)

1. Importa tu copia legal 1.3.128 (hace falta `libapp.so` para generar la tabla SIMD).
2. En la raíz del port: `.\build.ps1`
3. Eso escribe `native_prototype\nfsmwa_runtime.exe`. Copia a esta carpeta solo el motor (sin OBB ni `.so`):

```powershell
.\sync_motor.ps1
```

Quien clone GitHub obtiene el **código/binario del host**. Cada uno importa APK/OBB por su cuenta.
