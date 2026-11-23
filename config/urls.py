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
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from config.views import home, preview
from accounts.views import me, change_password, login_view, logout_view, people, person_detail
from sensors.views import get_sensor_list, configure_sensor, mock_sensor_readings, get_sensor_history, climate
from network.views import network_config, wifi_survey
from wiki.views import wiki_list, wiki_page, wiki_history
from blog.views import blog_list, blog_post, photo_upload
from almanac.views import almanac_month, almanac_day, almanac_events, almanac_event

urlpatterns = [
    path('api/wiki/', wiki_list),
    path('api/wiki/<slug:slug>/', wiki_page),
    path('api/wiki/<slug:slug>/history/', wiki_history),
    path('api/blog/', blog_list),
    path('api/blog/<int:post_id>/', blog_post),
    path('api/photos/', photo_upload),
    path('api/preview/', preview),
    path('api/almanac/month/', almanac_month),
    path('api/almanac/day/<str:day>/', almanac_day),
    path('api/almanac/events/', almanac_events),
    path('api/almanac/events/<int:event_id>/', almanac_event),
    # Photos live on the data drive (MEDIA_ROOT). Low traffic, so Django serves them.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('', home),
    path('api/climate/', climate),
    path('api/me/', me),
    path('api/me/password/', change_password),
    path('api/login/', login_view),
    path('api/logout/', logout_view),
    path('api/people/', people),
    path('api/people/<int:user_id>/', person_detail),
    path('admin/', admin.site.urls),
    path('api/sensors/', get_sensor_list),
    path('api/sensors/configure/', configure_sensor),
    path('api/sensors/<str:sensor_id>/readings/', mock_sensor_readings),
    path('api/sensors/<str:sensor_id>/history/', get_sensor_history),
    path('api/network/', network_config),
    path('api/network/survey/', wifi_survey),
]
