"""A very small FastAPI-style layer on top of Starlette.

Replay Studio originally used FastAPI, which depends on pydantic-core (a Rust extension with no Android
build). This module keeps the same handler style - decorators, typed path/query parameters, JSON body
models with validation, HTTPException - using only pure-Python dependencies, so the identical API code
runs on Linux and inside the Android app.
"""
from __future__ import annotations

import inspect
import json
import types
import typing
from typing import Any, Callable, Literal, get_args, get_origin, get_type_hints

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response  # noqa: F401 (re-export)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles  # noqa: F401 (re-export)

_REQUIRED = object()


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None):
        self.status_code = status_code
        self.detail = detail if detail is not None else "Error"
        super().__init__(str(self.detail))


class ValidationError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(json.dumps(errors))


# ------------------------------------------------------------------ models

class F:
    """Field constraints (subset of pydantic.Field)."""

    def __init__(self, default: Any = _REQUIRED, *, min_length: int | None = None, max_length: int | None = None,
                 gt: float | None = None, ge: float | None = None, le: float | None = None,
                 default_factory: Callable[[], Any] | None = None):
        self.default, self.default_factory = default, default_factory
        self.min_length, self.max_length, self.gt, self.ge, self.le = min_length, max_length, gt, ge, le


def _check_type(name: str, value: Any, tp: Any) -> Any:
    origin = get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        args = get_args(tp)
        if value is None and type(None) in args:
            return None
        errs = []
        for a in args:
            if a is type(None):
                continue
            try:
                return _check_type(name, value, a)
            except ValueError as e:
                errs.append(str(e))
        raise ValueError(errs[0] if errs else "invalid value")
    if origin is Literal:
        if value not in get_args(tp):
            raise ValueError(f"must be one of {', '.join(map(str, get_args(tp)))}")
        return value
    if origin is list:
        if not isinstance(value, list):
            raise ValueError("must be a list")
        (inner,) = get_args(tp) or (Any,)
        return [_check_type(name, v, inner) for v in value]
    if isinstance(tp, type) and issubclass(tp, Model):
        if not isinstance(value, dict):
            raise ValueError("must be an object")
        return tp.parse(value)
    if tp is bool:
        if not isinstance(value, bool):
            raise ValueError("must be true or false")
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be an integer")
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("must be a number")
        return float(value)
    if tp is str:
        if not isinstance(value, str):
            raise ValueError("must be text")
        return value
    return value


class Model:
    """Minimal pydantic-like model: annotations + F() constraints + optional validate() hook."""

    _fields: dict[str, tuple[Any, F]] = {}

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls._fields = {}

    @classmethod
    def _spec(cls) -> dict[str, tuple[Any, F]]:
        if not cls._fields:
            hints = get_type_hints(cls)
            for name, tp in hints.items():
                if name.startswith("_"):
                    continue
                raw = cls.__dict__.get(name, _REQUIRED)
                cls._fields[name] = (tp, raw if isinstance(raw, F) else F(raw))
        return cls._fields

    def __init__(self, **data: Any):
        obj = self.parse(data)
        self.__dict__.update(obj.__dict__)

    @classmethod
    def parse(cls, data: Any) -> "Model":
        if not isinstance(data, dict):
            raise ValidationError([{"loc": ["body"], "msg": "Expected a JSON object"}])
        obj = object.__new__(cls)
        errors = []
        for name, (tp, f) in cls._spec().items():
            if name in data:
                try:
                    v = _check_type(name, data[name], tp)
                    if isinstance(v, (str, list)):
                        if f.min_length is not None and len(v) < f.min_length:
                            raise ValueError(f"must have at least {f.min_length} characters/items")
                        if f.max_length is not None and len(v) > f.max_length:
                            raise ValueError(f"must have at most {f.max_length} characters/items")
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if f.gt is not None and not v > f.gt:
                            raise ValueError(f"must be greater than {f.gt:g}")
                        if f.ge is not None and not v >= f.ge:
                            raise ValueError(f"must be at least {f.ge:g}")
                        if f.le is not None and not v <= f.le:
                            raise ValueError(f"must be at most {f.le:g}")
                except ValidationError as e:
                    errors += [{"loc": ["body", name, *x["loc"][1:]], "msg": x["msg"]} for x in e.errors]
                    continue
                except ValueError as e:
                    errors.append({"loc": ["body", name], "msg": str(e)})
                    continue
            elif f.default_factory is not None:
                v = f.default_factory()
            elif f.default is not _REQUIRED:
                v = f.default
            else:
                errors.append({"loc": ["body", name], "msg": "Field required"})
                continue
            setattr(obj, name, v)
        if not errors:
            try:
                obj.validate()
            except ValueError as e:
                errors.append({"loc": ["body"], "msg": str(e)})
        if errors:
            raise ValidationError(errors)
        return obj

    def validate(self) -> None:  # override for cross-field checks
        pass

    def model_dump(self) -> dict:
        out = {}
        for name in self._spec():
            v = getattr(self, name)
            out[name] = v.model_dump() if isinstance(v, Model) else v
        return out


# ------------------------------------------------------------------ app

def _is_model(tp: Any) -> type[Model] | None:
    if isinstance(tp, type) and issubclass(tp, Model):
        return tp
    for a in get_args(tp):
        if isinstance(a, type) and issubclass(a, Model):
            return a
    return None


class App:
    """Collects routes like FastAPI and serves them through Starlette."""

    def __init__(self):
        self.state = types.SimpleNamespace()
        self._routes: list = []
        self._middleware: list[Middleware] = []
        self._exc_handlers: dict[type, Callable] = {}
        self._asgi: Starlette | None = None

    def middleware(self, kind: str = "http"):
        def deco(fn):
            self._middleware.append(Middleware(BaseHTTPMiddleware, dispatch=fn))
            return fn
        return deco

    def exception_handler(self, exc_type: type):
        def deco(fn):
            self._exc_handlers[exc_type] = fn
            return fn
        return deco

    def mount(self, path: str, app: Any, name: str | None = None) -> None:
        self._routes.append(Mount(path, app=app, name=name))

    def _route(self, path: str, methods: list[str]):
        def deco(fn):
            self._routes.append(Route(path, self._endpoint(fn), methods=methods))
            return fn
        return deco

    def get(self, path: str):
        return self._route(path, ["GET", "HEAD"])

    def post(self, path: str):
        return self._route(path, ["POST"])

    def put(self, path: str):
        return self._route(path, ["PUT"])

    def delete(self, path: str):
        return self._route(path, ["DELETE"])

    def _endpoint(self, fn: Callable):
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, globalns=fn.__globals__)
        is_async = inspect.iscoroutinefunction(fn)

        async def endpoint(request: Request) -> Response:
            out_resp = Response()
            try:
                kwargs: dict[str, Any] = {}
                errors = []
                for name, p in sig.parameters.items():
                    tp = hints.get(name, str)
                    if name == "request":
                        kwargs[name] = request
                    elif name == "response":
                        kwargs[name] = out_resp
                    elif _is_model(tp):
                        try:
                            data = await request.json()
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            if p.default is not inspect.Parameter.empty:
                                kwargs[name] = p.default
                                continue
                            raise ValidationError([{"loc": ["body"], "msg": "Invalid JSON body"}])
                        kwargs[name] = _is_model(tp).parse(data)
                    else:
                        raw = request.path_params.get(name, request.query_params.get(name))
                        if raw is None:
                            if p.default is inspect.Parameter.empty:
                                errors.append({"loc": ["query", name], "msg": "Field required"})
                            else:
                                kwargs[name] = p.default
                            continue
                        base = [a for a in get_args(tp) if a is not type(None)][0] if get_args(tp) else tp
                        try:
                            kwargs[name] = int(raw) if base is int else float(raw) if base is float else raw
                        except ValueError:
                            errors.append({"loc": ["query", name], "msg": f"must be {base.__name__}"})
                if errors:
                    raise ValidationError(errors)
                result = await fn(**kwargs) if is_async else await run_in_threadpool(fn, **kwargs)
            except HTTPException as e:
                return JSONResponse({"detail": e.detail}, status_code=e.status_code)
            except ValidationError as e:
                return JSONResponse({"detail": e.errors}, status_code=422)
            except Exception as e:
                for t, h in self._exc_handlers.items():
                    if isinstance(e, t):
                        r = h(request, e)
                        return await r if inspect.isawaitable(r) else r
                raise
            if isinstance(result, Response):
                resp = result
            else:
                resp = JSONResponse(result)
            for k, v in out_resp.raw_headers:
                if k == b"set-cookie":
                    resp.raw_headers.append((k, v))
            return resp
        return endpoint

    def build(self) -> Starlette:
        if self._asgi is None:
            self._asgi = Starlette(routes=self._routes, middleware=list(reversed(self._middleware)))
        return self._asgi

    async def __call__(self, scope, receive, send):
        await self.build()(scope, receive, send)
