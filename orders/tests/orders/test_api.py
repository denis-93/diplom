import pytest
from django.urls import reverse
from backend.models import User


@pytest.mark.django_db
def test_create_user(api_client):
    """Тест создания пользователя"""
    url = reverse('backend:user-register')
    user = {'first_name': 'Денис',
            'last_name': 'Денисов',
            'email': 'user_test@test.ru',
            'password': '123456789qwerty!!',
            'company': 'Company_name',
            'position': 'Developer'
            }
    resp = api_client.post(url, user)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json['Status'] == True


@pytest.mark.django_db
def test_add_contact(simple_user_client):
    """Тест добавления контактов пользователя"""
    url = reverse('backend:Contact-list')
    contact = {'city': 'Москва', 'street': 'Тверская ул.', 'house': '55', 'phone': '89145555555'}
    resp = simple_user_client.post(url, contact)
    assert resp.status_code == 201


@pytest.mark.django_db
def test_get_shop(api_client, shop_factory):
    """Тест получения списка магазинов"""
    shop1 = shop_factory()
    shop2 = shop_factory()
    url = reverse('backend:Shop-list')
    resp = api_client.get(url)
    resp_json = resp.json()
    assert resp.status_code == 200
    assert len(resp_json) == 2


@pytest.mark.django_db
def test_get_category(category_factory, api_client):
    """Тест на получение категории товаров"""
    category1 = category_factory()
    category2 = category_factory()
    url = reverse('backend:Category-list')
    resp = api_client.get(url)
    resp_json = resp.json()
    assert resp.status_code == 200
    assert len(resp_json) == 2


@pytest.mark.django_db
def test_product(api_client, product_factory, category_factory, product_info_factory, shop_factory):
    """Тест на получение списка товаров"""
    category = category_factory()
    product1 = product_factory(category_id=category.id)
    product2 = product_factory(category_id=category.id)
    shop = shop_factory()
    product_info = product_info_factory(product_id=product1.id, shop_id=shop.id)
    product_info2 = product_info_factory(product_id=product2.id, shop_id=shop.id)
    url = reverse('backend:ProductInfo-list')
    resp = api_client.get(url)
    resp_json = resp.json()
    assert resp.status_code == 200
    assert len(resp_json) == 2


@pytest.mark.django_db
def test_create_order(simple_user_client, order_factory, contact_factory):
    """Тест на создание заказа"""
    user = User.objects.get(email='test_user_123@test.ru')
    contact = contact_factory(user=user)
    basket = order_factory(state='basket', contact=contact, user_id=user.id)
    order = {'id': basket.id, 'contact': contact.id}
    url = reverse('backend:Order-list')
    resp = simple_user_client.post(url, order)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_get_orders(simple_user_client, order_factory):
    """Тест на получение заказов пользователя"""
    user = User.objects.get(email='test_user_123@test.ru')
    order1 = order_factory(user_id=user.id)
    order2 = order_factory(user_id=user.id)
    url = reverse('backend:Order-list')
    resp = simple_user_client.get(url)
    assert resp.status_code == 200
    assert len(resp.data) == 2
