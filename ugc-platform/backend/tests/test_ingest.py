import json

import httpx
import pytest

from ugc_studio.domain import JobRequest
from ugc_studio.plugins.ingest import WebIngest, parse_product_html

from .conftest import PRODUCT_HTML, jpeg_bytes


def test_parses_jsonld_product_inside_graph():
    p = parse_product_html(PRODUCT_HTML, "https://shop.example/p/1")
    assert p.title == "GripMount Magnetic Car Phone Mount"
    assert p.brand == "GripMount"
    assert (p.price, p.currency) == ("28.00", "USD")
    assert (p.rating, p.review_count) == (4.6, 1843)
    assert p.images == ["https://shop.example/a.jpg", "https://shop.example/b.jpg", "https://shop.example/og.jpg"]
    assert p.specs == {"Weight": "80 g"}
    assert p.reviews and "kept falling" in p.reviews[0]
    assert "Holds phones up to 300 g through potholes." in p.features


def test_falls_back_to_opengraph():
    html = '<head><meta property="og:title" content="Lamp"><meta property="og:description" content="A warm lamp."></head>'
    p = parse_product_html(html, "https://x.example/lamp")
    assert p.title == "Lamp" and p.description == "A warm lamp."


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_web_ingest_downloads_images(tmp_path):
    client = _client({
        "https://shop.example/robots.txt": httpx.Response(404),
        "https://shop.example/p/1": httpx.Response(200, text=PRODUCT_HTML),
        "https://shop.example/a.jpg": httpx.Response(200, content=jpeg_bytes()),
        "https://shop.example/b.jpg": httpx.Response(200, content=jpeg_bytes((0, 0, 255))),
    })
    info = WebIngest("TestBot", client, allow_private=True).ingest(JobRequest(url="https://shop.example/p/1"), tmp_path)
    assert info.source == "web"
    assert len(info.images) == 2 and all(p.endswith(".jpg") for p in info.images)


def test_shopify_public_json(tmp_path):
    product = {"product": {"title": "Linen Shirt", "vendor": "Acme", "body_html": "<p>Breathable linen.</p><p>Relaxed fit for summer.</p>",
                           "variants": [{"price": "49.00"}], "options": [{"name": "Size", "values": ["S", "M"]}],
                           "images": [{"src": "https://cdn.example/s.jpg"}]}}
    client = _client({
        "https://acme.example/robots.txt": httpx.Response(404),
        "https://acme.example/products/linen-shirt.json": httpx.Response(200, text=json.dumps(product)),
        "https://cdn.example/s.jpg": httpx.Response(200, content=jpeg_bytes()),
    })
    info = WebIngest("TestBot", client, allow_private=True).ingest(JobRequest(url="https://acme.example/products/linen-shirt?variant=1"), tmp_path)
    assert (info.title, info.brand, info.price) == ("Linen Shirt", "Acme", "49.00")
    assert info.specs == {"Size": "S, M"}
    assert len(info.images) == 1


def test_respects_robots_txt(tmp_path):
    client = _client({"https://shop.example/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /")})
    with pytest.raises(PermissionError):
        WebIngest("TestBot", client, allow_private=True).ingest(JobRequest(url="https://shop.example/p/1"), tmp_path)


def test_blocks_internal_addresses(tmp_path):
    client = _client({"http://127.0.0.1:3900/": httpx.Response(200, text="internal")})
    for url in ("http://127.0.0.1:3900/", "http://169.254.169.254/latest/meta-data/", "http://localhost/admin"):
        with pytest.raises(PermissionError):
            WebIngest("TestBot", client).ingest(JobRequest(url=url), tmp_path)
