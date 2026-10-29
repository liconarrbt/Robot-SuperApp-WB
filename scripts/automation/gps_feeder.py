#!/usr/bin/env python3
"""
Puente GPS físico (VK-162 u-blox) -> Android ReDroid
Lee las coordenadas en tiempo real desde gpsd (/dev/ttyACM0).
Cuando el GPS obtiene FIX satelital (3D), inyecta automáticamente la latitud y longitud
al proveedor de ubicación de Android vía LocationService.
Si aún está sincronizando satélites, utiliza las coordenadas reportadas por NMEA ($GPRMC/$GPGGA)
o coordenadas de respaldo manual.
"""

import sys
import time
import socket
import json
import argparse
import subprocess

# Forzar flush de salida estándar para visualización en tiempo real
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

DEFAULT_DEVICE = "localhost:5555"

def run_adb(cmd: list, device: str = None) -> str:
    base = ["adb"]
    if device:
        base += ["-s", device]
    try:
        res = subprocess.run(base + cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

def inject_location(lat: float, lon: float, device: str = DEFAULT_DEVICE):
    """Inyecta coordenadas en Android LocationManager"""
    run_adb([
        "shell", "am", "start-foreground-service", "--user", "0",
        "-n", "io.appium.settings/.LocationService",
        "--es", "longitude", str(lon),
        "--es", "latitude", str(lat)
    ], device)

def parse_nmea_coords(line: str):
    """Extrae latitud y longitud de sentencias NMEA $GPRMC o $GPGGA."""
    parts = line.strip().split(',')
    sentence_type = parts[0]
    try:
        if sentence_type in ['$GPRMC', '$GNRMC'] and len(parts) > 6:
            lat_raw, lat_dir, lon_raw, lon_dir = parts[3], parts[4], parts[5], parts[6]
            if lat_raw and lon_raw:
                lat = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                if lat_dir == 'S': lat = -lat
                lon = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                if lon_dir == 'W': lon = -lon
                return lat, lon
        elif sentence_type in ['$GPGGA', '$GNGGA'] and len(parts) > 5:
            lat_raw, lat_dir, lon_raw, lon_dir = parts[2], parts[3], parts[4], parts[5]
            if lat_raw and lon_raw:
                lat = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                if lat_dir == 'S': lat = -lat
                lon = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                if lon_dir == 'W': lon = -lon
                return lat, lon
    except (ValueError, IndexError):
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Puente GPS VK-162 hacia ReDroid")
    parser.add_argument("-s", "--device", default=DEFAULT_DEVICE, help="Serial ADB (ej. localhost:5555)")
    parser.add_argument("--lat", type=float, help="Latitud de respaldo manual")
    parser.add_argument("--lon", type=float, help="Longitud de respaldo manual")
    parser.add_argument("--once", action="store_true", help="Inyectar una sola vez y salir")
    parser.add_argument("--timeout", type=int, default=10, help="Segundos máximos de espera para modo --once (default: 10s)")
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
        sock.settimeout(3.0)
        sock.connect(("127.0.0.1", 2947))
        # Solicitar tanto objetos JSON como sentencias NMEA brutas
        sock.sendall(b'?WATCH={"enable":true,"json":true,"nmea":true}\n')
        stream = sock.makefile()
    except Exception as e:
        print(f"ERROR: No se pudo conectar a gpsd: {e}")
        if args.lat and args.lon:
            print(f"--> Usando coordenada manual de respaldo: Lat={args.lat}, Lon={args.lon}")
            inject_location(args.lat, args.lon, args.device)
        sys.exit(1)

    print("--> Escuchando satélites y telemetría del módulo VK-162...")
    last_inject = 0
    last_coords = None
    start_time = time.time()

    try:
        while True:
            line = stream.readline()
            if not line:
                break
            line_str = line.strip()

            # 1. Parsear NMEA si la línea empieza con $
            if line_str.startswith('$'):
                coords = parse_nmea_coords(line_str)
                if coords:
                    last_coords = coords

            # 2. Parsear JSON si la línea empieza con {
            elif line_str.startswith('{'):
                try:
                    msg = json.loads(line_str)
                except Exception:
                    continue

                cls = msg.get("class")
                if cls == "SKY":
                    sats = [x for x in msg.get("satellites", []) if x.get("ss", 0) > 0]
                    used = [x for x in msg.get("satellites", []) if x.get("used")]
                    total_sats = msg.get("nSat", len(msg.get("satellites", [])))
                    print(f"\r[Satélites] Visibles: {total_sats} | Con señal: {len(sats)} | En solución 3D: {len(used)}   ", end="", flush=True)

                elif cls == "TPV":
                    mode = msg.get("mode", 0)
                    lat = msg.get("lat")
                    lon = msg.get("lon")

                    if mode >= 2 and lat and lon:
                        # Fix 2D o 3D válido
                        now = time.time()
                        if now - last_inject >= 2:
                            inject_location(lat, lon, args.device)
                            last_inject = now
                            print(f"\n[✓ FIX FÍSICO 3D INYECTADO] Lat={lat:.6f}, Lon={lon:.6f} -> ReDroid")
                            if args.once:
                                break

            # Manejo de --once si se acaba el tiempo de espera y tenemos coordenadas NMEA
            if args.once and (time.time() - start_time) > args.timeout:
                if last_coords:
                    lat, lon = last_coords
                    inject_location(lat, lon, args.device)
                    print(f"\n[✓ COORDENADAS GPS FÍSICO INYECTADAS (NMEA)] Lat={lat:.6f}, Lon={lon:.6f} -> ReDroid")
                    break
                elif args.lat and args.lon:
                    inject_location(args.lat, args.lon, args.device)
                    print(f"\n[✓ COORDENADAS DE RESPALDO INYECTADAS] Lat={args.lat:.6f}, Lon={args.lon:.6f} -> ReDroid")
                    break
                else:
                    print(f"\n⚠ Timeout ({args.timeout}s): No se obtuvo fijación 3D aún. Reintentando...")
                    break

    except KeyboardInterrupt:
        print("\nPuente GPS detenido por el usuario.")

if __name__ == "__main__":
    main()
