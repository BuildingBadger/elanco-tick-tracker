from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Sighting(models.Model):
    reported_at = models.DateTimeField(auto_now_add=True)
    sighting_at = models.DateTimeField()
    species = models.CharField(max_length=120, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="sightings/", blank=True, null=True)
    source = models.CharField(max_length=30, default="user")
    source_id = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-sighting_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_id"],
                condition=Q(source_id__isnull=False),
                name="unique_non_null_sighting_source_id",
            )
        ]
        indexes = [
            models.Index(fields=["sighting_at"]),
            models.Index(fields=["species"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def clean(self):
        super().clean()
        if self.sighting_at and self.sighting_at > timezone.now():
            raise ValidationError({"sighting_at": "Sighting date cannot be in the future."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.species or 'Unknown tick'} at {self.location or 'unknown location'}"
