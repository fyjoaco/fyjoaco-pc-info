import platform
import psutil
import cpuinfo
import socket
import getpass
import datetime
import subprocess
import re

# Intentamos importar WMI para info avanzada en Windows
try:
    import wmi
    w = wmi.WMI()
    is_windows = True
except ImportError:
    w = None
    is_windows = False

def get_system_info():
    return (f"Equipo: {platform.node()}\n"
            f"Usuario: {getpass.getuser()}\n"
            f"Sistema Operativo: {platform.system()} {platform.release()} ({platform.version()})\n"
            f"Arquitectura: {platform.machine()}")

def get_cpu_info():
    cpu = cpuinfo.get_cpu_info()
    freq = psutil.cpu_freq()
    return (f"Nombre: {cpu.get('brand_raw')}\n"
            f"Núcleos físicos: {psutil.cpu_count(logical=False)}\n"
            f"Hilos: {psutil.cpu_count(logical=True)}\n"
            f"Frecuencia actual: {freq.current:.2f} MHz")

def get_ram_info():
    mem = psutil.virtual_memory()
    ram_total_gb = round(mem.total / (1024**3), 2)
    ram_free_percent = mem.available * 100 / mem.total
    detalles = ""
    if is_windows:
        try:
            mem_modules = w.Win32_PhysicalMemory()
            tipos = set()
            velocidades = set()
            fabricantes = set()
            capacidades = []
            MEMORY_TYPE_MAP = {
                20: "DDR",
                21: "DDR2",
                24: "DDR3",
                26: "DDR4",
            }
            for mod in mem_modules:
                tipos.add(mod.MemoryType)
                velocidades.add(mod.Speed)
                fabricantes.add(mod.Manufacturer.strip())
                capacidades.append(round(int(mod.Capacity) / (1024**3), 2))
            tipos_str = ", ".join(MEMORY_TYPE_MAP.get(t, str(t)) for t in tipos)
            velocidades_str = ", ".join(str(s) + " MHz" for s in velocidades)
            fabricantes_str = ", ".join(fabricantes)
            capacidades_str = ", ".join(str(c) + " GB" for c in capacidades)
            detalles = (f"Tipo Memoria: {tipos_str}\n"
                        f"Velocidades: {velocidades_str}\n"
                        f"Fabricantes: {fabricantes_str}\n"
                        f"Módulos y capacidades: {capacidades_str}\n")
        except Exception:
            pass
    return (f"Total instalado: {ram_total_gb} GB\n"
            f"Disponible: {round(mem.available / (1024**3), 2)} GB ({ram_free_percent:.1f}%)\n"
            f"{detalles}")

def get_disks_info():
    report = []
    if is_windows:
        try:
            for disk in w.Win32_DiskDrive():
                tipo = disk.InterfaceType
                modelo = disk.Model.strip()
                fabricante = disk.Manufacturer.strip() if disk.Manufacturer else "Desconocido"
                tam_gb = round(int(disk.Size) / (1024**3), 2) if disk.Size else "N/D"
                report.append(f"Disco: {modelo}")
                report.append(f"  Fabricante: {fabricante}")
                report.append(f"  Capacidad: {tam_gb} GB")
                report.append(f"  Tipo conexión: {tipo}")
                for part in w.Win32_DiskPartition():
                    if part.DiskIndex == disk.Index:
                        try:
                            usage = psutil.disk_usage(part.DeviceID)
                            report.append(f"  Partición: {part.DeviceID} - {part.Name}")
                            report.append(f"    Total: {round(usage.total/(1024**3),2)} GB")
                            report.append(f"    Usado: {round(usage.used/(1024**3),2)} GB")
                            report.append(f"    Libre: {round(usage.free/(1024**3),2)} GB")
                        except Exception:
                            pass
        except Exception:
            report.append("Error al obtener discos.")
    else:
        report.append("Detección de discos no soportada.")
    return "\n".join(report)

def get_gpu_info():
    report = []
    if is_windows:
        try:
            for gpu in w.Win32_VideoController():
                name = gpu.Name.strip()
                mem = int(gpu.AdapterRAM) / (1024**2) if gpu.AdapterRAM else 0
                driver = getattr(gpu, "DriverVersion", "N/D")
                tipo = "Integrada" if "intel" in name.lower() else "Dedicada"
                report.append(f"GPU: {name}")
                report.append(f"  Memoria dedicada: {round(mem)} MB")
                report.append(f"  Driver: {driver}")
                report.append(f"  Tipo: {tipo}")
        except Exception:
            report.append("Error al obtener GPU.")
    else:
        report.append("Detección de GPU no soportada.")
    return "\n".join(report)

def diagnostico_rapido():
    report = []
    mem = psutil.virtual_memory()
    if mem.available * 100 / mem.total < 20:
        report.append(f"⚠️ RAM disponible baja: {round(mem.available / (1024**3), 2)} GB (<20%)")
    for disk in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            gb_libres = usage.free / (1024**3)
            porcentaje_libre = usage.free * 100 / usage.total
            if gb_libres < 10 or porcentaje_libre < 10:
                report.append(f"⚠️ Poco espacio en disco: {disk.device} - {round(gb_libres,2)} GB libres ({round(porcentaje_libre,2)}%)")
        except PermissionError:
            pass
    battery = psutil.sensors_battery()
    if battery:
        if battery.percent < 20:
            report.append(f"⚠️ Batería baja: {battery.percent}%")
    else:
        report.append("No hay batería detectada o no es laptop.")
    return "\n".join(report) if report else "No hay alertas críticas."

def get_network_info():
    report = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    wifi_ssid = None
    for iface in addrs:
        if is_windows and ("wi-fi" in iface.lower() or "wireless" in iface.lower()):
            speed = stats[iface].speed if iface in stats else 0
            try:
                netsh_output = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True)
                ssid_match = re.search(r'SSID\s*:\s*(.+)', netsh_output)
                if ssid_match:
                    wifi_ssid = ssid_match.group(1).strip()
                    report.append(f"WiFi: {iface}")
                    report.append(f"  SSID: {wifi_ssid}")
                    report.append(f"  Velocidad: {speed} Mbps")
            except Exception:
                pass
        elif is_windows and ("ethernet" in iface.lower() or "eth" in iface.lower()):
            speed = stats[iface].speed if iface in stats else 0
            report.append(f"Ethernet: {iface}")
            report.append(f"  Velocidad: {speed} Mbps")
    return "\n".join(report) if report else "No se detectó conexión WiFi o Ethernet activa."

def get_bios_info():
    report = []
    if is_windows:
        try:
            bios_list = w.Win32_BIOS()
            for bios in bios_list:
                release_date = bios.ReleaseDate
                fecha_formateada = (f"{release_date[6:8]}/{release_date[4:6]}/{release_date[0:4]}"
                                    if release_date else "N/D")
                report.append(f"Fabricante BIOS: {bios.Manufacturer.strip()}")
                report.append(f"Versión BIOS: {bios.SMBIOSBIOSVersion.strip()}")
                report.append(f"Fecha de lanzamiento: {fecha_formateada}")
                report.append(f"Descripción: {bios.Description.strip()}")
        except Exception:
            report.append("Error al obtener info de BIOS.")
    else:
        report.append("Información de BIOS no soportada.")
    return "\n".join(report)

def generar_informe():
    secciones = [
        ("🖥️ SISTEMA", get_system_info()),
        ("🔍 CPU", get_cpu_info()),
        ("🧠 RAM", get_ram_info()),
        ("💾 DISCOS", get_disks_info()),
        ("🎮 GPU", get_gpu_info()),
        ("🧪 DIAGNÓSTICO RÁPIDO", diagnostico_rapido()),
        ("🖧 RED", get_network_info()),
        ("🖥️ BIOS", get_bios_info()),
    ]

    contenido = "=== INFORME DE HARDWARE ===\n\n"

    for titulo, texto in secciones:
        contenido += f"=== {titulo} ===\n"
        contenido += texto.strip() + "\n\n"

    contenido += f"Informe generado el {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    nombre_archivo = f"informe_{platform.node().upper().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    print(f"✅ Informe generado: {nombre_archivo}")

if __name__ == "__main__":
    print("⏳ Generando informe, por favor espere...\n")
    generar_informe()
    print("\n✅ Informe generado correctamente.")
    input("Presione Enter para salir...")


#Para ejecutarlo:
#python inf-PC.py
