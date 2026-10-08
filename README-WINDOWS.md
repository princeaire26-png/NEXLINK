# NEXLINK Windows Applications

Build the two Python executables with `BUILD_NEXLINK_WINDOWS.ps1`.

- `NEXLINK-Server.exe`
- `NEXLINK-Client.exe`

The client bundles the Python agent. No separate agent executable is required.


## Desktop GUIs

`NEXLINK-Server.exe` opens the NEXLINK Server control panel and runs FastAPI/Uvicorn in the background. `NEXLINK-Client.exe` opens the PyQt6 client dashboard. Neither executable requires a console window.
