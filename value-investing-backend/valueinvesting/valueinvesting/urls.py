"""
URL configuration for valueinvesting project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from . import views

# API-specific routes
api_urlpatterns = [
    # path("dcf/", include('dcf.urls')),
    path("key-ratios/", include('keyratios.urls')),
    # path("fmp/", include('fmp.urls')),
    # path("assetval/", include('assetvaluation.urls')),
    path("screener/", include('screener.urls')),
    path("quickfs/", include('quickfs_dj.urls')),
    path('dj-rest-auth/', include('dj_rest_auth.urls')),
    path('dj-rest-auth/google/', views.GoogleLogin.as_view(), name='google_login'),
    path("watchlist/", include('watchlist.urls')),
    path('history/', include('valuation_history.urls')),
    path("analyst-reports/", include('analyst_reports.urls')),
]

urlpatterns = [

    #keep admin at the root
    path("admin/", admin.site.urls),

    # All other routes under /api/
    path("api/", include(api_urlpatterns)),

    # path("key-ratios/", include('keyratios.urls')),
    # path("screener/", include('screener.urls')),
    # path("quickfs/", include('quickfs_dj.urls')),
    # path('dj-rest-auth/', include('dj_rest_auth.urls')),
    # path('dj-rest-auth/google/', views.GoogleLogin.as_view(), name='google_login')


]