
import asyncio
import json
import base64
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
        
        responses = []
        async def handle_response(response):
            if response.request.resource_type in ["fetch", "xhr"]:
                try:
                    body = await response.text()
                    responses.append({
                        "url": response.url,
                        "status": response.status,
                        "body": body[:1000] # Save first 1000 chars
                    })
                except:
                    pass

        page.on("response", handle_response)

        print("Navigating to GoldenApple...")
        await page.goto("https://goldapple.ru/", timeout=60000)
        await asyncio.sleep(5)
        await page.goto("https://goldapple.ru/makijazh", timeout=60000)
        await asyncio.sleep(15)
        
        with open("ga_responses.json", "w") as f:
            json.dump(responses, f, indent=2)
            
        await browser.close()

asyncio.run(run())
