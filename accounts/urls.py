from django.contrib.auth.views import LogoutView
from django.urls import path

from . import google, views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.CheeriLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("google/", google.google_login, name="google_login"),
    path("google/callback/", google.google_callback, name="google_callback"),
    path("verify/", views.verify_pending, name="verify_pending"),
    path("verify/resend/", views.resend_verification, name="resend_verification"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("onboarding/", views.onboarding_start, name="onboarding_start"),
    path("onboarding/<slug:step>/", views.onboarding, name="onboarding"),
    path("photos/<int:pk>/delete/", views.delete_photo, name="delete_photo"),
    path("photos/<int:pk>/main/", views.make_main_photo, name="make_main_photo"),
    path("me/", views.my_profile, name="me"),
    path("settings/", views.settings_view, name="settings"),
    path("u/<int:pk>/", views.profile_detail, name="profile"),
    path("u/<int:pk>/report/", views.report_user, name="report"),
    path("u/<int:pk>/block/", views.block_user, name="block"),
    path("u/<int:pk>/unblock/", views.unblock_user, name="unblock"),
]
