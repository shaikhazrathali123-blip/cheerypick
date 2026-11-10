from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("unread/", views.unread_count, name="unread"),
    path("<int:pk>/", views.thread, name="thread"),
    path("<int:pk>/poll/", views.poll, name="poll"),
]
