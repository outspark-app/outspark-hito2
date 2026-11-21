"""Adaptador ASGI Lambda; nunca habilita la identidad demo ni un endpoint local."""

from mangum import Mangum

from .bootstrap import compose, create_app
from .persistence import cloud_storage

_adapter = None


def lambda_handler(event, context):
    global _adapter
    if _adapter is None:
        _adapter = Mangum(create_app(compose(cloud_storage()), local_demo=False), lifespan="off")
    return _adapter(event, context)
