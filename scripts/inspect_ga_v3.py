
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        print("Navigating to GA Homepage...")
        await page.goto("https://goldapple.ru/", timeout=60000, wait_until="networkidle")
        await asyncio.sleep(5)
        
        # Click cookie button if exists
        try:
            cookie_btn = await page.query_selector("button:has-text('Принять'), button:has-text('ОК'), [class*='cookie'] button")
            if cookie_btn:
                print("Clicking cookie button...")
                await cookie_btn.click()
                await asyncio.sleep(2)
        except:
            pass
            
        print("Navigating to Category...")
        await page.goto("https://goldapple.ru/makijazh", timeout=60000, wait_until="networkidle")
        
        # Scroll down to trigger lazy loading
        print("Scrolling...")
        for _ in range(3):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(2)
            
        content = await page.content()
        with open("ga_debug_v3.html", "w") as f:
            f.write(content)
            
        cards = await page.query_selector_all("article, [class*='product-card']")
        print(f"Found {len(cards)} cards")
        
        await browser.close()

asyncio.run(run())
