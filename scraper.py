import requests, re, time, asyncio, json, os
from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

# Define headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
}

# Devfolio Scraper
def scrape_devfolio():
    events = []
    res = requests.get('https://devfolio.co/hackathons', headers=HEADERS)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise RuntimeError("Couldn't find __NEXT_DATA__ in Devfolio page")

    data = json.loads(script.string)
    hackathons = data \
        .get("props", {}) \
        .get("pageProps", {}) \
        .get("dehydratedState", {}) \
        .get("queries", [])[0] \
        .get('state',{})\
        .get('data',{})

    open_hackathons = hackathons.get('open_hackathons',[])
    upcoming_hackathons = hackathons.get('upcoming_hackathons',[])

    for hack in open_hackathons:
        # parse title, URL, status, theme, types, and dates
        title = hack.get("name", "")
        link = hack.get("site", "") if hack.get("site", "") != None else 'No'
        theme = hack.get("themes", [])[0].get('theme',{}).get('name',"")
        start_date = hack.get("starts_at",'')[:9]
        end_date = hack.get("ends_at",'')[:9]
        deadline = hack.get("settings",{}).get('reg_ends_at')[:9] + ' ' + hack.get("settings",{}).get('reg_ends_at')[11:19] 
        is_online = hack.get("is_online",{}) 

        events.append({
            "name": title,
            "domain": theme,
            "mode": "Online" if is_online!="False" else "Offline",
            "status": 'open',
            "start_date": start_date,
            "end_date": end_date,
            "deadline": deadline,
            "url": link if link!='' else 'No link',
            "registration_fee":"Free",
            "source":"DevFolio"
    })
    for hack in upcoming_hackathons:
        # parse title, URL, status, theme, types, and dates
        title = hack.get("name", "")
        link = hack.get("site", "") if hack.get("site", "") != None else 'No'
        theme = hack.get("themes", [])[0].get('theme',{}).get('name',"")
        start_date = hack.get("starts_at",'')[:9]
        end_date = hack.get("ends_at",'')[:9]
        deadline = hack.get("settings",{}).get('reg_ends_at')[:10] + ' ' + hack.get("settings",{}).get('reg_ends_at')[11:19] 
        is_online = hack.get("is_online",{}) 

        events.append({
            "name": title,
            "domain": theme,
            "mode": "Online" if is_online!="False" else "Offline",
            "status": 'Upcoming',
            "start_date": start_date,
            "end_date": end_date,
            "deadline": deadline,
            "url": link if link!='' else 'No link',
            "registration_fee":"Free",
            "source":"DevFolio"
    })
    return events    

async def scrape_unstop_link():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://unstop.com/hackathons", wait_until="networkidle")
            await asyncio.sleep(3) 
            await page.wait_for_selector("app-competition-listing", timeout=15000)
            hackathon_cards = await page.query_selector_all("app-competition-listing")
            hackathons = []
            
            for card in hackathon_cards:
                hackathon_data = {}
                
                try:
                    # Extract title from h2 element
                    title_element = await card.query_selector("h2.double-wrap")
                    if title_element:
                        hackathon_data["title"] = (await title_element.inner_text()).strip()
                    
                    # Extract tags/skills
                    tags = []
                    tag_elements = await card.query_selector_all(".chip_text")
                    for tag in tag_elements:
                        tag_text = await tag.inner_text()
                        tags.append(tag_text.strip())
                    hackathon_data["tags"] = tags

                    # Extract hackathon link
                    link_element = await card.query_selector("div[id^='i_']")
                    if link_element:
                        hackathon_id = await link_element.get_attribute("id")
                        if hackathon_id:
                            # Extract ID from format like "i_1505045_1
                            id_parts = hackathon_id.split("_")
                            if len(id_parts) >= 2:
                                opportunity_id = id_parts[1]
                                # You'll need to construct the URL
                                hackathon_data["opportunity_id"] = opportunity_id
                    
                    if hackathon_data:  # Only add if we got some data
                        hackathons.append(hackathon_data)
                        
                except Exception as e:
                    print(f"Error extracting data from card: {e}")
                    continue
            
            return hackathons
        
        except Exception as e:
            print(f"Error occurred: {e}")
            await page.screenshot(path="debug_screenshot.png")
            return []
        
        finally:
            await browser.close()

async def get_hackathon_details(opportunity_id):
    """Get detailed hackathon information using the opportunity ID"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            url = f"https://unstop.com/hackathons/{opportunity_id}"
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            
            details = {}
            
            # Extract title
            title_element = await page.query_selector("h1.ttl")
            if title_element:
                details["name"] = await title_element.inner_text()
            
            # Extract registration deadline - CORRECTED VERSION
            deadline_element = await page.query_selector('.item span:has-text("Registration Deadline")')
            if deadline_element:
                # Get the parent item div
                parent_item = await deadline_element.query_selector('xpath=../..')
                if parent_item:
                    deadline_text = await parent_item.inner_text()
                    # Extract just the date part
                    lines = deadline_text.split('\n')
                    for line in lines:
                        if 'IST' in line or any(month in line for month in ['Jan', 'Feb', 'Mar', 'Apr',
                                                                            'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                            details["deadline"] = line.strip()
                            break
            
            # Extract description
            # description_element = await page.query_selector(".un_editor_text_live")
            # if description_element:
            #     details["description"] = await description_element.inner_text()
            
            # Extract location
            location_element = await page.query_selector(".location div")
            if location_element:
                details["mode"] = await location_element.inner_text()
            
            # Extract eligibility
            eligibility_elements = await page.query_selector_all(".eligi")
            eligibility = []
            for elem in eligibility_elements:
                eligibility.append(await elem.inner_text())
            details["eligibility"] = eligibility
            
            # Extract registration fee
            fee_element = await page.query_selector('.reg_fee span')
            if fee_element:
                details["registration_fee"] = await fee_element.inner_text()

            details["status"] = 'open'
            details['url'] = url
            details['source']='Unstop'
            return details
            
        except Exception as e:
            print(f"Error getting details for {opportunity_id}: {e}")
            return {}
        
        finally:
            await browser.close()

async def scrape_unstop():
    events = []
    hackathons = await scrape_unstop_link()

    # Get detailed info for hackathons
    # detailed_hackathons = []
    for hackathon in hackathons:
        if hackathon.get("opportunity_id"):
            # print(f"\nGetting details for: {hackathon['title']}")
            details = await get_hackathon_details(hackathon["opportunity_id"])
            details['domain']=hackathon['tags']
            details['name'] = hackathon['title']
            events.append(details)
            # print(details)
            await asyncio.sleep(2)
    return events

client = MongoClient(os.getenv('DATABASE_URL'))
db = client["hackathon_db"]
col = db["events"]

def store_events(events):
    for event in events:
        col.update_one({"name": event["name"]}, { '$set' :event}, upsert=True)
        
async def main():
    d1 = scrape_devfolio()
    d2= await scrape_unstop()
    store_events(d1+d2)
    print(d2)

if __name__ == "__main__":
    asyncio.run(main())