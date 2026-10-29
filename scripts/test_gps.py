#!/usr/bin/env python3
"""
Test VK-162 USB GPS (u-blox 7)
Lee sentencias NMEA y coordenadas en tiempo real.
Soporta conexión transparente vía daemon gpsd (puerto 2947) o puerto serie directo (/dev/ttyACM0 /dev/gps_vk162).
"""

import sys
import glob
import time
import os
import socket

# Forzar flush de salida estándar para visualización en tiempo real
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

def find_gps_port():
    candidates = [
        # Linux (Raspberry Pi / Orange Pi)
        '/dev/gps_vk162',
        '/dev/ttyACM0',
        '/dev/ttyACM1',
        '/dev/ttyUSB0',
        # macOS
        '/dev/cu.usbmodem*',
        '/dev/tty.usbmodem*',
        '/dev/cu.usbserial*'
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None

def parse_nmea_sentence(line: str):
    parts = line.strip().split(',')
    sentence_type = parts[0]
    
    # Manejar GGA (Fix data)
    if sentence_type in ['$GPGGA', '$GNGGA']:
        try:
            lat_raw = parts[2]
            lat_dir = parts[3]
            lon_raw = parts[4]
            lon_dir = parts[5]
            quality = parts[6]
            satellites = parts[7]
            hdop = parts[8]
            altitude = parts[9]
            
            if lat_raw and lon_raw:
                lat_deg = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                if lat_dir == 'S':
                    lat_deg = -lat_deg
                
                lon_deg = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                if lon_dir == 'W':
                    lon_deg = -lon_deg

                fix_str = "FIX 3D ACTIVO" if int(quality) > 0 else "Buscando satélites (Sin Fix)"
                return (
                    f"[{sentence_type}] Coordenadas: {lat_deg:.6f}, {lon_deg:.6f} | "
                    f"Altitud: {altitude}m | Satélites: {satellites} | HDOP: {hdop} | Estado: {fix_str}"
                )
            else:
                return f"[{sentence_type}] Satélites en seguimiento: {satellites} (Esperando datos de posición...)"
        except (ValueError, IndexError):
            pass
            
    # Manejar RMC (Recommended minimum)
    elif sentence_type in ['$GPRMC', '$GNRMC']:
        try:
            status = parts[2]  # A=Active/Valid, V=Void/Invalid
            lat_raw = parts[3]
            lat_dir = parts[4]
            lon_raw = parts[5]
            lon_dir = parts[6]
            speed_knots = parts[7] if len(parts) > 7 and parts[7] else "0.0"
            speed_kmh = float(speed_knots) * 1.852

            if lat_raw and lon_raw:
                lat_deg = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                if lat_dir == 'S': lat_deg = -lat_deg
                lon_deg = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                if lon_dir == 'W': lon_deg = -lon_deg
                pos_str = f" | Posición: {lat_deg:.6f}, {lon_deg:.6f}"
            else:
                pos_str = ""

            if status == 'A':
                return f"[{sentence_type}] Señal: VÁLIDA (Fix confirmado){pos_str} | Velocidad: {speed_kmh:.2f} km/h"
            else:
                return f"[{sentence_type}] Señal: Sincronizando satélites...{pos_str}"
        except (IndexError, ValueError):
            pass

    return None

def read_via_gpsd():
    """Conecta a gpsd en localhost:2947 para evitar colisión de puertos."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(('127.0.0.1', 2947))
        sock.sendall(b'?WATCH={"enable":true,"nmea":true}\n')
        f = sock.makefile()
        print("--> Conectado mediante servicio gpsd (puerto 2947).")
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith('$'):
                parsed = parse_nmea_sentence(line)
                if parsed:
                    print(parsed)
        return True
    except Exception:
        return False

def read_gps_serial(port: str):
    """Lectura serie directa si gpsd no está activo."""
    print(f"--> Abriendo puerto serie: {port}...")
    try:
        import serial
        ser = serial.Serial(port, baudrate=9600, timeout=1.0)
        print("--> Conectado mediante pySerial.")
        while True:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if not line:
                continue
            parsed = parse_nmea_sentence(line)
            if parsed:
                print(parsed)
    except Exception as e:
        print(f"ERROR abriendo puerto serie: {e}")
        print("Tip: Si gpsd está corriendo, ejecuta: sudo systemctl stop gpsd gpsd.socket")

def main():
    print(f"==================================================")
    print(f"  Test de Diagnóstico GPS VK-162 (u-blox 7)")
    print(f"==================================================")

    # 1. Probar primero si gpsd está escuchando
    if read_via_gpsd():
        return

    # 2. Si no hay gpsd, intentar puerto directo
    port = sys.argv[1] if len(sys.argv) > 1 else find_gps_port()
    if not port:
        print("ERROR: No se encontró ningún puerto serie para el GPS.")
        sys.exit(1)

    print(f"Dispositivo detectado: {port}")
    try:
        read_gps_serial(port)
    except KeyboardInterrupt:
        print("\nPrueba finalizada por el usuario.")

if __name__ == '__main__':
    main()
