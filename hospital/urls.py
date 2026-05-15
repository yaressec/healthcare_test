from django.urls import path

from . import views

app_name = 'hospital'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/', views.api_root, name='api_root'),
    path('api/patients/', views.patient_list, name='patient_list'),
    path('api/patients/<uuid:patient_uuid>/', views.patient_detail, name='patient_detail'),
    path('api/patients/<uuid:patient_uuid>/bundle/', views.patient_bundle, name='patient_bundle'),
    path(
        'api/patients/<uuid:patient_uuid>/resource-types/',
        views.patient_resource_types,
        name='patient_resource_types',
    ),
    path(
        'api/patients/<uuid:patient_uuid>/resources/<str:resource_type>/',
        views.patient_resources,
        name='patient_resources',
    ),
]
