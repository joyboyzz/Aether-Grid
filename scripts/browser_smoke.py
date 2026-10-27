import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
async def main():
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for path,name in [('/','command'),('/buyer','buyer'),('/analytics','analytics'),('/carrier','carrier'),('/insurance','insurance')]:
            start=len(errors);response=await page.goto('http://127.0.0.1:8000'+path,wait_until='networkidle')
            await page.screenshot(path=str(ROOT/'verification/screenshots'/f'{name}.png'),full_page=True)
            text=await page.locator('body').inner_text()
            results.append({'portal':name,'http_status':response.status,'body_characters':len(text),
                'page_errors':errors[start:],'simulation_banner':'SIMULATION / PROTOTYPE' in text})
        await browser.close()
    (ROOT/'verification/browser_smoke.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
    assert all(r['http_status']==200 and not r['page_errors'] and r['simulation_banner'] and r['body_characters']>500 for r in results)
asyncio.run(main())
