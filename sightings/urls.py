from django.urls import path
from .views import SightingInsightsView, SightingListCreateView

urlpatterns = [
    path("sightings/", SightingListCreateView.as_view(), name="sighting-list"),
    path("insights/", SightingInsightsView.as_view(), name="sighting-insights"),
]
