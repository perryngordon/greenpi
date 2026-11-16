"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from config.views import home, me
from sensors.views import get_sensor_list, configure_sensor, mock_sensor_readings, get_sensor_history, climate
from network.views import network_config, wifi_survey

urlpatterns = [
    path('', home),
    path('api/climate/', climate),
    path('api/me/', me),
    path('admin/', admin.site.urls),
    path('api/sensors/', get_sensor_list),
    path('api/sensors/configure/', configure_sensor),
    path('api/sensors/<str:sensor_id>/readings/', mock_sensor_readings),
    path('api/sensors/<str:sensor_id>/history/', get_sensor_history),
    path('api/network/', network_config),
    path('api/network/survey/', wifi_survey),
]
