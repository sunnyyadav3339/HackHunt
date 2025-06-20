import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import time
from pymongo import MongoClient

# Define headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
}

# Placeholder for storing scraped events
events = []

# Devfolio Scraper
def scrape_devfolio():
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
            "source":"DevFolio"
    })

client = MongoClient("mongodb+srv://adityas1:adityas1@clusterhai.lmq5kse.mongodb.net/?retryWrites=true&w=majority&appName=ClusterHai")
db = client["hackathon_db"]
col = db["events"]

def store_events(events):
    for event in events:
        col.update_one({"name": event["name"]}, { '$set' :event}, upsert=True)
        
if __name__=='__main__':
    scrape_devfolio()
    store_events(events)