import asyncio
from playwright.async_api import async_playwright
import zipfile

# Create dummy zip
with zipfile.ZipFile('dummy.zip', 'w') as z:
    z.writestr('chat.txt', '12/12/23, 10:00 - Alice: hello from zip!\n')
    z.writestr('image.jpg', '00000000')

async def test_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))
        page.on("dialog", lambda dialog: print(f"Browser dialog: {dialog.message}"))
        
        print("[TEST] Navigating to http://localhost:5000/tool/summarize")
        await page.goto('http://localhost:5000/tool/summarize')

        print("[TEST] Uploading dummy.zip...")
        await page.set_input_files('#fileInput', 'dummy.zip')
        await asyncio.sleep(1)
        
        await page.click('#summarizeBtn')

        print("[TEST] Waiting for fast stats to complete...")
        # Check if stats column becomes visible
        try:
            await page.wait_for_selector('#statsColumn', state='visible', timeout=10000)
            print("[TEST] Fast stats loaded successfully!")
        except Exception as e:
            print(f"[TEST] Fast stats failed: {e}")

        print("[TEST] Waiting for processing to complete...")
        try:
            await page.wait_for_selector('#summaryContent', state='visible', timeout=60000)
            print("[TEST] Summary loaded successfully!")
        except Exception as e:
            print(f"[TEST] AI Summary failed: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_flow())
