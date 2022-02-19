from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views import (
    PartnerViewSet,
    LoginAccount,
    RegisterAccount,
    ProductInfoViewSet,
    BasketViewSet,
    ContactViewSet,
    OrderViewSet,
    CategoryViewSet,
    ShopViewSet
)

app_name = 'backend'
router = DefaultRouter()
router.register(r'shops', ShopViewSet, basename='Shop')
router.register(r'categories', CategoryViewSet, basename='Category')
router.register(r'products', ProductInfoViewSet, basename='ProductInfo')
router.register(r'user/orders', OrderViewSet, basename='Order')
router.register(r'user/contacts', ContactViewSet, basename='Contact')
router.register(r'user/basket', BasketViewSet, basename='Bascet')
router.register(r'partners', PartnerViewSet, basename='Partner')

urlpatterns = [
    path('user/login', LoginAccount.as_view(), name='user-login'),
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('schema', SpectacularAPIView.as_view(), name='schema'),
    path('swagger', SpectacularSwaggerView.as_view(url_name='backend:schema'), name='swagger'),
    path('redoc', SpectacularRedocView.as_view(url_name='backend:schema'), name='redoc'),
    path('', include(router.urls))
]
