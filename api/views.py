# Create your views here.
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product
from .serializers import ProductSerializer


class CheckView(APIView):
    def get(self, _: Request):
        return Response(
            data={"message": "API успешно запущено и работает."},
            status=200,
        )


class ProductListView(APIView):
    def get(self, _: Request):

        product_list = Product.objects.all()
        serializer = ProductSerializer(product_list, many=True)
        return Response(
            data=serializer.data,
            status=200,
        )
