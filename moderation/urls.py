from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path(
        "report/<str:target_type>/<int:target_id>/",
        views.create_report,
        name="create_report",
    ),
    path("queue/", views.report_queue, name="report_queue"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path(
        "reports/<int:pk>/action/",
        views.take_action,
        name="take_action",
    ),
    path("history/", views.action_history, name="action_history"),
]