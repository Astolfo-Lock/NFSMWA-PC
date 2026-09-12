# Launcher

Menú PyQt6 de Need for Speed Most Wanted Android. **No incluye** OBB ni `.so`.

Esos archivos están en `NFSMWA\Motor` (el mismo contenido que `native_prototype`). Al pulsar **Jugar**, este launcher arranca `Motor\nfsmwa_runtime.exe`.

## Compilar el .exe

Desde esta carpeta:

```powershell
.\build_launcher.ps1
```

Sale en `dist\Need For Speed Most Wanted Android.exe`.

O sin compilar:

```powershell
..\..\.venv\Scripts\python.exe launcher.py
```
