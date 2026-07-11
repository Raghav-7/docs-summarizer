import asyncio
from playwright.async_api import async_playwright
import zipfile
import os

# Create dummy zip
with zipfile.ZipFile('dummy.zip', 'w') as z:
    z.writestr('chat.txt', '12/12/23, 10:00 - Alice: hello from zip!\n')
    z.writestr('image.jpg', '00000000')

async def test_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("[TEST] Navigating to http://localhost:5000/tool/summarize")
        await page.goto('http://localhost:5000/tool/summarize')

        print("[TEST] Uploading dummy.zip...")
        await page.set_input_files('#fileInput', 'dummy.zip')
        
        # We need to wait a tiny bit to ensure the file is processed if there's any async file handling
        await asyncio.sleep(1)
        
        await page.click('#summarizeBtn')

        print("[TEST] Waiting for processing to complete...")
        # Since it uses JSZip, it should be very fast.
        await page.wait_for_selector('#summaryContent', state='visible', timeout=60000)
        print("[TEST] Summary loaded successfully!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_flow())
