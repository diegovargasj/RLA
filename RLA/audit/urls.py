from django.urls import path

from audit import views

urlpatterns = [
    path('', views.landing_page_view),
    path('new/', views.create_audit_view),
    path('view/<int:audit_pk>/', views.view_audit_view)
]
