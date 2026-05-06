# Ako Windows Build/Installer Guide

## Build/runtime split

- Developer build must use full Python 3.12 with Tcl/Tk.
- Do not use `installer_assets\python-3.12.10-embed-amd64.zip` for PyInstaller.
- The embed zip is installer/runtime support only. It is extracted by `bootstrap_runtime.bat` under `%LOCALAPPDATA%\Ako-ai\runtime\python312` when needed.
- User runtime must not run `pip install -r requirements.txt`; `Ako-ai.exe` is already packaged by PyInstaller.

## Verification

1. Confirm full Python 3.12 + tkinter:

```powershell
py -3.12 -c "import tkinter; print('TK OK', tkinter.TkVersion)"
```

2. Remove broken build output:

```powershell
Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue
```

3. Build onefolder:

```powershell
.\build_onefolder_runtime_bootstrap.bat
```

4. Test the executable directly before creating an installer:

```powershell
.\dist\Ako-ai\Ako-ai.exe
```

5. Compile the installer only after the GUI opens:

```powershell
iscc .\installer\AkoSetup.iss
```

6. Expected installer:

```text
installer_output\AkoSetup-0.1.2.exe
```

7. On a clean test PC, uninstall existing Ako, delete old shortcuts, delete `%LOCALAPPDATA%\Ako-ai\runtime`, install the new build, then test first run and second run.
