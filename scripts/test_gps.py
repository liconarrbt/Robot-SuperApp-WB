#!/usr/bin/env python3
"""
Test VK-162 USB GPS (u-blox 7)
Lee sentencias NMEA desde el puerto serie USB e imprime la posición en tiempo real.
"""

import sys
import glob
import time
import os

def find_gps_port():
    candidates = [
        # macOS
        '/dev/cu.usbmodem*',
        '/dev/tty.usbmodem*',
        '/dev/cu.usbserial*',
        '/dev/tty.usbserial*',
        # Linux (Orange Pi)
        '/dev/gps_vk162',
        '/dev/ttyACM*',
        '/dev/ttyUSB*'
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
            utc_time = parts[1]
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
            speed_knots = parts[7] if len(parts) > 7 and parts[7] else "0.0"
            speed_kmh = float(speed_knots) * 1.852
            if status == 'A':
                return f"[{sentence_type}] Señal: VÁLIDA (Fix confirmado) | Velocidad: {speed_kmh:.2f} km/h"
            else:
                return f"[{sentence_type}] Señal: Buscando satélites..."
        except (IndexError, ValueError):
            pass

    return None

def read_gps_stream(port: str):
    print(f"--> Abriendo puerto GPS: {port}...")
    
    # Intentar con pyserial si está instalado, sino usar lectura nativa POSIX
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
    except ImportError:
        print("--> pySerial no instalado. Usando lectura directa POSIX (termios/os)...")
        fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
        buffer = b''
        try:
            while True:
                chunk = os.read(fd, 256)
                if not chunk:
                    time.sleep(0.05)
                    continue
                buffer += chunk
                if b'\n' in buffer:
                    lines = buffer.split(b'\n')
                    buffer = lines[-1]
                    for raw_line in lines[:-1]:
                        line = raw_line.decode('ascii', errors='replace').strip()
                        parsed = parse_nmea_sentence(line)
                        if parsed:
                            print(parsed)
        finally:
            os.close(fd)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_gps_port()
    if not port:
        print("ERROR: No se encontró ningún puerto serie para el GPS.")
        print("En Mac se espera /dev/cu.usbmodem*, en Linux /dev/ttyACM* o /dev/ttyUSB*.")
        sys.exit(1)
        
    print(f"==================================================")
    print(f"  Test de Diagnóstico GPS VK-162 (u-blox 7)")
    print(f"  Dispositivo detectado: {port}")
    print(f"==================================================")
    try:
        read_gps_stream(port)
    except KeyboardInterrupt:
        print("\nPrueba finalizada por el usuario.")

if __name__ == '__main__':
    main()
