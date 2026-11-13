from django.db import models

class NetworkConfig(models.Model):
    ssid = models.CharField(max_length=255, default="GreenPi_WiFi")
    wifi_password = models.CharField(max_length=255, default="password123")
    dns_entry = models.CharField(max_length=255, default="8.8.8.8")
    ap_dhcp_range = models.CharField(max_length=255, default="192.168.1.100-192.168.1.200")
    primary_eth_ip = models.GenericIPAddressField(default="192.168.1.1")
    wifi_client_ssid = models.CharField(max_length=255, default="None", blank=True)
    wifi_client_password = models.CharField(max_length=255, default="None", blank=True)
    local_hostname = models.CharField(max_length=255, default="greenhouse", blank=True)
    is_ap_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"NetworkConfig: {self.ssid}"
