from django.urls import path

from . import views

app_name = "matching"

urlpatterns = [
    path("discover/", views.discover, name="discover"),
    path("quick-pick/", views.quick_pick, name="quick_pick"),
    path("swipe/<int:pk>/", views.swipe, name="swipe"),
    path("deck/", views.deck, name="deck"),
    path("deck/feed/", views.deck_feed, name="deck_feed"),
    path("deck/swipe/<int:pk>/", views.deck_swipe, name="deck_swipe"),
    path("matches/", views.my_matches, name="matches"),
    path("matches/<int:pk>/its-a-match/", views.its_a_match, name="its_a_match"),
]
