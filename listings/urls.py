from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("", views.my_listings, name="mine"),
    path("new/", views.listing_create, name="create"),
    path("<int:pk>/", views.listing_detail, name="detail"),
    path("<int:pk>/edit/", views.listing_edit, name="edit"),
    path("<int:pk>/toggle/", views.listing_toggle, name="toggle"),
    path("<int:pk>/delete/", views.listing_delete, name="delete"),
    path("photos/<int:pk>/delete/", views.listing_photo_delete, name="photo_delete"),
]
