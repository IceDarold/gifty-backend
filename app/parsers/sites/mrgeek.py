from __future__ import annotations
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.parsers.catalog_base import BaseCatalogParser
from app.parsers.schemas import ParsedProduct, ParsedCatalog

logger = logging.getLogger(__name__)

class MrGeekParser(BaseCatalogParser):
    async def parse(self, url: str) -> ParsedProduct:
        # Fallback to generic parsing for single product page for now, 
        # or implement specific single-page logic if needed.
        # Since the user emphasized catalog parsing, we focus on parse_catalog.
        # But to satisfy the abstract method, we can reuse generic logic or implement minimal here.
        # For simplicity, let's just use the metadata-based parsing for single pages 
        # via the parent/mixin if we had one, but here we can just throw or implement basic.
        # Let's verify if BaseCatalogParser inherits BaseParser which has abstract parse.
        # Yes. Let's redirect to GenericParser logic or implement a simple one.
        # Actually, let's just implement the specific single page parser too since we know the selectors are likely similar or standard.
        # But the user asked for catalog parsing primarily. Let's make it robust.
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Single page selectors (hypothesis based on catalog classes, usually they differ slightly but let's try)
        # Often h1 is title.
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Untitled"
        # .price .totalPrice might work here too
        price_tag = soup.select_one(".price .totalPrice")
        price = self._clean_price(price_tag.get_text(strip=True)) if price_tag else None
        
        return ParsedProduct(
            title=title,
            product_url=url,
            price=price,
            currency="RUB",
            merchant="MrGeek",
            raw_data={"source": "mrgeek_single"}
        )

    async def parse_catalog(self, url: str) -> ParsedCatalog:
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        items = soup.select("div.good_inner")
        products = []
        
        for item in items:
            try:
                title_tag = item.select_one("a.subject")
                if not title_tag:
                    continue
                    
                title = title_tag.get_text(strip=True)
                relative_link = title_tag['href']
                product_url = urljoin(url, relative_link)
                
                desc_tag = item.select_one("span.descr")
                description = desc_tag.get_text(strip=True) if desc_tag else None
                
                price_tag = item.select_one(".price .totalPrice")
                price = self._clean_price(price_tag.get_text(strip=True)) if price_tag else None
                
                img_tag = item.select_one(".foto img")
                image_url = img_tag['src'] if img_tag else None
                if image_url and not image_url.startswith("http"):
                     image_url = urljoin(url, image_url)

                product = ParsedProduct(
                    title=title,
                    description=description,
                    price=price,
                    currency="RUB",
                    image_url=image_url,
                    product_url=product_url,
                    merchant="MrGeek",
                    raw_data={"source": "mrgeek_catalog"}
                )
                products.append(product)
            except Exception as e:
                logger.error(f"Error parsing item in MrGeek catalog: {e}")
                continue
                
        return ParsedCatalog(
            products=products,
            source_url=url,
            count=len(products)
        )

    def _clean_price(self, price_str: str) -> float | None:
        try:
            # Remove spaces and non-breaking spaces
            clean = price_str.replace(" ", "").replace("\xa0", "")
            return float(clean)
        except ValueError:
            return None
