
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 375, "height": 812},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        
        print("Navigating to Letu homepage...")
        await page.goto("https://www.letu.ru/", timeout=60000)
        await asyncio.sleep(5)
        
        print("Navigating to Letu category...")
        response = await page.goto("https://www.letu.ru/browse/makiyazh", timeout=60000)
        print(f"Status: {response.status}")
        await asyncio.sleep(15)
        
        # Get the content AFTER JS rendering
        content = await page.content()
        print(f"Content size: {len(content)}")
        
        # Check for product tiles
        cards = await page.query_selector_all('.re-product-tile')
        print(f"Found {len(cards)} re-product-tile cards")
        
        # Check what the first card looks like
        if cards:
            first_card_html = await cards[0].inner_html()
            print(f"First card HTML (first 500 chars): {first_card_html[:500]}")
        
        await browser.close()

asyncio.run(run())
