"""Product ingestion: a product link or a manual brief becomes ProductInfo.

The web ingestor reads what a store publishes for sharing and search engines
(schema.org JSON-LD, OpenGraph tags, Shopify's public product JSON). It obeys
robots.txt and does not try to get around bot protection. Marketplaces such as
Amazon and Flipkart usually block automated fetches; for those, use the
marketplace's official product API as another IngestPlugin, or paste details
into a manual brief.
"""
from __future__ import annotations

import io
import ipaddress
import json
import re
import socket
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from PIL import Image

from ..domain import JobRequest, ProductInfo
from .base import IngestPlugin

MAX_IMAGES = 6
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self.title = ""
        self._in_jsonld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content") and key.lower() not in self.meta:
                self.meta[key.lower()] = unescape(a["content"]).strip()
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)
        elif self._in_title:
            self.title += data


def _walk_jsonld(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk_jsonld(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk_jsonld(node[key])


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(str(x).lower() in ("product", "productgroup") for x in types)


def _text(v) -> str:
    if isinstance(v, dict):
        return str(v.get("name") or v.get("@value") or "")
    if isinstance(v, list):
        return _text(v[0]) if v else ""
    return re.sub(r"<[^>]+>", " ", unescape(str(v or ""))).strip()


def _strip_html(s: str) -> str:
    s = re.sub(r"<(br|/p|/li)[^>]*>", "\n", s or "", flags=re.I)
    return re.sub(r"[ \t]+", " ", unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_product_html(html: str, url: str) -> ProductInfo:
    """Extract product data from a product page. Pure function, easy to test."""
    p = _HeadParser()
    p.feed(html)
    product: dict = {}
    for raw in p.jsonld:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk_jsonld(data):
            if _is_product(node):
                product = node
                break
        if product:
            break

    m = p.meta
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if offers.get("@type") == "AggregateOffer":
        offers = {**offers, "price": offers.get("lowPrice") or offers.get("price")}
    rating = product.get("aggregateRating") or {}
    images = product.get("image") or []
    if isinstance(images, (str, dict)):
        images = [images]
    image_urls = [i.get("url") if isinstance(i, dict) else i for i in images]
    if m.get("og:image"):
        image_urls.append(m["og:image"])

    reviews = []
    for r in (product.get("review") or [])[:50]:
        if isinstance(r, dict) and r.get("reviewBody"):
            reviews.append(_text(r["reviewBody"])[:600])

    specs = {}
    for prop in product.get("additionalProperty") or []:
        if isinstance(prop, dict) and prop.get("name"):
            specs[_text(prop["name"])] = _text(prop.get("value"))

    price = str(offers.get("price") or m.get("product:price:amount") or m.get("og:price:amount") or "")
    currency = str(offers.get("priceCurrency") or m.get("product:price:currency") or m.get("og:price:currency") or "")

    info = ProductInfo(
        title=_text(product.get("name")) or m.get("og:title") or p.title.strip() or urlparse(url).path,
        brand=_text(product.get("brand")) or m.get("og:site_name", ""),
        description=_strip_html(_text(product.get("description")) or m.get("og:description") or m.get("description", "")),
        price=price,
        currency=currency,
        specs=specs,
        rating=float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        review_count=int(float(rating.get("reviewCount") or rating.get("ratingCount") or 0)) or None,
        reviews=reviews,
        images=[urljoin(url, u) for u in dict.fromkeys(u for u in image_urls if u)],
        source_url=url,
    )
    info.features = _features_from_description(info.description)
    return info


def _features_from_description(desc: str) -> list[str]:
    lines = [l.strip(" -•*\t") for l in re.split(r"[\n•]+", desc)]
    feats = [l for l in lines if 8 <= len(l) <= 160]
    if len(feats) < 2:  # one long paragraph: fall back to sentences
        feats = [s.strip() for s in re.split(r"(?<=[.!?])\s+", desc) if 12 <= len(s.strip()) <= 160]
    return feats[:8]


def save_image(content: bytes, dest: Path) -> Path:
    img = Image.open(io.BytesIO(content))
    img = img.convert("RGB")
    img.thumbnail((2400, 2400))
    img.save(dest, "JPEG", quality=92)
    return dest


class BlockedAddress(PermissionError):
    pass


def assert_public_host(host: str) -> None:
    """Refuse hosts that resolve to private, loopback or link-local addresses
    (SSRF guard: product links must not reach internal services or cloud metadata)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise BlockedAddress(f"Cannot resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise BlockedAddress(f"{host} resolves to a non-public address")


class WebIngest(IngestPlugin):
    name = "web"
    priority = 20
    license = "MIT (this project)"
    description = "Product pages via schema.org JSON-LD + OpenGraph; Shopify public product JSON. Respects robots.txt."

    def __init__(self, user_agent: str, client: httpx.Client | None = None, allow_private: bool = False):
        self.user_agent = user_agent
        self.allow_private = allow_private
        self.client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": user_agent})
        # Checked on every request, including each redirect hop and image download.
        self.client.event_hooks["request"].append(self._guard)

    def _guard(self, request: httpx.Request) -> None:
        if request.url.scheme not in ("http", "https"):
            raise BlockedAddress(f"Scheme {request.url.scheme} not allowed")
        if not self.allow_private:
            assert_public_host(request.url.host)

    def can_handle(self, request: JobRequest) -> bool:
        return bool(request.url) and urlparse(request.url).scheme in ("http", "https")

    def _allowed(self, url: str) -> bool:
        parts = urlparse(url)
        rp = RobotFileParser()
        try:
            r = self.client.get(f"{parts.scheme}://{parts.netloc}/robots.txt")
            if r.status_code >= 400:
                return True
            rp.parse(r.text.splitlines())
        except httpx.HTTPError:
            return True
        return rp.can_fetch(self.user_agent, url)


    def ingest(self, request: JobRequest, workdir: Path) -> ProductInfo:
        url = request.url or ""
        if not self._allowed(url):
            raise PermissionError(f"robots.txt disallows fetching {url}. Use a manual brief or the store's API.")
        info = self._shopify(url)
        if info is None:
            resp = self.client.get(url)
            resp.raise_for_status()
            info = parse_product_html(resp.text, str(resp.url))
        info.source = self.name
        info.images = self._download(info.images, workdir)
        return info

    def _shopify(self, url: str) -> ProductInfo | None:
        m = re.search(r"(https?://[^?#]+/products/[^/?#]+)", url)
        if not m:
            return None
        try:
            r = self.client.get(m.group(1) + ".json")
            if r.status_code != 200 or "product" not in r.json():
                return None
        except (httpx.HTTPError, ValueError):
            return None
        p = r.json()["product"]
        variant = (p.get("variants") or [{}])[0]
        desc = _strip_html(p.get("body_html") or "")
        return ProductInfo(
            title=p.get("title", ""),
            brand=p.get("vendor", ""),
            description=desc,
            price=str(variant.get("price") or ""),
            features=_features_from_description(desc),
            specs={o["name"]: ", ".join(o.get("values", [])) for o in p.get("options", []) if o.get("name") != "Title"},
            images=[i["src"] for i in p.get("images", []) if i.get("src")],
            source_url=url,
        )

    def _download(self, urls: list[str], workdir: Path) -> list[str]:
        out = []
        for i, u in enumerate(urls[: MAX_IMAGES * 2]):
            if len(out) >= MAX_IMAGES:
                break
            try:
                r = self.client.get(u)
                if r.status_code != 200 or len(r.content) > MAX_IMAGE_BYTES:
                    continue
                out.append(str(save_image(r.content, workdir / f"img_{i}.jpg")))
            except (httpx.HTTPError, OSError):
                continue
        return out


class ManualIngest(IngestPlugin):
    name = "manual"
    priority = 10
    license = "MIT (this project)"
    description = "Product details and images uploaded by the user."

    def __init__(self, uploads_dir: Path):
        self.uploads_dir = uploads_dir

    def can_handle(self, request: JobRequest) -> bool:
        return request.brief is not None

    def ingest(self, request: JobRequest, workdir: Path) -> ProductInfo:
        b = request.brief
        assert b is not None
        images = []
        for uid in b.upload_ids:
            src = self.uploads_dir / uid
            if not re.fullmatch(r"[a-f0-9]{32}", uid) or not src.exists():
                raise FileNotFoundError(f"Unknown upload id {uid}")
            images.append(str(save_image(src.read_bytes(), workdir / f"img_{len(images)}.jpg")))
        return ProductInfo(
            title=b.title,
            brand=b.brand,
            description=b.description,
            price=b.price,
            features=b.features or _features_from_description(b.description),
            reviews=b.reviews,
            images=images,
            source_url=request.url,
            source=self.name,
        )
