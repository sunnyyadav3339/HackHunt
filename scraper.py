import requests, re, time, asyncio, json, os,aiohttp
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

# Unstop Scraper
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

# Hackerearth scraper
async def scrape_challenge_links(url, status):
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Initialize the target data structure
    challenge_info = {
            'name': '',
            'link':url,
            'mode':'',
            'status':status,
            'prize_money': '',
            'deadline': '',
            'start_date': '',
            'end_date': '',
            'registration_fee': '',
            'source':"Hackerearth"
        }
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                content = await response.read()
                soup = BeautifulSoup(content, 'html.parser')
        
                # Extract Title
                title_selectors = [
                    'h1.challenge-title',
                    'h1.header-title',
                    '.challenge-header h1',
                    'h1',
                    'title'
                ]
                
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        challenge_info['name'] = title_elem.get_text().strip()
                        break
                
                mode = soup.find('div',class_ ='regular bold desc dark')
                if mode:
                    challenge_info['mode']=mode.get_text().strip()
                # Extract Prize Money
                prize_patterns = [
                    r'\$[\d,]+',
                    r'₹[\d,]+',
                    r'Prize.*?\$[\d,]+',
                    r'Cash.*?\$[\d,]+',
                    r'Worth.*?\$[\d,]+'
                ]
                
                page_text = soup.get_text()
                for pattern in prize_patterns:
                    prize_match = re.search(pattern, page_text, re.IGNORECASE)
                    if prize_match:
                        challenge_info['prize_money'] = prize_match.group().strip()
                        break
                
                # Look for prize information in specific elements
                prize_elements = soup.find_all(['div', 'span', 'p'], 
                                            text=re.compile(r'prize|reward|cash', re.IGNORECASE))
                for elem in prize_elements:
                    text = elem.get_text()
                    prize_match = re.search(r'\$[\d,]+|₹[\d,]+', text)
                    if prize_match and not challenge_info['prize_money']:
                        challenge_info['prize_money'] = prize_match.group()
                        break
                
                # Extract Dates (Start, End, Deadline)
                date_patterns = [
                    r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                    r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
                    r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
                    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})'
                ]
                
                # Look for date containers
                date_containers = soup.find_all(['div', 'span', 'p'], 
                                            class_=re.compile(r'date|time|deadline|start|end', re.IGNORECASE))
                
                dates_found = []
                for container in date_containers:
                    text = container.get_text()
                    for pattern in date_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        dates_found.extend(matches)
                
                # Also search in the entire page text
                for pattern in date_patterns:
                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                    dates_found.extend(matches)
                
                # Remove duplicates and assign dates
                unique_dates = list(set(dates_found))
                if len(unique_dates) >= 2:
                    challenge_info['start_date'] = unique_dates[0]
                    challenge_info['end_date'] = unique_dates[1]
                    challenge_info['deadline'] = unique_dates[-1] 
                elif len(unique_dates) == 1:
                    challenge_info['deadline'] = unique_dates[0]
                
                
                # Extract Registration Fee
                fee_patterns = [
                    r'registration.*?free',
                    r'free.*?registration',
                    r'no.*?fee',
                    r'fee.*?\$[\d,]+',
                    r'cost.*?\$[\d,]+',
                    r'₹[\d,]+.*?registration'
                ]
                
                for pattern in fee_patterns:
                    fee_match = re.search(pattern, page_text, re.IGNORECASE)
                    if fee_match:
                        challenge_info['registration_fee'] = fee_match.group().strip()
                        break
                
                # If no specific fee found, assume free (common for hackathons)
                if not challenge_info['registration_fee']:
                    if re.search(r'free|no cost|no fee', page_text, re.IGNORECASE):
                        challenge_info['registration_fee'] = 'Free'
                
                return challenge_info

    except Exception as e:
        print(f"Error: {e}")
        return None

async def scrape_hackerearth():    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Set to True for headless mode
        page = await browser.new_page()
        events = []
        
        try:
            await page.goto("https://www.hackerearth.com/challenges/?filters=hackathon")
            await page.wait_for_load_state("networkidle")

            html_content = await page.content()
            doc = BeautifulSoup(html_content, 'html.parser')
            
            # Find all challenge card links, not just one
            ong_chal = doc.find(class_='ongoing challenge-list').find_all('a', class_='challenge-card-wrapper challenge-card-link')
            link_on = []
            for link in ong_chal:
                href = link.get('href')
                link_on.append(scrape_challenge_links(href, 'Ongoing'))

            events= await asyncio.gather(*link_on)

        except Exception as e:
            print(e)

        finally:
            await browser.close()
            
        return events

client = MongoClient(os.getenv('MONGO_DB_URL'))
db = client["hackathon_db"]
col = db["events"]

def store_events(events):
    for event in events:
        col.update_one({"name": event["name"]}, { '$set' :event}, upsert=True)
        
async def scrape():
    d1 = scrape_devfolio()
    d2 = await scrape_unstop()
    d3 = await scrape_hackerearth()
    store_events(d1+d2+d3)

if __name__ == "__main__":
    asyncio.run(scrape())