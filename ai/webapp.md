ui should have responsive modes for small screens
ui should have a growing things feel to it in terms of color scheme and graphic devices
create a fun google style inspred splashpage

admin users and regular users

garden wiki

data display
use javascript in ui and python in backend to allow for beautiful data visualizations 
data should be exportable - csv ?


-sensors
sensors show in unconfigured mode / screen until accepted/configured 
unconfigured sensors are any that are seen on i2c bus or usb that are not in the database
click on the sensor to go into sensor view/config mode, give the sensor a name and optional description and save, now in db , accepted and configured
any metadata the sensor provides should be persisted in the sensor db object
view/config mode for uncinfigured sensors should show its metadata and have realtime display of raw data
view/config mode for configured sensors shows realtime uipdating data also but in curated fields instead of raw data 



config
- network
  ability to  config indicated wireless interface as a configurable AP, with DHCP, and dns with entry "greenhouse" that points at the home page
  if wifi interface is present  go ahead and assume ap mode enabled on it, and set SSID to greenhouse , dhcp net to 172.16.18.0/24  
  ability to  config indicated wifi interface as a client in order to allow for connecting to a greate town  network
  enable and default primary ethernet interface to 192.168.1.1 
