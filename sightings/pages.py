from django.shortcuts import render

from .models import Sighting


SPECIES_COMMON_NAMES = {
    "Ixodes ricinus": "Sheep tick",
    "Ixodes hexagonus": "Hedgehog tick",
    "Dermacentor reticulatus": "Ornate cow tick",
    "Unknown": "Unknown species",
}


def home(request):
    species_names = (
        Sighting.objects.exclude(species="")
        .values_list("species", flat=True)
        .distinct()
        .order_by("species")
    )
    species_options = [
        {
            "value": species,
            "label": (
                f"{SPECIES_COMMON_NAMES[species]} ({species})"
                if species in SPECIES_COMMON_NAMES
                else species
            ),
        }
        for species in species_names
    ]
    return render(
        request,
        "sightings/home.html",
        {"species_options": species_options},
    )