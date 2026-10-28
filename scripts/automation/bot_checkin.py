#!/usr/bin/env python3
"""
Bot de automatización para Check-in en Android (ReDroid)
Interactúa con el contenedor Redroid vía ADB, valida que el GPS físico esté activo
y ejecuta las acciones de check-in en la SuperApp correspondiente.
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# Parámetros por defecto para Workbeat
ADB_HOST = os.getenv("ADB_HOST", "127.0.0.1")
ADB_PORT = os.getenv("ADB_PORT", "5555")
TARGET_PACKAGE = os.getenv("TARGET_PACKAGE", "com.workbeatmobile")
TARGET_ACTIVITY = os.getenv("TARGET_ACTIVITY", "com.superappworkbeat.MainActivity")

def run_adb(cmd: list) -> str:
    full_cmd = ["adb", "-s", f"{ADB_HOST}:{ADB_PORT}"] + cmd
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando ADB: {' '.join(full_cmd)}")
        print(f"Stderr: {e.stderr}")
        return ""

def connect_device():
    print(f"--> Conectando a Redroid vía ADB en {ADB_HOST}:{ADB_PORT}...")
    subprocess.run(["adb", "connect", f"{ADB_HOST}:{ADB_PORT}"], capture_output=True)
    time.sleep(2)
    
    devices = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    if f"{ADB_HOST}:{ADB_PORT}" not in devices:
        print(f"ERROR: No se pudo conectar con el dispositivo en {ADB_HOST}:{ADB_PORT}")
        sys.exit(1)
    print("✓ Conectado a Redroid exitosamente.")

def verify_gps_status():
    print("--> Verificando estado del proveedor de ubicación (Location Provider)...")
    dumpsys = run_adb(["shell", "dumpsys", "location"])
    
    # Redroid con GPS por hardware no reporta 'mock'
    if "gps" in dumpsys.lower():
        print("✓ Proveedor GPS habilitado en el sistema Android.")
    else:
        print("⚠ Advertencia: No se detecta proveedor GPS activo en dumpsys. Verifica la configuración de ttyACM0.")

def wake_and_unlock():
    print("--> Despertando pantalla y desbloqueando...")
    run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
    time.sleep(1)
    # Swipe hacia arriba para desbloquear
    run_adb(["shell", "input", "swipe", "360", "1000", "360", "300", "300"])
    time.sleep(1)

def launch_app():
    print(f"--> Iniciando aplicación: {TARGET_PACKAGE}...")
    run_adb(["shell", "am", "start", "-n", f"{TARGET_PACKAGE}/{TARGET_ACTIVITY}"])
    time.sleep(5)  # Espera para que la app cargue y consulte la ubicación real del GPS

def take_screenshot(tag="checkin"):
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_path = f"/sdcard/screen_{timestamp}.png"
    local_path = f"screenshots/{tag}_{timestamp}.png"
    
    run_adb(["shell", "screencap", "-p", remote_path])
    subprocess.run(["adb", "-s", f"{ADB_HOST}:{ADB_PORT}", "pull", remote_path, local_path], capture_output=True)
    run_adb(["shell", "rm", remote_path])
    print(f"✓ Captura guardada en: {local_path}")
    return local_path

def perform_checkin():
    print("--> Ejecutando acción de check-in...")
    # NOTA: Ajustar coordenadas (x, y) de acuerdo a los botones de la aplicación objetivo
    # Ejemplo: Botón "Check-in" en (360, 800)
    # run_adb(["shell", "input", "tap", "360", "800"])
    
    # Capturar pantalla previa
    take_screenshot("pre_checkin")
    
    # Simular tap o evento (descomentar y ajustar coordenadas exactas)
    # time.sleep(2)
    # run_adb(["shell", "input", "tap", "360", "800"])
    # time.sleep(3)
    
    # Capturar pantalla posterior
    take_screenshot("post_checkin")
    print("✓ Proceso de check-in finalizado.")

def main():
    print(f"=== INICIANDO ROBOT DE CHECK-IN ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    connect_device()
    verify_gps_status()
    wake_and_unlock()
    launch_app()
    perform_checkin()
    print("=== FIN DEL PROCESO ===")

if __name__ == '__main__':
    main()
