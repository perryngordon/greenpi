import os

from django.core.management.base import BaseCommand

from network.views import DEFAULT_DHCP_RANGE, _get_config, apply_ap

INSECURE_DEFAULTS = {"", "None", "password123"}


class Command(BaseCommand):
    help = (
        "Writes hostapd/dnsmasq config for the hotspot from the stored "
        "NetworkConfig and restarts them. With --from-env, first replaces an "
        "empty/default hotspot password with $GREENPI_AP_PASSWORD and moves an "
        "old 192.168.1.x DHCP range to the hotspot subnet. Used by deploy/install.sh."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from-env", action="store_true")

    def handle(self, *args, **opts):
        config = _get_config()
        if opts["from_env"]:
            env_pw = os.environ.get("GREENPI_AP_PASSWORD", "")
            if config.wifi_password in INSECURE_DEFAULTS and env_pw:
                config.wifi_password = env_pw
                self.stdout.write("Hotspot password set from GREENPI_AP_PASSWORD.")
            if config.ap_dhcp_range.startswith("192.168.1."):
                config.ap_dhcp_range = DEFAULT_DHCP_RANGE
            config.is_ap_mode = True
            config.save()
        apply_ap(config)
        self.stdout.write(f"Hotspot config written (SSID {config.ssid}, range {config.ap_dhcp_range}).")
