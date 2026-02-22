
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
        
        print("Navigating to GA...")
        await page.goto("https://goldapple.ru/", timeout=60000)
        await asyncio.sleep(5)
        
        print("Navigating to GA Category...")
        await page.goto("https://goldapple.ru/makijazh", timeout=60000)
        await asyncio.sleep(15)
        
        await page.screenshot(path="ga_screenshot.png")
        print("Screenshot saved to ga_screenshot.png")
        
        content = await page.content()
        with open("ga_debug_v2.html", "w") as f:
            f.write(content)
        
        await browser.close()

asyncio.run(run())
