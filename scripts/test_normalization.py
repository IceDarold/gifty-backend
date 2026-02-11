import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.ingestion import normalize_url

def test_normalize_url():
    test_cases = [
        ("https://example.com/p/1?utm_source=google&utm_medium=cpc&ref=xyz", "https://example.com/p/1?ref=xyz"),
        ("https://detmir.ru/product/123?yclid=888&gclid=999", "https://detmir.ru/product/123"),
        ("https://shop.ru/item?fbclid=abc&from=main&asid=123", "https://shop.ru/item?from=main&asid=123"),
        ("https://site.com/search?q=gift&utm_campaign=winter", "https://site.com/search?q=gift"),
        ("https://site.com/path#fragment", "https://site.com/path"), # Fragments should be removed
    ]
    
    for input_url, expected in test_cases:
        actual = normalize_url(input_url)
        print(f"Input: {input_url}")
        print(f"Expect: {expected}")
        print(f"Actual: {actual}")
        assert actual == expected, f"Failed for {input_url}"
    
    print("All normalization tests passed!")

if __name__ == "__main__":
    test_normalize_url()
