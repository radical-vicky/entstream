from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("", views.plan_list, name="plans"),
    path("mine/", views.my_subscriptions, name="my_subscriptions"),
    path("subscribe/<int:plan_id>/", views.subscribe, name="subscribe"),
    path(
        "cancel/<int:subscription_id>/",
        views.cancel_subscription,
        name="cancel",
    ),
]