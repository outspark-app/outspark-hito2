"""Entrada Uvicorn de demo en loopback con DynamoDB Local o PostgreSQL."""

import argparse
import os

import uvicorn

from .bootstrap import compose, create_app
from .persistence import local_storage, postgres_local_storage


def application():
    if os.environ.get("OUTSPARK_POSTGRES_DSN"):
        storage = postgres_local_storage()
        try:
            storage.require_tables()
            app = create_app(compose(storage), local_demo=True, storage_name="PostgreSQL")
        except Exception:
            storage.close()
            raise
        app.router.add_event_handler("shutdown", storage.close)
        return app
    return create_app(compose(local_storage()), local_demo=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prepare", action="store_true", help="Crear esquema y semilla local antes de la API"
    )
    parser.add_argument("--postgres", action="store_true", help="Usar OUTSPARK_POSTGRES_DSN")
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--table-prefix", default="Outspark-local")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    if args.postgres:
        from .seed import seed

        storage = postgres_local_storage()
        try:
            if args.prepare:
                seed(storage)
            storage.require_tables()
            uvicorn.run(
                create_app(compose(storage), local_demo=True, storage_name="PostgreSQL"),
                host="127.0.0.1",
                port=args.port,
                access_log=False,
            )
        finally:
            storage.close()
        return
    if args.prepare:
        if args.endpoint != "http://127.0.0.1:18000" or args.table_prefix != "Outspark-local":
            parser.error("--prepare usa el endpoint y tabla locales por defecto")
        from .prepare import prepare

        prepare()
    storage = local_storage(args.endpoint, args.table_prefix)
    storage.require_tables()
    app = create_app(compose(storage), local_demo=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
