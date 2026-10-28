#!/usr/bin/env python3
"""
Robot de Automatización para Workbeat Mobile (SuperApp)
Flujo completo:
1. Iniciar aplicación
2. Ir a "Iniciar sesión"
3. Ingresar usuario y avanzar ("Continuar")
4. Ingresar contraseña y avanzar ("Continuar")
5. Registrar asistencia ("Registrar checada") y tomar captura
6. Ir a "Mi Perfil"
7. Cerrar sesión ("Cerrar sesión" -> "ACEPTAR")
8. Guardar capturas de auditoría en Screenshots-Temp/

Soporta configuración vía parámetros CLI y archivos .config/*.yaml
"""

import os
import re
import sys
import time
import argparse
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

# Valores por defecto
DEFAULT_PACKAGE = "com.workbeatmobile"
DEFAULT_ACTIVITY = "com.superappworkbeat.MainActivity"
DEFAULT_SCREENSHOT_DIR = "Screenshots-Temp"

def run_adb(cmd: list, device: str = None) -> str:
    base = ["adb"]
    if device:
        base += ["-s", device]
    full_cmd = base + cmd
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[ADB ERROR] {' '.join(full_cmd)}")
        print(f"Stderr: {e.stderr.strip()}")
        return ""

def load_yaml_config(path: str) -> dict:
    config = {}
    if not os.path.isfile(path):
        return config
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                config[key.strip().upper()] = val.strip().strip("'\"")
    return config

def get_connected_devices() -> list:
    out = run_adb(["devices"])
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices

def dump_ui(device: str = None) -> ET.Element:
    remote_xml = "/data/local/tmp/window_dump.xml"
    run_adb(["shell", "uiautomator", "dump", remote_xml], device)
    xml_content = run_adb(["shell", "cat", remote_xml], device)
    try:
        return ET.fromstring(xml_content)
    except Exception:
        return None

def find_element_bounds(root: ET.Element, query: str = None, class_match: str = None):
    if root is None:
        return None
    for elem in root.iter():
        text = elem.attrib.get("text", "")
        desc = elem.attrib.get("content-desc", "")
        cls = elem.attrib.get("class", "")
        bounds = elem.attrib.get("bounds", "")

        if class_match and class_match.lower() not in cls.lower():
            continue

        if query:
            q = query.lower()
            if q not in text.lower() and q not in desc.lower():
                continue

        if bounds:
            return bounds
    return None

def bounds_to_center(bounds_str: str):
    nums = list(map(int, re.findall(r"\d+", bounds_str)))
    if len(nums) == 4:
        return (nums[0] + nums[2]) // 2, (nums[1] + nums[3]) // 2
    return None

def tap_element(root: ET.Element, query: str = None, class_match: str = None, device: str = None) -> bool:
    bounds = find_element_bounds(root, query=query, class_match=class_match)
    if bounds:
        center = bounds_to_center(bounds)
        if center:
            run_adb(["shell", "input", "tap", str(center[0]), str(center[1])], device)
            return True
    return False

def wait_and_tap(query: str = None, class_match: str = None, timeout: int = 10, device: str = None) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        root = dump_ui(device)
        if tap_element(root, query=query, class_match=class_match, device=device):
            return True
        time.sleep(1)
    return False

def hide_keyboard(device: str = None):
    run_adb(["shell", "input", "keyevent", "111"], device)  # KEYCODE_ESCAPE
    time.sleep(0.5)

def type_text(text: str, device: str = None):
    # En ADB shell, la barra invertida \ debe escaparse como \\\\ para input text
    escaped = text.replace("\\", "\\\\")
    run_adb(["shell", "input", "text", f'"{escaped}"'], device)

def capture_screenshot(tag: str, screenshot_dir: str, device: str = None):
    os.makedirs(screenshot_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_path = f"/sdcard/screen_{timestamp}.png"
    local_path = os.path.join(screenshot_dir, f"{tag}_{timestamp}.png")
    run_adb(["shell", "screencap", "-p", remote_path], device)
    
    base = ["adb"]
    if device:
        base += ["-s", device]
    subprocess.run(base + ["pull", remote_path, local_path], capture_output=True)
    run_adb(["shell", "rm", remote_path], device)
    print(f"  [📸 Captura] Guardada en: {local_path}")
    return local_path

def execute_flow(user: str, password: str, delay: int, screenshot_dir: str, device: str = None):
    print("=" * 60)
    print("  INICIANDO FLUJO DE CHECK-IN WORKBEAT SUPERAPP")
    print(f"  Usuario: {user}")
    print(f"  Dispositivo: {device or 'Por defecto'}")
    print(f"  Delay post-check: {delay}s")
    print("=" * 60)

    # 1. Despertar dispositivo
    print("\n[Paso 1] Despertando dispositivo y abriendo Workbeat...")
    run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], device)
    time.sleep(1)
    run_adb(["shell", "am", "start", "-n", f"{DEFAULT_PACKAGE}/{DEFAULT_ACTIVITY}"], device)
    time.sleep(3)
    capture_screenshot("01_app_iniciada", screenshot_dir, device)

    # 2. Pantalla de Bienvenida -> "Iniciar sesión"
    print("\n[Paso 2] Localizando botón 'Iniciar sesión'...")
    if wait_and_tap(query="Iniciar sesión", timeout=6, device=device):
        print("  ✓ Clic en 'Iniciar sesión'.")
        time.sleep(2)
    else:
        print("  Ya nos encontramos en formulario o dashboard.")

    # 3. Ingresar Usuario
    print("\n[Paso 3] Ingresando usuario...")
    root = dump_ui(device)
    bounds_user = find_element_bounds(root, class_match="android.widget.EditText")
    if bounds_user:
        center = bounds_to_center(bounds_user)
        run_adb(["shell", "input", "tap", str(center[0]), str(center[1])], device)
        time.sleep(0.5)
        # Limpiar texto previo
        for _ in range(30):
            run_adb(["shell", "input", "keyevent", "67"], device)  # KEYCODE_DEL
        type_text(user, device)
        print(f"  ✓ Usuario '{user}' ingresado.")
        time.sleep(1)
        hide_keyboard(device)
        capture_screenshot("02_usuario_ingresado", screenshot_dir, device)

    # Pulsar Continuar
    print("  Avanzando al campo de contraseña...")
    wait_and_tap(query="Continuar", timeout=5, device=device)
    time.sleep(2)

    # 4. Ingresar Contraseña
    print("\n[Paso 4] Ingresando contraseña...")
    root = dump_ui(device)
    # El campo de contraseña es el EditText que dice 'Contraseña' o el segundo EditText
    bounds_pass = None
    for elem in root.iter():
        if "EditText" in elem.attrib.get("class", ""):
            text = elem.attrib.get("text", "")
            if "contraseña" in text.lower() or text == "" or "••••" in text:
                bounds_pass = elem.attrib.get("bounds")
                break
    
    if not bounds_pass:
        bounds_pass = find_element_bounds(root, query="Contraseña")

    if bounds_pass:
        center = bounds_to_center(bounds_pass)
        run_adb(["shell", "input", "tap", str(center[0]), str(center[1])], device)
        time.sleep(0.5)
        type_text(password, device)
        print("  ✓ Contraseña ingresada.")
        time.sleep(1)
        hide_keyboard(device)
        capture_screenshot("03_password_ingresado", screenshot_dir, device)

    # Pulsar Continuar (Iniciar Sesión)
    print("  Iniciando sesión...")
    wait_and_tap(query="Continuar", timeout=5, device=device)
    time.sleep(5)

    # Verificar si hubo popup de error
    root = dump_ui(device)
    if find_element_bounds(root, query="No se pudo iniciar sesión"):
        print("  ⚠ Alerta detectada, cerrando popup...")
        tap_element(root, query="OK", device=device)
        time.sleep(2)

    # 5. Dashboard -> Registrar Checada
    print("\n[Paso 5] Verificando Dashboard y registrando asistencia...")
    # Esperar a que el dashboard cargue
    for _ in range(10):
        root = dump_ui(device)
        if find_element_bounds(root, query="Registrar checada") or find_element_bounds(root, query="Explorar"):
            break
        time.sleep(1)

    capture_screenshot("04_dashboard_inicio", screenshot_dir, device)

    if wait_and_tap(query="Registrar checada", timeout=8, device=device):
        print("  ✓ ¡Botón 'Registrar checada' pulsado con éxito!")
        time.sleep(2)
        capture_screenshot("05_checada_registrada", screenshot_dir, device)
    else:
        print("  ⚠ No se localizó botón 'Registrar checada' (puede que ya se haya registrado o requiera scroll).")

    if delay > 0:
        print(f"  Esperando {delay} segundos antes de cerrar sesión (según configuración)...")
        time.sleep(delay)

    # 6. Ir a Mi Perfil
    print("\n[Paso 6] Navegando a 'Mi Perfil'...")
    if not wait_and_tap(query="Mi Perfil", timeout=8, device=device):
        # Fallback a coordenadas de la barra inferior
        run_adb(["shell", "input", "tap", "1046", "2675"], device)
    time.sleep(3)
    capture_screenshot("06_pantalla_perfil", screenshot_dir, device)

    # 7. Cerrar Sesión
    print("\n[Paso 7] Cerrando sesión...")
    if wait_and_tap(query="Cerrar sesión", timeout=8, device=device):
        print("  ✓ Clic en 'Cerrar sesión'.")
        time.sleep(2)
        # Confirmación del diálogo: "¿Desea cerrar sesión?" -> ACEPTAR
        if wait_and_tap(query="ACEPTAR", timeout=5, device=device):
            print("  ✓ Sesión cerrada con confirmación 'ACEPTAR'.")
            time.sleep(3)
            capture_screenshot("07_sesion_cerrada", screenshot_dir, device)
        else:
            print("  ⚠ No apareció diálogo de confirmación o ya se cerró.")
    else:
        print("  ⚠ No se localizó el botón 'Cerrar sesión'.")

    print("\n" + "=" * 60)
    print("  ¡FLUJO DE CHECK-IN FINALIZADO CORRECTAMENTE!")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Robot Check-in Workbeat Mobile")
    parser.add_argument("-c", "--config", type=str, default=".config/diegol.yaml", help="Ruta al archivo .yaml de configuración")
    parser.add_argument("-u", "--user", type=str, help="Usuario o código de usuario")
    parser.add_argument("-p", "--password", type=str, help="Contraseña de usuario")
    parser.add_argument("-d", "--delay", type=int, help="Segundos de espera post-checada")
    parser.add_argument("-s", "--device", type=str, help="ID/Serial del dispositivo ADB")
    parser.add_argument("--screenshot-dir", type=str, default=DEFAULT_SCREENSHOT_DIR, help="Carpeta para guardar capturas")
    args = parser.parse_args()

    # Cargar archivo de configuración
    config_path = args.config
    if not os.path.exists(config_path) and os.path.exists(f".config/{config_path}.yaml"):
        config_path = f".config/{config_path}.yaml"

    cfg = load_yaml_config(config_path) if os.path.exists(config_path) else {}

    # Prioridad: Argumento CLI > Archivo de configuración > Variable de entorno
    user = args.user or cfg.get("USER") or os.getenv("WORKBEAT_USER")
    password = args.password or cfg.get("PASS") or os.getenv("WORKBEAT_PASS")
    delay = args.delay if args.delay is not None else int(cfg.get("SCREENSHOT_DELAY", 5))
    screenshot_dir = args.screenshot_dir

    if not user or not password:
        print("ERROR: Debe proporcionar usuario y contraseña.")
        print(f"Uso: python3 {sys.argv[0]} --config .config/diegol.yaml")
        print(f"O:   python3 {sys.argv[0]} -u 'USUARIO' -p 'PASSWORD'")
        sys.exit(1)

    devices = get_connected_devices()
    if not devices:
        print("ERROR: No hay dispositivos Android conectados por ADB.")
        print("Ejecuta 'adb devices' para verificar tu teléfono o contenedor ReDroid.")
        sys.exit(1)

    device = args.device or devices[0]
    execute_flow(user=user, password=password, delay=delay, screenshot_dir=screenshot_dir, device=device)

if __name__ == "__main__":
    main()
