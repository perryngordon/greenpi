"""
Network configuration API.

Two radios (see deploy/README.md):
  * settings.GREENPI_AP_INTERFACE  (wlap0, Linksys AE1200) - the local
    "greenhouse" hotspot, run by hostapd + dnsmasq, unmanaged by NetworkManager.
  * settings.GREENPI_STA_INTERFACE (wlsta0, Comfast RTL8188EUS) - Wi-Fi client
    uplink (e.g. a neighbour's network), managed by NetworkManager via nmcli.

Both endpoints change the host's networking, so they require a logged-in
staff user (log in at /admin/) and normal CSRF protection.
"""
import ipaddress
import json
import subprocess

from django.conf import settings
from django.http import JsonResponse

from .models import NetworkConfig

HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.d/greenpi-ap.conf"
DEFAULT_DHCP_RANGE = "10.42.0.100-10.42.0.200"


def _staff_required(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse(
            {"status": "error", "message": "Log in at /admin/ to change network settings."},
            status=403,
        )
    return None


def _ap_ip(config):
    """The hotspot's own address: .1 of the /24 that holds the DHCP range."""
    start = config.ap_dhcp_range.split("-")[0].strip()
    net = ipaddress.ip_network(f"{start}/24", strict=False)
    return str(net.network_address + 1)


def _write_root_file(path, text, mode="644"):
    # The web app runs unprivileged; write via sudo tee (see deploy/sudoers).
    subprocess.run(["sudo", "tee", path], input=text.encode(), stdout=subprocess.DEVNULL, check=True)
    subprocess.run(["sudo", "chmod", mode, path], check=True)


def apply_ap(config):
    iface = settings.GREENPI_AP_INTERFACE
    if len(config.wifi_password) < 8:
        raise ValueError("Hotspot password must be at least 8 characters.")
    hostapd = "\n".join([
        f"interface={iface}",
        "driver=nl80211",
        f"ssid={config.ssid}",
        "hw_mode=g",
        "channel=6",
        "wmm_enabled=1",
        "auth_algs=1",
        "ignore_broadcast_ssid=0",
        "wpa=2",
        "wpa_key_mgmt=WPA-PSK",
        "rsn_pairwise=CCMP",
        f"wpa_passphrase={config.wifi_password}",
        "",
    ])
    _write_root_file(HOSTAPD_CONF, hostapd, mode="600")

    ap_ip = _ap_ip(config)
    start, end = [p.strip() for p in config.ap_dhcp_range.split("-")]
    host = config.local_hostname or "greenhouse"
    dnsmasq = "\n".join([
        f"interface={iface}",
        "bind-dynamic",  # tolerates the interface appearing after dnsmasq starts
        f"dhcp-range={start},{end},255.255.255.0,12h",
        # No default gateway: phones keep using mobile data for the internet
        # while still reaching the dashboard at the hotspot address.
        "dhcp-option=option:router",
        f"dhcp-option=option:dns-server,{ap_ip}",
        f"address=/{host}/{ap_ip}",
        f"address=/{host}.lan/{ap_ip}",
        "dhcp-authoritative",
        "",
    ])
    _write_root_file(DNSMASQ_CONF, dnsmasq)

    subprocess.run(["sudo", "ip", "addr", "replace", f"{ap_ip}/24", "dev", iface], check=True)
    if config.is_ap_mode:
        subprocess.run(["sudo", "systemctl", "restart", "hostapd", "dnsmasq"], check=True)
    else:
        subprocess.run(["sudo", "systemctl", "stop", "hostapd"], check=True)


def apply_client(config):
    iface = settings.GREENPI_STA_INTERFACE
    ssid = (config.wifi_client_ssid or "").strip()
    if not ssid or ssid == "None":
        subprocess.run(["sudo", "nmcli", "device", "disconnect", iface], check=False)
        return
    cmd = ["sudo", "nmcli", "--wait", "30", "device", "wifi", "connect", ssid, "ifname", iface]
    if config.wifi_client_password and config.wifi_client_password != "None":
        cmd += ["password", config.wifi_client_password]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "nmcli failed")


def _get_config():
    config = NetworkConfig.objects.first()
    if not config:
        config = NetworkConfig.objects.create(
            ssid="GreenPi_WiFi",
            wifi_password="",
            ap_dhcp_range=DEFAULT_DHCP_RANGE,
            wifi_client_ssid="",
            wifi_client_password="",
            local_hostname="greenhouse",
            is_ap_mode=True,
        )
    return config


def network_config(request):
    denied = _staff_required(request)
    if denied:
        return denied

    config = _get_config()

    if request.method == "GET":
        return JsonResponse({
            "ssid": config.ssid,
            "dns_entry": config.dns_entry,
            "ap_dhcp_range": config.ap_dhcp_range,
            "ap_ip": _ap_ip(config),
            "primary_eth_ip": str(config.primary_eth_ip),
            "wifi_client_ssid": config.wifi_client_ssid,
            # Never echo stored passwords back to the browser.
            "wifi_client_password_set": bool(config.wifi_client_password and config.wifi_client_password != "None"),
            "local_hostname": config.local_hostname,
            "is_ap_mode": config.is_ap_mode,
        })

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only GET and POST are allowed"}, status=405)

    data = json.loads(request.body or b"{}")
    fields = ["ssid", "wifi_password", "dns_entry", "ap_dhcp_range", "primary_eth_ip",
              "wifi_client_ssid", "wifi_client_password", "local_hostname", "is_ap_mode"]
    for field in fields:
        if field in data:
            val = data[field]
            if field in ("wifi_password", "wifi_client_password") and val == "":
                continue  # blank password field in the form = keep the current one
            if field == "is_ap_mode" and isinstance(val, str):
                val = val.lower() == "true"
            setattr(config, field, val)
    config.save()

    try:
        if {"ssid", "wifi_password", "ap_dhcp_range", "local_hostname", "is_ap_mode"} & data.keys():
            apply_ap(config)
        if {"wifi_client_ssid", "wifi_client_password"} & data.keys():
            apply_client(config)
    except Exception as e:  # report the failure to the UI instead of a bare 500
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "success"})
