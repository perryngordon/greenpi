from django.db import models


class AlmanacEvent(models.Model):
    """A dated almanac entry: frost dates, planting windows, tasks, notes."""

    KIND_CHOICES = [
        ("frost", "Frost"),
        ("planting", "Planting"),
        ("harvest", "Harvest"),
        ("task", "Task"),
        ("note", "Note"),
    ]

    title = models.CharField(max_length=200)
    date = models.DateField(db_index=True)
    # Repeats every year on the same month/day (e.g. average last frost).
    yearly = models.BooleanField(default=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="note")
    notes = models.TextField(blank=True)  # Markdown, may contain [[wiki links]]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "title"]

    def occurs_on(self, day):
        if self.yearly:
            return (self.date.month, self.date.day) == (day.month, day.day)
        return self.date == day

    def __str__(self):
        return f"{self.date} {self.title}{' (yearly)' if self.yearly else ''}"
