from django.utils import timezone
from rest_framework import serializers

from .models import Sighting


class SightingSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Sighting
        fields = [
            "id",
            "reported_at",
            "sighting_at",
            "species",
            "latitude",
            "longitude",
            "location",
            "description",
            "image",
            "image_url",
            "source",
        ]
        read_only_fields = ["id", "reported_at", "source"]

    def validate_sighting_at(self, value):
        if value and value > timezone.now():
            raise serializers.ValidationError("Sighting date cannot be in the future.")
        return value

    def validate_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def validate(self, attrs):
        if not attrs.get("species") and not attrs.get("description"):
            raise serializers.ValidationError(
                "Provide a species or a description for the sighting."
            )
        return attrs

    def create(self, validated_data):
        validated_data["source"] = "user"
        return Sighting.objects.create(**validated_data)

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url
