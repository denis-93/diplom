from django.urls import path
from .views import (
    PartnerUpdate,
    LoginAccount,
    RegisterAccount,
    ProductInfoView,
    BasketView,
    ContactView,
    OrderView,
    PartnerOrdersView,
    CategoryView,
    ShopView
)

app_name = 'backend'

urlpatterns = [
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),
    path('partner/orders', PartnerOrdersView.as_view(), name='partner-orders'),
    path('user/login', LoginAccount.as_view(), name='user-login'),
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('user/basket', BasketView.as_view(), name='user-basket'),
    path('user/contact', ContactView.as_view(), name='user-contact'),
    path('user/orders', OrderView.as_view(), name='user-orders'),
    path('product', ProductInfoView.as_view(), name='product-info'),
    path('category', CategoryView.as_view(), name='category'),
    path('shop', ShopView.as_view(), name='shop')
]