import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

User = get_user_model()


class PeopleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser("perryn", "", "admin-pass-123")

    def post(self, url, data, client=None):
        return (client or self.client).post(url, json.dumps(data), content_type="application/json")

    def put(self, url, data, client=None):
        return (client or self.client).put(url, json.dumps(data), content_type="application/json")

    def login(self, username, password, client=None):
        return self.post("/api/login/", {"username": username, "password": password}, client)

    def add_person(self, username="corell", role="gardener"):
        self.login("perryn", "admin-pass-123")
        r = self.post("/api/people/", {"username": username, "display_name": "Corell", "role": role})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.logout()
        return r.json()

    def test_login_and_me(self):
        self.assertFalse(self.client.get("/api/me/").json()["authenticated"])
        r = self.login("Perryn", "admin-pass-123")  # login names are case-insensitive
        self.assertEqual(r.status_code, 200)
        me = self.client.get("/api/me/").json()
        self.assertTrue(me["is_staff"])
        self.assertEqual(me["user"]["role"], "admin")
        self.assertEqual(len(me["avatars"]), 16)
        self.post("/api/logout/", {})
        self.assertFalse(self.client.get("/api/me/").json()["authenticated"])

    def test_wrong_passwords_lock_the_account(self):
        for _ in range(5):
            self.assertEqual(self.login("perryn", "nope").status_code, 400)
        r = self.login("perryn", "admin-pass-123")
        self.assertEqual(r.status_code, 429)
        self.assertIn("15 minutes", r.json()["message"])

    def test_new_gardener_must_set_password_before_editing(self):
        made = self.add_person()
        temp = made["temporary_password"]
        self.assertTrue(made["person"]["must_change_password"])
        self.assertEqual(self.login("corell", temp).status_code, 200)
        me = self.client.get("/api/me/").json()
        self.assertFalse(me["can_edit"])
        self.assertEqual(self.post("/api/blog/", {"title": "Hi"}).status_code, 403)

        r = self.post("/api/me/password/", {"current": temp, "new": "short"})
        self.assertEqual(r.status_code, 400)  # Django's validators: too short
        r = self.post("/api/me/password/", {"current": temp, "new": "tomatoes-in-ward-2026"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["can_edit"])

        self.put("/api/me/", {"avatar": "ladybug", "display_name": "Corell P."})
        r = self.post("/api/blog/", {"title": "First frost", "body": "Brr"})
        self.assertEqual(r.status_code, 201, r.content)
        post = self.client.get(f"/api/blog/{r.json()['id']}/").json()
        self.assertEqual(post["author"]["name"], "Corell P.")
        self.assertEqual(post["author"]["avatar_url"], "/static/avatars/ladybug.svg")

    def test_gardener_cannot_touch_admin_things(self):
        temp = self.add_person()["temporary_password"]
        self.login("corell", temp)
        self.post("/api/me/password/", {"current": temp, "new": "tomatoes-in-ward-2026"})
        self.assertEqual(self.client.get("/api/network/").status_code, 403)
        self.assertEqual(self.client.get("/api/people/").status_code, 403)
        self.assertEqual(self.post("/api/people/", {"username": "x"}).status_code, 403)
        self.assertEqual(self.post("/api/sensors/configure/", {}).status_code, 403)
        self.assertEqual(self.put("/api/me/", {"avatar": "dragon"}).status_code, 400)

    def test_reset_disable_and_self_protection(self):
        made = self.add_person()
        uid = made["person"]["id"]
        self.login("perryn", "admin-pass-123")
        r = self.put(f"/api/people/{uid}/", {"reset_password": True})
        new_temp = r.json()["temporary_password"]
        self.assertNotEqual(new_temp, made["temporary_password"])
        self.put(f"/api/people/{uid}/", {"active": False})
        r = self.put(f"/api/people/{self.admin.id}/", {"role": "gardener"})
        self.assertEqual(r.status_code, 400)
        self.client.logout()
        self.assertEqual(self.login("corell", made["temporary_password"]).status_code, 400)
        self.assertEqual(self.login("corell", new_temp).status_code, 400)  # disabled

    def test_duplicate_and_bad_usernames(self):
        self.login("perryn", "admin-pass-123")
        self.assertEqual(self.post("/api/people/", {"username": "Bad Name!"}).status_code, 400)
        self.assertEqual(self.post("/api/people/", {"username": "perryn"}).status_code, 400)
