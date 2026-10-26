from django.urls import path

from . import views

app_name = "earnings"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("withdraw/", views.withdrawal_request, name="withdraw"),
    path(
        "withdrawals/review/",
        views.withdrawal_review_list,
        name="withdrawal_review_list",
    ),
    path(
        "withdrawals/review/<int:pk>/",
        views.withdrawal_review,
        name="withdrawal_review",
    ),
    path(
        "transactions/<int:pk>/complete/",
        views.complete_earning_transaction,
        name="complete_earning",
    ),
]