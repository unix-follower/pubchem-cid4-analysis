from fastapi_cid4.config import FastApiServerConfig, resolve_data_dir, resolve_server_config

__all__ = ["FastApiServerConfig", "create_app", "resolve_data_dir", "resolve_server_config"]


def create_app(*args: object, **kwargs: object):
    from fastapi_cid4.app import create_app as _create_app

    return _create_app(*args, **kwargs)
