
from django.urls import path
from .mpesa_callbacks import mpesa_callback
from . import views

app_name = "payments"

urlpatterns = [
    path("history/", views.payment_history, name="history"),
    path("history/<str:reference>/", views.payment_detail, name="detail"),
    path("manage/", views.payment_admin_list, name="admin_list"),
    path(
        "webhooks/provider/",
        views.payment_provider_callback,
        name="provider_callback",
    ),

    path("webhooks/mpesa/", mpesa_callback, name="mpesa_callback"),
    path(
    "<str:reference>/check-mpesa/",
    views.check_mpesa_status,
    name="check_mpesa_status",
),
]
