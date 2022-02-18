from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.viewsets import ModelViewSet
from yaml import safe_load
from .tasks import send_email
from .models import Shop, Category, ProductInfo, Product, Parameter, ProductParameter, Order, OrderItem, Contact
from .serializers import (
    UserSerializer,
    ProductInfoSerializer,
    OrderSerializer,
    OrderItemSerializer,
    ContactSerializer,
    CategorySerializer,
    ShopSerializer
)


class PartnerViewSet(ModelViewSet):

    http_method_names = ['get', 'post']

    def create(self, request, *args, **kwargs):  # Загрузка данных из файла
        if not request.user.is_authenticated:
            print(request.user, request.auth, request.headers)
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        url = request.data.get('url')
        if url:
            with open(url, encoding='utf-8') as f:
                data = safe_load(f)
            shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
            for category in data['categories']:
                category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                category_object.shops.add(shop.id)
                category_object.save()
            ProductInfo.objects.filter(shop_id=shop.id).delete()
            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
                product_info = ProductInfo.objects.create(
                    product_id=product.id,
                    external_id=item['id'],
                    model=item['model'],
                    price=item['price'],
                    price_rrc=item['price_rrc'],
                    quantity=item['quantity'],
                    shop_id=shop.id
                )
                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.create(
                        product_info_id=product_info.id, parameter_id=parameter_object.id, value=value
                    )
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def list(self, request, *args, **kwargs):  # Отображение заказов для поставщика
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category').distinct()
        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class LoginAccount(APIView):

    def post(self, request, *args, **kwargs):
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])
            if user is not None:
                if user.is_active:
                    token, created = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})
            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class RegisterAccount(APIView):  # Для регистрации покупателей

    def post(self, request, *args, **kwargs):
        # проверяем обязательные аргументы
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):
            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    send_email('Подтверждение регистрации', 'Регистрация прошла успешно!', [request.data['email']])
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ProductInfoViewSet(ModelViewSet):  # Список продуктов

    serializer_class = ProductInfoSerializer
    search_fields = ['product__name', 'model']
    http_method_names = ['get']

    def get_queryset(self):
        query = Q(shop__state=True)
        shop_id = self.request.GET.get('shop_id', None)
        category_id = self.request.GET.get('category_id', None)
        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(product__category_id=category_id)
        queryset = ProductInfo.objects.filter(query).select_related(
            'shop', 'product').distinct()
        return queryset


class BasketViewSet(ModelViewSet):  # Работа с корзиной для покупателя

    serializer_class = OrderSerializer
    http_method_names = ['get', 'post', 'put', 'delete']

    # отобразить корзину
    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category')

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # добавить позицию в корзину
    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        items = request.data.get('ordered_items')
        if items:
            basket, created = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            objects_created = 0
            for item in items:
                exists_item = OrderItem.objects.filter(order=basket.id, product_info=item["product_info"])
                if len(exists_item) > 0:
                    return JsonResponse({'Status': False, 'Errors': f'Позиция product_info={item["product_info"]}'
                                                                    f' уже есть в корзине'})
                item.update({'order': basket.id})
                serializer = OrderItemSerializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    objects_created += 1
                else:
                    return JsonResponse({'Status': False, 'Errors': serializer.errors})
            return JsonResponse({'Status': True, 'Создано позиций': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить позиции из корзины
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        items = request.data.get('ordered_items')
        if items:
            basket, created = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            for item in items:
                query = query | Q(order_id=basket.id, product_info=item["product_info"])
            deleted_count = OrderItem.objects.filter(query).delete()[0]
            return JsonResponse({'Status': True, 'Удалено позиций': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактировать позиции в корзине
    def update(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        items = request.data.get('ordered_items')
        if items:
            basket, created = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            objects_updated = 0
            for item in items:
                objects_updated += OrderItem.objects.filter(order_id=basket.id, product_info=item['product_info']).\
                    update(quantity=item['quantity'])
                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ContactViewSet(ModelViewSet):  # Работа с контактами

    serializer_class = ContactSerializer
    http_method_names = ['get', 'post', 'put', 'delete']

    # получить все контакты
    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        contact = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавить контакт
    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        if {'city', 'street', 'house', 'phone'}.issubset(request.data):
            request.data._mutable = True
            request.data.update({'user': request.user.id})
            serializer = ContactSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=201)
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактировать контакт
    def update(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                if contact:
                    request.data.update({'user': request.user.id})
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return Response(serializer.data)
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить контакт
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        contact_id = request.data.get('id')
        if contact_id:
            if contact_id.isdigit():
                Contact.objects.filter(Q(user_id=request.user.id, id=contact_id)).delete()
                return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderViewSet(ModelViewSet):  # Заказы покупателя

    serializer_class = OrderSerializer
    http_method_names = ['get', 'post']

    # получить мои заказы
    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').distinct()
        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # сделать новый заказ из корзины
    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Только для зарегистрированных пользователей'}, status=403)
        if {'id', 'contact'}.issubset(request.data):
            id_order = request.data['id']
            data = Order.objects.filter(id=id_order, user=request.user.id, state='basket')
            if len(data) == 0:
                return JsonResponse({'Status': False, 'Errors': 'Не найдена корзина пользователя'})
            data.update(state='new', contact_id=request.data['contact'])
            send_email('Подтверждение заказа', 'Заказ успешно принят в обработку!', [request.user.email])
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryViewSet(ModelViewSet):  # Просмотр категорий

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ["name"]
    http_method_names = ['get']


class ShopViewSet(ModelViewSet):

    serializer_class = ShopSerializer
    queryset = Shop.objects.filter(state=True)
    http_method_names = ['get']
    search_fields = ['name']
