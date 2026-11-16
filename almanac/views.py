import calendar
import math
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db.models import Avg, Count, FloatField, Max, Min
from django.db.models.fields.json import KT
from django.db.models.functions import Cast, TruncDate
from django.http import JsonResponse
from django.utils import timezone

from blog.models import Post
from blog.views import post_summary
from config.api import bad_request, is_staff, json_body, staff_only
from config.markup import render
from sensors.models import Sensor, SensorReading

from .models import AlmanacEvent

MOON_PHASES = [  # (upper bound of astral's 0-27.99 phase value, name, emoji)
    (1.84, "New moon", "🌑"), (5.53, "Waxing crescent", "🌒"), (9.22, "First quarter", "🌓"),
    (12.91, "Waxing gibbous", "🌔"), (16.61, "Full moon", "🌕"), (20.30, "Waning gibbous", "🌖"),
    (23.99, "Last quarter", "🌗"), (27.68, "Waning crescent", "🌘"), (99, "New moon", "🌑"),
]


# --------------------------------------------------------------------------- data


def _climate_sensor():
    """The primary air sensor (first configured sensor that reports temperature)."""
    for s in Sensor.objects.filter(status="configured").order_by("id"):
        if (s.metadata or {}).get("climate") is False:
            continue
        if s.readings.filter(values__has_key="temperature_f").exists():
            return s
    return None


def _daily_climate(start, end):
    """{date: {...}} min/max/avg temperature and humidity per local day in [start, end)."""
    sensor = _climate_sensor()
    if not sensor:
        return {}
    tz = timezone.get_current_timezone()
    lo = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    hi = timezone.make_aware(datetime.combine(end, datetime.min.time()))
    rows = (
        SensorReading.objects.filter(sensor=sensor, timestamp__gte=lo, timestamp__lt=hi)
        .annotate(day=TruncDate("timestamp", tzinfo=tz),
                  t=Cast(KT("values__temperature_f"), FloatField()),
                  h=Cast(KT("values__humidity_pct"), FloatField()))
        .order_by()  # clear the model's default ordering so GROUP BY is by day only
        .values("day")
        .annotate(tmin=Min("t"), tmax=Max("t"), tavg=Avg("t"),
                  hmin=Min("h"), hmax=Max("h"), havg=Avg("h"), n=Count("id"))
    )
    r1 = lambda v: None if v is None else round(v, 1)
    return {row["day"]: {"temp_min": r1(row["tmin"]), "temp_max": r1(row["tmax"]),
                         "temp_avg": r1(row["tavg"]), "rh_min": r1(row["hmin"]),
                         "rh_max": r1(row["hmax"]), "rh_avg": r1(row["havg"]),
                         "readings": row["n"]}
            for row in rows}


def _location():
    lat, lon = settings.GREENPI_LATITUDE, settings.GREENPI_LONGITUDE
    return (lat, lon) if lat is not None and lon is not None else None


def _sun(day):
    loc = _location()
    if not loc:
        return None
    from astral import Observer
    from astral.sun import sun

    try:
        s = sun(Observer(latitude=loc[0], longitude=loc[1]), date=day,
                tzinfo=timezone.get_current_timezone())
    except ValueError:  # polar day/night; not an issue at greenhouse latitudes
        return None
    fmt = lambda t: t.strftime("%H:%M")
    length = s["sunset"] - s["sunrise"]
    return {"dawn": fmt(s["dawn"]), "sunrise": fmt(s["sunrise"]), "noon": fmt(s["noon"]),
            "sunset": fmt(s["sunset"]), "dusk": fmt(s["dusk"]),
            "daylight_minutes": round(length.total_seconds() / 60)}


def _moon(day):
    from astral import moon

    p = moon.phase(day)
    name, emoji = next((n, e) for bound, n, e in MOON_PHASES if p < bound)
    illum = round((1 - math.cos(2 * math.pi * p / 29.53)) / 2 * 100)
    return {"phase": round(p, 1), "name": name, "emoji": emoji, "illumination_pct": illum}


def _events_between(start, end):
    """{date: [event,...]} for one-off events in range plus yearly repeats."""
    out = {}
    events = list(AlmanacEvent.objects.filter(yearly=True)) + \
        list(AlmanacEvent.objects.filter(yearly=False, date__gte=start, date__lt=end))
    d = start
    while d < end:
        hits = [e for e in events if e.occurs_on(d)]
        if hits:
            out[d] = hits
        d += timedelta(days=1)
    return out


def _event_json(e, full=False):
    data = {"id": e.id, "title": e.title, "kind": e.kind, "yearly": e.yearly,
            "date": e.date.isoformat()}
    if full:
        data.update(notes=e.notes, notes_html=render(e.notes))
    return data


def _posts_between(request, start, end):
    posts = Post.objects.filter(date__gte=start, date__lt=end)
    if not is_staff(request):
        posts = posts.filter(published=True)
    out = {}
    for p in posts.order_by("date", "created_at"):
        out.setdefault(p.date, []).append(p)
    return out


# --------------------------------------------------------------------------- views


def almanac_month(request):
    today = timezone.localdate()
    try:
        y, m = map(int, (request.GET.get("month") or f"{today:%Y-%m}").split("-"))
        start = date(y, m, 1)
    except ValueError:
        return bad_request("month must be YYYY-MM")
    end = date(y + (m == 12), m % 12 + 1, 1)

    climate = _daily_climate(start, end)
    events = _events_between(start, end)
    posts = _posts_between(request, start, end)
    days = []
    for i in range((end - start).days):
        d = start + timedelta(days=i)
        sun = _sun(d)
        days.append({
            "date": d.isoformat(),
            "climate": climate.get(d),
            "sunrise": sun and sun["sunrise"], "sunset": sun and sun["sunset"],
            "moon": _moon(d),
            "events": [_event_json(e) for e in events.get(d, [])],
            "posts": [{"id": p.id, "title": p.title} for p in posts.get(d, [])],
        })
    return JsonResponse({
        "month": f"{start:%Y-%m}", "title": f"{calendar.month_name[m]} {y}",
        "first_weekday": start.weekday(),  # Monday = 0
        "today": today.isoformat(), "location_set": _location() is not None,
        "days": days, "can_edit": is_staff(request),
    })


def almanac_day(request, day):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return bad_request("date must be YYYY-MM-DD")
    nxt = d + timedelta(days=1)
    sun = _sun(d)
    prev_sun = _sun(d - timedelta(days=1))
    if sun and prev_sun:
        sun["daylight_change_minutes"] = sun["daylight_minutes"] - prev_sun["daylight_minutes"]
    return JsonResponse({
        "date": d.isoformat(),
        "climate": _daily_climate(d, nxt).get(d),
        "sun": sun, "moon": _moon(d), "location_set": _location() is not None,
        "events": [_event_json(e, full=True) for e in _events_between(d, nxt).get(d, [])],
        "posts": [post_summary(p) for p in _posts_between(request, d, nxt).get(d, [])],
        "can_edit": is_staff(request),
    })


def _apply_event(e, data):
    title = (data.get("title") or "").strip()
    if not title:
        return "An event needs a title."
    try:
        e.date = date.fromisoformat(data.get("date") or "")
    except ValueError:
        return "Date must be YYYY-MM-DD."
    kind = data.get("kind") or "note"
    if kind not in dict(AlmanacEvent.KIND_CHOICES):
        return "Unknown kind."
    e.title, e.kind = title, kind
    e.yearly = bool(data.get("yearly"))
    e.notes = data.get("notes") or ""
    return None


def almanac_events(request):
    if request.method == "GET":
        return JsonResponse({"events": [_event_json(e, full=True) for e in AlmanacEvent.objects.all()],
                             "kinds": AlmanacEvent.KIND_CHOICES})
    denied = staff_only(request)
    if denied:
        return denied
    data = json_body(request)
    if data is None:
        return bad_request("Invalid JSON.")
    e = AlmanacEvent()
    err = _apply_event(e, data)
    if err:
        return bad_request(err)
    e.save()
    return JsonResponse({"status": "success", "id": e.id}, status=201)


def almanac_event(request, event_id):
    e = AlmanacEvent.objects.filter(id=event_id).first()
    if not e:
        return JsonResponse({"error": "Not found"}, status=404)
    if request.method == "GET":
        return JsonResponse(_event_json(e, full=True))
    denied = staff_only(request)
    if denied:
        return denied
    if request.method == "DELETE":
        e.delete()
        return JsonResponse({"status": "success"})
    data = json_body(request)
    if data is None:
        return bad_request("Invalid JSON.")
    err = _apply_event(e, data)
    if err:
        return bad_request(err)
    e.save()
    return JsonResponse({"status": "success", "id": e.id})
