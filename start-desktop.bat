@echo off
title Senorita Desktop Launcher

echo Starting Senorita Desktop App (Tauri)...
echo This will automatically build and launch the Rust shell and Next.js frontend.
echo.

cd desktop
npm run tauri dev
