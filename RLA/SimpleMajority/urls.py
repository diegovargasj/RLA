from django.urls import path

from SimpleMajority import views

urlpatterns = [
    # path('create/', views.create_view),
    path('preliminary/<int:audit_pk>/', views.preliminary_view),
    path('recount/<int:audit_pk>/', views.recount_view),
    path('validated/<int:audit_pk>/', views.validated_view)
]
