from django.urls import path

from audit import views

urlpatterns = [
    path('', views.LandingPageView.as_view()),
    path('new/', views.CreateAuditView.as_view()),
    path('view/<int:audit_pk>/', views.AuditView.as_view())
]
