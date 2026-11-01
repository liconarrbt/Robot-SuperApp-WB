#!/usr/bin/env bash
set -e

echo "=== [1/6] Verificando arquitectura del sistema ==="
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "ADVERTENCIA: La arquitectura detectada es $ARCH. Se recomienda aarch64."
else
    echo "Arquitectura correcta: $ARCH"
fi

# Detectar modelo de placa
BOARD_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Desconocido")
echo "Placa detectada: $BOARD_MODEL"

echo ""
echo "=== [2/6] Configurando IPC Binder (ReDroid) ==="
# Verificar si el kernel tiene binderfs estático
BINDERFS_SUPPORTED=false
if grep -q "binder" /proc/filesystems 2>/dev/null || zgrep -q "CONFIG_ANDROID_BINDERFS=y" /proc/config.gz 2>/dev/null || grep -q "CONFIG_ANDROID_BINDERFS=y" /boot/config-$(uname -r) 2>/dev/null; then
    BINDERFS_SUPPORTED=true
fi

if [ "$BINDERFS_SUPPORTED" = true ]; then
    echo "-> Detectado soporte para BinderFS en el kernel."
    sudo mkdir -p /dev/binderfs
    if ! mountpoint -q /dev/binderfs; then
        if sudo mount -t binder binder /dev/binderfs -o max=1048576,default_mode=0666 2>/dev/null; then
            echo "✓ /dev/binderfs montado exitosamente."
        else
            echo "⚠ Intento de montaje de /dev/binderfs fallido."
            BINDERFS_SUPPORTED=false
        fi
    fi

    if [ "$BINDERFS_SUPPORTED" = true ]; then
        # Persistencia en /etc/fstab
        if ! grep -q "binder /dev/binderfs" /etc/fstab; then
            echo "binder /dev/binderfs binder default_mode=0666,nofail 0 0" | sudo tee -a /etc/fstab >/dev/null
            echo "✓ Añadida entrada persistente en /etc/fstab para binderfs."
        fi

        # Enlaces simbólicos y tmpfiles.d para /dev/binder*
        sudo ln -sf /dev/binderfs/binder /dev/binder
        sudo ln -sf /dev/binderfs/hwbinder /dev/hwbinder
        sudo ln -sf /dev/binderfs/vndbinder /dev/vndbinder
        sudo chmod 755 /dev/binderfs
        sudo chmod 666 /dev/binder* /dev/binderfs/* 2>/dev/null || true

        echo -e "L+ /dev/binder - - - - /dev/binderfs/binder\nL+ /dev/hwbinder - - - - /dev/binderfs/hwbinder\nL+ /dev/vndbinder - - - - /dev/binderfs/vndbinder" | sudo tee /etc/tmpfiles.d/binder.conf >/dev/null
        echo "✓ Reglas persistentes de systemd creadas en /etc/tmpfiles.d/binder.conf."
    fi
fi

if [ "$BINDERFS_SUPPORTED" = false ]; then
    # Fallback para módulos dinámicos binder_linux
    if modprobe binder_linux devices="binder,hwbinder,vndbinder" 2>/dev/null; then
        echo "✓ Módulo binder_linux cargado exitosamente."
        echo "binder_linux" | sudo tee /etc/modules-load.d/redroid.conf >/dev/null
        echo 'options binder_linux devices="binder,hwbinder,vndbinder"' | sudo tee /etc/modprobe.d/redroid.conf >/dev/null
    else
        echo "⚠ No se detectó binderfs activo ni módulo binder_linux precompilado."
        echo "  (Nota: Para ReDroid en este kernel se requerirá compilar o habilitar binder_linux)"
    fi
fi

# memfd / ashmem
if modprobe ashmem_linux 2>/dev/null; then
    echo "✓ Módulo ashmem_linux cargado exitosamente."
    echo "ashmem_linux" | sudo tee -a /etc/modules-load.d/redroid.conf >/dev/null
else
    echo "ℹ ashmem_linux no requerido en Linux >= 5.18 (usa memfd nativo)."
fi

echo ""
echo "=== [3/6] Verificando parámetros del kernel para Android LMKD y Cgroups ==="
CMDLINE_FILE=""
REBOOT_REQUIRED=false

# Detectar archivo de configuración de arranque según la distribución / placa
if [ -f /boot/firmware/cmdline.txt ]; then
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
elif [ -f /boot/cmdline.txt ]; then
    CMDLINE_FILE="/boot/cmdline.txt"
elif [ -f /boot/orangepiEnv.txt ]; then
    CMDLINE_FILE="/boot/orangepiEnv.txt"
elif [ -f /boot/armbianEnv.txt ]; then
    CMDLINE_FILE="/boot/armbianEnv.txt"
fi

if [ -n "$CMDLINE_FILE" ]; then
    echo "Archivo de arranque detectado: $CMDLINE_FILE"
    CURRENT_CONTENT=$(cat "$CMDLINE_FILE")

    if [[ "$CMDLINE_FILE" == *"Env.txt" ]]; then
        # Formato Orange Pi / Armbian (clave=valor, ej. extraargs=...)
        NEEDED_PARAMS="psi=1 cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1"
        if grep -q "^extraargs=" "$CMDLINE_FILE"; then
            EXTRAARGS_LINE=$(grep "^extraargs=" "$CMDLINE_FILE")
            NEW_EXTRAARGS="$EXTRAARGS_LINE"
            for param in $NEEDED_PARAMS; do
                if [[ ! "$EXTRAARGS_LINE" =~ "$param" ]]; then
                    NEW_EXTRAARGS="$NEW_EXTRAARGS $param"
                    REBOOT_REQUIRED=true
                fi
            done
            if [ "$REBOOT_REQUIRED" = true ]; then
                sudo sed -i "s|^extraargs=.*|$NEW_EXTRAARGS|" "$CMDLINE_FILE"
                echo "✓ Actualizada línea 'extraargs' en $CMDLINE_FILE: $NEW_EXTRAARGS"
            else
                echo "✓ Parámetros PSI y cgroups ya están presentes en 'extraargs'."
            fi
        else
            echo "extraargs=$NEEDED_PARAMS" | sudo tee -a "$CMDLINE_FILE" >/dev/null
            REBOOT_REQUIRED=true
            echo "✓ Añadida directiva 'extraargs=$NEEDED_PARAMS' en $CMDLINE_FILE."
        fi
    else
        # Formato Raspberry Pi cmdline.txt (una sola línea de parámetros)
        UPDATED_CMDLINE="$CURRENT_CONTENT"
        if [[ ! "$CURRENT_CONTENT" =~ "psi=1" ]]; then
            UPDATED_CMDLINE="$UPDATED_CMDLINE psi=1"
            REBOOT_REQUIRED=true
        fi
        if [[ ! "$CURRENT_CONTENT" =~ "cgroup_enable=memory" ]]; then
            UPDATED_CMDLINE="$UPDATED_CMDLINE cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1"
            REBOOT_REQUIRED=true
        fi

        if [ "$REBOOT_REQUIRED" = true ]; then
            echo "$UPDATED_CMDLINE" | sudo tee "$CMDLINE_FILE" >/dev/null
            echo "✓ Parámetros 'psi=1 cgroup_enable=memory cgroup_memory=1' añadidos a $CMDLINE_FILE."
        else
            echo "✓ Parámetros PSI y cgroups ya están configurados en $CMDLINE_FILE."
        fi
    fi

    if [ "$REBOOT_REQUIRED" = true ]; then
        echo "⚠ IMPORTANTE: Se requiere reiniciar el sistema para que el kernel active el monitor de memoria PSI y cgroups."
    fi
else
    echo "ℹ No se encontró archivo cmdline.txt o orangepiEnv.txt estándar. Si usas GRUB o U-Boot personalizado, verifica que 'psi=1 cgroup_enable=memory' estén activos."
fi

echo ""
echo "=== [4/6] Configurando reglas udev para GPS VK-162 ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULE="$SCRIPT_DIR/../configs/udev/99-vk162-gps.rules"

if [ -f "$UDEV_RULE" ]; then
    sudo cp "$UDEV_RULE" /etc/udev/rules.d/
    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger 2>/dev/null || true
    echo "✓ Reglas udev instaladas en /etc/udev/rules.d/99-vk162-gps.rules."
fi

echo ""
echo "=== [5/6] Verificando detección del módulo GPS VK-162 ==="
if ls -l /dev/ttyACM* /dev/ttyUSB* /dev/gps_vk162 2>/dev/null; then
    echo "✓ Dispositivo GPS detectado en el sistema."
    sudo chmod 666 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
else
    echo "⚠ No se detectó puerto serie de GPS. Conecta el VK-162 a un puerto USB."
fi

echo ""
echo "=== [6/6] Dependencias del Host y Docker ==="
sudo apt-get update -qq
sudo apt-get install -y -qq adb python3 python3-pip python3-venv minicom gpsd-clients curl git 2>/dev/null || true

# Verificar / instalar Docker
if ! command -v docker &> /dev/null; then
    echo "-> Docker no está instalado. Instalando Docker oficial..."
    curl -fsSL https://get.docker.com | sudo sh
    CURRENT_USER=${SUDO_USER:-$USER}
    if [ -n "$CURRENT_USER" ] && [ "$CURRENT_USER" != "root" ]; then
        sudo usermod -aG docker "$CURRENT_USER"
        echo "✓ Usuario $CURRENT_USER añadido al grupo docker."
    fi
    echo "✓ Docker instalado correctamente."
else
    echo "✓ Docker ya está instalado en el sistema."
fi

# Verificar soporte de docker compose (plugin o standalone)
if ! docker compose version &>/dev/null && ! command -v docker-compose &>/dev/null; then
    echo "-> Instalando Docker Compose plugin..."
    sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
fi

# Crear directorios requeridos por ReDroid y el bot
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/empty_xbin" "$PROJECT_ROOT/Screenshots-Temp" "$PROJECT_ROOT/.config"
chmod 755 "$PROJECT_ROOT/empty_xbin" 2>/dev/null || true

echo ""
echo "=================================================="
echo "  ¡Aprovisionamiento completado!"
if [ "$REBOOT_REQUIRED" = true ]; then
    echo "  >> Por favor ejecuta 'sudo reboot' para activar PSI en el kernel. <<"
fi
echo "=================================================="
