#!/usr/bin/env python3
"""
Test VK-162 USB GPS (u-blox 7)
Lee sentencias NMEA desde el puerto serie USB e imprime la posición en tiempo real.
"""

import sys
import glob
import time
import serial

def find_gps_port():
    candidates = ['/dev/gps_vk162', '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    for dev in candidates:
        matches = glob.glob(dev)
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
            altitude = parts[9]
            
            if lat_raw and lon_raw:
                lat_deg = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                if lat_dir == 'S':
                    lat_deg = -lat_deg
                
                lon_deg = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                if lon_dir == 'W':
                    lon_deg = -lon_deg

                fix_str = "Con Fix 3D" if int(quality) > 0 else "Buscando satélites (Sin Fix)"
                return f"[{sentence_type}] Lat: {lat_deg:.6f}, Lon: {lon_deg:.6f}, Alt: {altitude}m, Satélites: {satellites} ({fix_str})"
            else:
                return f"[{sentence_type}] Satélites en seguimiento: {satellites} (Esperando datos de posición...)"
        except (ValueError, IndexError):
            pass
            
    # Manejar RMC (Recommended minimum)
    elif sentence_type in ['$GPRMC', '$GNRMC']:
        try:
            status = parts[2]  # A=Active/Valid, V=Void/Invalid
            if status == 'A':
                return f"[{sentence_type}] Estado: Válido (Fix confirmado)"
            else:
                return f"[{sentence_type}] Estado: Buscando señal..."
        except IndexError:
            pass

    return None

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_gps_port()
    baudrate = 9600
    
    if not port:
        print("ERROR: No se encontró ningún puerto serie para el GPS (/dev/ttyACM* o /dev/ttyUSB*).")
        print("Asegúrate de conectar el VK-162 vía USB a la Orange Pi.")
        sys.exit(1)

    print(f"--> Abriendo puerto serie {port} a {baudrate} baudios...")
    try:
        ser = serial.Serial(port, baudrate=baudrate, timeout=1.0)
    except Exception as e:
        print(f"Error al abrir el puerto {port}: {e}")
        print("Sugerencia: Ejecuta con 'sudo' o añade tu usuario al grupo 'dialout'.")
        sys.exit(1)

    print("Leyendo datos NMEA del VK-162. Presiona Ctrl+C para salir.\n")
    try:
        while True:
            raw_line = ser.readline()
            if not raw_line:
                continue
            line = raw_line.decode('ascii', errors='replace').strip()
            
            parsed = parse_nmea_sentence(line)
            if parsed:
                print(f"\r{parsed}", flush=True)
            elif line.startswith('$'):
                # Imprimir sentencia en bruto si aún no hay fix
                # print(f"Raw: {line}")
                pass
    except KeyboardInterrupt:
        print("\nLectura detenida por el usuario.")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
