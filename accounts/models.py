from django.conf import settings
from django.db import models

from .avatars import AVATAR_SLUGS


class Profile(models.Model):
    """What the app shows for a person. Role comes from User.is_staff:
    staff = admin (network, sensors, people), everyone else = gardener (content)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=60, blank=True)
    avatar = models.CharField(max_length=30, blank=True)
    # Set when an admin creates the account or resets its password: the person
    # must choose their own password before they can edit anything.
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name or self.user.get_username()


def profile_for(user):
    """The user's Profile, created on first use (older accounts predate profiles)."""
    try:
        return user.profile
    except Profile.DoesNotExist:
        avatar = AVATAR_SLUGS[(user.pk or 0) % len(AVATAR_SLUGS)]
        return Profile.objects.create(user=user, display_name=user.get_username(), avatar=avatar)
