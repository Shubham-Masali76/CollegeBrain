import sqlite3
import os
import json
import time
from groq import Groq
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
DB_PATH = os.path.join(os.path.dirname(__file__), "collegebrain.db")

def search_web(query):
    try:
        results = DDGS().text(query, max_results=3)
        return "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in results])
    except:
        return ""

def discover_colleges_for_region(region, limit=50):
    print(f"\n[AI Scout] Searching the web for Engineering Colleges in {region}...")
    context = search_web(f"List of AICTE DTE approved engineering colleges in {region} Maharashtra with DTE Institute Codes EN")
    
    prompt = f"""
    You are an AI data extractor. Using your internal knowledge and the search context below, 
    generate a list of up to {limit} engineering colleges located in or affiliated with {region}, Maharashtra.
    
    CRITICAL: You MUST include their official 4-digit or 6-digit DTE Maharashtra Institute Code (e.g. EN6006 for COEP, EN3012 for VJTI).
    
    Search Context:
    {context}
    
    Return ONLY a raw JSON array of objects. Do not use markdown backticks.
    [
      {{
        "institute_code": "EN6006",
        "name": "College of Engineering Pune",
        "city": "Pune"
      }}
    ]
    """
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # We will wrap the array in an object to satisfy Groq JSON mode
        )
        # Groq json_object mode requires returning an object, so let's adjust prompt on the fly
        pass
    except:
        pass

def discover_all():
    # Modified prompt for Groq JSON Mode
    regions = ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Amravati"]
    all_colleges = []
    
    for region in regions:
        print(f"\n[AI Scout] Searching the web for Engineering Colleges in {region}...")
        context = search_web(f"List of engineering colleges in {region} Maharashtra with DTE Institute Codes")
        
        prompt = f"""
        Generate a list of engineering colleges in {region}, Maharashtra.
        You MUST include their official DTE Maharashtra Institute Code (e.g. EN6006).
        
        Context: {context}
        
        Return ONLY valid JSON matching this exact schema:
        {{
          "colleges": [
            {{
              "institute_code": "EN6006",
              "name": "College of Engineering Pune",
              "city": "Pune"
            }}
          ]
        }}
        """
        
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            colleges = data.get("colleges", [])
            print(f" -> Found {len(colleges)} colleges in {region}!")
            all_colleges.extend(colleges)
        except Exception as e:
            print(f" -> Failed to extract for {region}: {e}")
            
        time.sleep(2) # rate limit
        
    return all_colleges

def seed_database():
    colleges = discover_all()
    
    print(f"\n[Database] Seeding {len(colleges)} discovered colleges into SQLite...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    for c in colleges:
        # Check if already exists to prevent duplicates
        cursor.execute("SELECT id FROM colleges WHERE institute_code = ?", (c['institute_code'],))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO colleges (institute_code, name, city, state, country, university)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c['institute_code'], c['name'], c['city'], 'Maharashtra', 'India', 'State University'))
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"[SUCCESS] Seeded {inserted} new colleges! You can now run live_scraper.py!")

if __name__ == "__main__":
    seed_database()
