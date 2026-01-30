import asyncio
import sys
import json
from app.parsers.factory import ParserFactory

async def test_url(url: str):
    print(f"\n--- Testing URL: {url} ---")
    parser = ParserFactory.get_parser(url)
    print(f"Selected Parser: {parser.__class__.__name__}")
    
    try:
        # If the URL looks like a catalog or the parser has catalog capability
        if "category" in url or "catalog" in url or hasattr(parser, "parse_catalog"):
            print("Detected potential catalog URL. Trying parse_catalog...")
            catalog = await parser.parse_catalog(url)
            print(f"Parsed Catalog Result ({catalog.count} items):")
            # Show only first 2 items to avoid flooding
            if catalog.products:
                print("First item preview:")
                print(json.dumps(catalog.products[0].model_dump(), indent=2, ensure_ascii=False))
            return

        product = await parser.parse(url)
        print("Parsed Product Result:")
        print(json.dumps(product.model_dump(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error parsing URL: {e}")
        # Fallback to single product parse if catalog failed but we want to try anyway
        try:
            print("Retrying with single product parse...")
            product = await parser.parse(url)
            print(json.dumps(product.model_dump(), indent=2, ensure_ascii=False))
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_parser.py <URL>")
        # Default test URL (some generic product)
        test_urls = [
            "https://www.ikea.com/ru/ru/p/lugga-aromatizirovannaya-svecha-v-stakane-rozovyy-cvetok-80259182/",
            "https://ozon.ru/product/example-id/"
        ]
    else:
        test_urls = sys.argv[1:]

    for url in test_urls:
        asyncio.run(test_url(url))
