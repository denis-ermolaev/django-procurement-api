# Create your views here.
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class CheckView(APIView):
    def get(self, request: Request):
        return Response(
            data={"message": "API успешно запущено и работает."},
            status=200,
        )
