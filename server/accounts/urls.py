from django.urls import path
from . import views

urlpatterns = [
    path('google/', views.GoogleLoginView.as_view(), name='google_login'),
    path('me/', views.MeView.as_view(), name='me'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
]
