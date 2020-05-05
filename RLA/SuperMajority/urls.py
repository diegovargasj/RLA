from django.urls import path

from SuperMajority import views

urlpatterns = [
    path('preliminary/<int:audit_pk>/', views.PreliminaryView.as_view()),
    path('recount/<int:audit_pk>/', views.RecountView.as_view()),
    path('validated/<int:audit_pk>/', views.ValidationView.as_view())
]
