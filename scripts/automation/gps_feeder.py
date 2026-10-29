#!/usr/bin/env python3
"""
Puente GPS físico (VK-162 u-blox) -> Android ReDroid
Lee las coordenadas en tiempo real desde gpsd (/dev/ttyACM0).
Cuando el GPS obtiene FIX satelital (3D), inyecta automáticamente la latitud y longitud
al proveedor de ubicación de Android vía LocationService.
Si aún está adquiriendo satélites, puede utilizar una coordenada de respaldo (fallback).
"""

import sys
import time
import socket
import json
import argparse
import subprocess

DEFAULT_DEVICE = "localhost:5555"

def run_adb(cmd: list, device: str = None) -> str:
    base = ["adb"]
    if device:
        base += ["-s", device]
    try:
        res = subprocess.run(base + cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        return ""

def inject_location(lat: float, lon: float, device: str = DEFAULT_DEVICE):
    """Inyecta coordenadas en Android LocationManager"""
    run_adb([
        "shell", "am", "start-foreground-service", "--user", "0",
        "-n", "io.appium.settings/.LocationService",
        "--es", "longitude", str(lon),
        "--es", "latitude", str(lat)
    ], device)

def main():
    parser = argparse.ArgumentParser(description="Puente GPS VK-162 hacia ReDroid")
    parser.add_argument("-s", "--device", default=DEFAULT_DEVICE, help="Serial ADB (ej. localhost:5555)")
    parser.add_argument("--lat", type=float, help="Latitud de respaldo manual")
    parser.add_argument("--lon", type=float, help="Longitud de respaldo manual")
    parser.add_argument("--once", action="store_true", help="Inyectar una sola vez y salir")
    args = parser.parse_args()

    print("=" * 60)
    print("  PUENTE GPS FÍSICO VK-162 -> ANDROID REDROID")
    print(f"  Dispositivo: {args.device}")
    print("=" * 60)

    # Si se especificaron coordenadas manuales directas
    if args.lat and args.lon and args.once:
        print(f"--> Inyectando coordenada manual: Lat={args.lat}, Lon={args.lon}")
        inject_location(args.lat, args.lon, args.device)
        print("✓ Coordenada inyectada en Android LocationManager.")
        return

    # Conectar a gpsd (puerto estándar 2947)
    print("--> Conectando al daemon gpsd (puerto 2947)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 2947))
        sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
        stream = sock.makefile()
    except Exception as e:
        print(f"ERROR: No se pudo conectar a gpsd: {e}")
        if args.lat and args.lon:
            print(f"--> Usando coordenada manual de respaldo: Lat={args.lat}, Lon={args.lon}")
            inject_location(args.lat, args.lon, args.device)
        sys.exit(1)

    print("--> Escuchando satélites del módulo VK-162...")
    last_inject = 0

    try:
        while True:
            line = stream.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except Exception:
                continue

            cls = msg.get("class")
            if cls == "SKY":
                sats = [x for x in msg.get("satellites", []) if x.get("ss", 0) > 0]
                used = [x for x in msg.get("satellites", []) if x.get("used")]
                print(f"\r[Satélites] Con señal: {len(sats)} | En solución 3D: {len(used)}   ", end="", flush=True)

            elif cls == "TPV":
                mode = msg.get("mode", 0)
                lat = msg.get("lat")
                lon = msg.get("lon")

                if mode >= 2 and lat and lon:
                    # Fix 2D o 3D válido
                    now = time.time()
                    if now - last_inject >= 2:  # Actualizar cada 2 segundos
                        inject_location(lat, lon, args.device)
                        last_inject = now
                        print(f"\n[✓ FIX FÍSICO INYECTADO] Lat={lat:.6f}, Lon={lon:.6f} -> ReDroid")
                        if args.once:
                            break
    except KeyboardInterrupt:
        print("\nPuente GPS detenido por el usuario.")

if __name__ == "__main__":
    main()
