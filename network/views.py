from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import subprocess
from .models import NetworkConfig

def configure_network(config):
    if config.is_ap_mode:
        # Hostapd configuration
        config_lines = [
            "interface=wlan0",
            "driver=nl80211",
            f"ssid={config.ssid}",
            "hw_mode=g",
            "channel=6",
            "wmm_enabled=0",
            "macaddr_acl=0",
            "auth_algs=1",
            "ignore_broadcast_ssid=0",
            "wpa=2",
            f"wpa_passphrase={config.wifi_password}",
            "wpa_key_mgmt=WPA-PSK",
            "wpa_pairwise=TKIP",
            "rsn_pairwise=CCMP"
        ]

        config_path = "/etc/hostapd/hostapd.conf"
        try:
            with open(config_path, "w") as f:
                f.write("\n".join(config_lines))
            
            subprocess.run(["sudo", "systemctl", "restart", "hostapd"], check=True)

            # Set wlan0 IP to start of DHCP range
            range_parts = config.ap_dhcp_range.split('-')
            if len(range_parts) == 2:
                start_ip = range_parts[0]
                # Assuming /24 subnet mask
                subprocess.run(["sudo", "ip", "addr", "flush", "dev", "wlan0"], check=True)
                subprocess.run(["sudo", "ip", "addr", "add", f"{start_ip}/24", "dev", "wlan0"], check=True)
                subprocess.run(["sudo", "ip", "link", "set", "wlan0", "up"], check=True)
        except Exception as e:
            print(f"Error configuring network: {e}")
    else:
        # Placeholder for wpa_supplicant / client mode configuration
        print("Configuring for client mode (wpa_supplicant)")

@csrf_exempt
def network_config(request):
    if request.method == 'GET':
        config = NetworkConfig.objects.first()
        if not config:
            config = NetworkConfig.objects.create(
                ssid="GreenPi_WiFi",
                wifi_password="password123",
                dns_entry="8.8.8.8",
                ap_dhcp_range="192.168.1.100-192.168.1.200",
                primary_eth_ip="192.168.1.1",
                wifi_client_ssid="None",
                wifi_client_password="None",
                local_hostname="greenhouse",
                is_ap_mode=False
            )
        return JsonResponse({
            "ssid": config.ssid,
            "dns_entry": config.dns_entry,
            "ap_dhcp_range": config.ap_dhcp_range,
            "primary_eth_ip": str(config.primary_eth_ip),
            "wifi_client_ssid": config.wifi_client_ssid,
            "wifi_client_password": config.wifi_client_password,
            "local_hostname": config.local_hostname,
            "is_ap_mode": config.is_ap_mode
        })
    elif request.method == 'POST':
        data = json.loads(request.body)
        config = NetworkConfig.objects.first()
        
        if not config:
            config = NetworkConfig.objects.create(
                ssid=data.get("ssid", "GreenPi_WiFi"),
                wifi_password=data.get("wifi_password", "password123"),
                dns_entry=data.get("dns_entry", "8.8.8.8"),
                ap_dhcp_range=data.get("ap_dhcp_range", "192.168.1.100-192.168.1.200"),
                primary_eth_ip=data.get("primary_eth_ip", "192.168.1.1"),
                wifi_client_ssid=data.get("wifi_client_ssid", "None"),
                wifi_client_password=data.get("wifi_client_password", "None"),
                local_hostname=data.get("local_hostname", "greenhouse"),
                is_ap_mode=data.get("is_ap_mode", False)
            )
        else:
            fields = ["ssid", "wifi_password", "dns_entry", "ap_dhcp_range", "primary_eth_ip", "wifi_client_ssid", "wifi_client_password", "local_hostname", "is_ap_mode"]
            for field in fields:
                if field in data:
                    val = data[field]
                    if field == "is_ap_mode" and isinstance(val, str):
                        val = val.lower() == 'true'
                    setattr(config, field, val)
            config.save()
        
        if "is_ap_mode" in data:
            configure_network(config)

        # DNS/DHCP Configuration Logic
        if "dns_entry" in data or "ap_dhcp_range" in data or "primary_eth_ip" in data or "local_hostname" in data:
            try:
                range_parts = config.ap_dhcp_range.split('-')
                start_ip = data.get('start_ip', range_parts[0])
                end_ip = data.get('end_ip', range_parts[1])
                dns_server = data.get('dns_server', config.dns_entry)
                gateway = data.get('gateway', config.primary_eth_ip)
                lease_time = "12h"

                config_lines = [
                    f"dhcp-range={start_ip},{end_ip},{lease_time}",
                    f"dhcp-option=option:dns-server,{dns_server}",
                    f"dhcp-option=option:router,{gateway}",
                    f"address/{config.local_hostname},{config.primary_eth_ip}",
                    "dhcp-authoritative\n"
                ]
                
                config_path = "/etc/dnsmasq.d/django-dhcp.conf"
                with open(config_path, "w") as f:
                    f.write("\n".join(config_lines))
                
                subprocess.run(["sudo", "systemctl", "restart", "dnsmasq"], check=True)
            except Exception as e:
                return JsonResponse({"status": "error", "message": str(e)}, status=500)

        return JsonResponse({"status": "success", "received_data": data})
    return JsonResponse({"status": "error", "message": "Only GET and POST requests are allowed"}, status=405
)
