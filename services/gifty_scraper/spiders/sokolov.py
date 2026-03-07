import json
import re
import scrapy
from gifty_scraper.base_spider import GiftyBaseSpider
from gifty_scraper.items import CategoryItem

class SokolovSpider(GiftyBaseSpider):
    name = "sokolov"
    allowed_domains = ["sokolov.ru", "catalog.sokolov.ru"]
    site_key = "sokolov"
    
    # Base URLs
    WEB_BASE_URL = "https://sokolov.ru"
    API_BASE_URL = "https://catalog.sokolov.ru/api/v2/catalog"
    FILTERS_URL = "https://catalog.sokolov.ru/api/v2/filters"
    
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Origin": "https://sokolov.ru",
            "Referer": "https://sokolov.ru/",
        },
    }

    def start_requests(self):
        # The public web catalog may return 401 from this environment. For discovery, rely on the
        # API filters endpoint which provides a stable category tree.
        start_url = self.url or (self.start_urls[0] if self.start_urls else None)
        if self.strategy == "discovery":
            yield scrapy.Request(
                start_url or self.FILTERS_URL,
                callback=self.parse,
                dont_filter=True,
                headers={"Accept": "application/json"},
            )
        else:
            if start_url:
                yield scrapy.Request(start_url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Main entry point. Dispatches to discovery or catalog.
        Sokolov URLs starting with /jewelry-catalog/ are usually catalog or product pages.
        """
        if self.strategy == "discovery":
            yield from self.parse_discovery(response)
        else:
            yield from self.parse_catalog(response)

    def parse_discovery(self, response):
        """
        Discovery strategy: find category links.
        """
        # Preferred discovery mode: parse the category tree from `/api/v2/filters`.
        content_type = response.headers.get("Content-Type", b"").decode().lower()
        if "application/json" not in content_type:
            yield response.follow(self.FILTERS_URL, callback=self.parse_discovery, dont_filter=True)
            return

        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse filters JSON: {e}")
            return

        category = data.get("category") if isinstance(data, dict) else None
        fields = category.get("fields") if isinstance(category, dict) else None
        if not isinstance(fields, list) or not fields:
            self.logger.warning(f"No category fields found in filters response: {response.url}")
            return

        seen = set()

        def emit(node: dict, parent_url: str | None):
            name = (node.get("name") or "").strip()
            value = (node.get("value") or "").strip()
            if not name or not value:
                return
            # Use API catalog URLs so deep parsing works even if web catalog is blocked.
            url = f"{self.API_BASE_URL}/jewelry-catalog/{value}/?per_page=72&page=1"
            if url in seen:
                return
            seen.add(url)
            yield self.create_category(
                name=name,
                url=url,
                parent_url=parent_url or response.url,
            )

        def walk(nodes: list, parent_url: str | None):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                for item in emit(node, parent_url):
                    yield item
                children = node.get("children")
                if isinstance(children, list) and children:
                    child_parent = f"{self.API_BASE_URL}/jewelry-catalog/{(node.get('value') or '').strip()}/?per_page=72&page=1"
                    yield from walk(children, child_parent)

        yield from walk(fields, response.url)

    def parse_catalog(self, response):
        """
        Catalog strategy: handle either the HTML page (extract JSON or convert to API) or the JSON response.
        """
        # If response is JSON, parse products
        content_type = response.headers.get("Content-Type", b"").decode().lower()
        if "application/json" in content_type:
            yield from self._parse_api_response(response)
            return

        # If response is HTML, we need to extract products from the page or jump to API
        next_data = self._extract_next_data(response)
        if next_data:
            yield from self._parse_next_data(next_data, response)
            return

        # Fallback: if it's a web URL, try to guess the API URL and request it
        # Extract the path after domain (e.g. /jewelry-catalog/rings/)
        match = re.search(r'sokolov\.ru(/jewelry-catalog/.*)', response.url)
        if match:
            path = match.group(1).split('?')[0]
            # Ensure path ends with / and doesn't have duplicate slashes
            path = path.rstrip('/') + '/'
            api_url = f"{self.API_BASE_URL}{path}?per_page=72&page=1"
            self.logger.info(f"Stepping into API for catalog: {api_url}")
            yield response.follow(api_url, callback=self.parse_catalog)
        else:
            self.logger.warning(f"Could not handle catalog URL: {response.url}")

    def _parse_api_response(self, response):
        """Parses the direct JSON response from catalog.sokolov.ru API"""
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return

        # API returns products in 'data' key or sometimes 'products'
        products = data.get("data")
        if not products:
            products = data.get("products", [])
            
        if not products:
            self.logger.warning(f"No products found in API response: {response.url}")
            return

        for product in products:
            yield self._build_product(product, response)

        # Pagination using links from API response
        next_url = data.get("links", {}).get("next")
        if next_url:
            yield response.follow(next_url, callback=self.parse_catalog)
        else:
            # Fallback to manual pagination if links missing
            meta = data.get("meta", {})
            current_page = meta.get("current_page", 1)
            page_count = meta.get("page_count", 1)
            
            if current_page < page_count:
                next_page = current_page + 1
                if 'page=' in response.url:
                    next_url = re.sub(r'page=\d+', f'page={next_page}', response.url)
                else:
                    separator = '&' if '?' in response.url else '?'
                    next_url = f"{response.url}{separator}page={next_page}"
                
                yield response.follow(next_url, callback=self.parse_catalog)

    def _parse_next_data(self, next_data, response):
        """Parses products from __NEXT_DATA__ script tag"""
        props = next_data.get("props", {}).get("pageProps", {})
        
        # Try different locations for catalog data in Next.js props
        catalog_data = props.get("catalogData")
        if not catalog_data:
            # Check initialState if catalogData is not direct
            catalog_state = props.get("initialState", {}).get("catalog", {})
            if isinstance(catalog_state, dict):
                catalog_data = catalog_state
            
        products = catalog_data.get("products") or catalog_data.get("data", [])
        if not products:
            self.logger.debug(f"No products found in NEXT_DATA for {response.url}")
            return

        for product in products:
            yield self._build_product(product, response)
            
        # Pagination: Next.js usually only has page 1. Follow API for subsequent pages.
        if self.strategy in ["deep", "discovery"]:
            meta = catalog_data.get("meta", {})
            current_page = meta.get("current_page", 1)
            page_count = meta.get("page_count", 1)
            
            if current_page < page_count:
                match = re.search(r'sokolov\.ru(/jewelry-catalog/.*)', response.url)
                if match:
                    path = match.group(1).split('?')[0]
                    path = path.rstrip('/') + '/'
                    api_url = f"{self.API_BASE_URL}{path}?per_page=72&page={current_page + 1}"
                    yield response.follow(api_url, callback=self.parse_catalog)

    def _build_product(self, product, response):
        """Helper to create ProductItem from product JSON object"""
        url_code = product.get("url_code")
        if not url_code:
            return None
            
        # Catalog path - try to get it from product data or fall back to sensible default
        catalog_path = product.get("catalog", "jewelry-catalog")
        product_url = f"{self.WEB_BASE_URL}/{catalog_path}/product/{url_code}/"
        
        # Images: Usually in 'media' array
        media = product.get("media", [])
        image_url = None
        if media:
            # Find first item with url or data.jpg
            for item in media:
                if item.get("url"):
                    image_url = item.get("url")
                    break
                if item.get("data", {}).get("jpg"):
                    image_url = item.get("data", {}).get("jpg")
                    break
            
            # Fallback to 'photos' array if media fails
            if not image_url and product.get("photos"):
                image_url = product.get("photos")[0]
                    
            if image_url and not image_url.startswith("http"):
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                else:
                    image_url = f"https://sokolov.ru{image_url}"

        # Price extraction
        price = product.get("price")
        # Sometimes it's a dict, sometimes a number
        if isinstance(price, dict):
            price = price.get("value")
            
        try:
            price_val = float(price) if price is not None else None
        except (ValueError, TypeError):
            price_val = None

        return self.create_product(
            title=product.get("name"),
            product_url=product_url,
            price=price_val,
            image_url=image_url,
            merchant="Sokolov",
            raw_data={
                "id": product.get("id"),
                "article": product.get("article"),
                "url_code": url_code
            }
        )

    def _extract_next_data(self, response):
        """Helper to extract __NEXT_DATA__ JSON from HTML"""
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception as e:
                self.logger.debug(f"Failed to decode __NEXT_DATA__: {e}")
                return None
        return None
