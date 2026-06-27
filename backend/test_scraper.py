import os
import json
from dotenv import load_dotenv
from ddgs import DDGS
from groq import Groq
from google import genai

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

def search_web(query):
    print(f"Searching web for: {query}")
    try:
        results = DDGS().text(query, max_results=3)
        context = ""
        for r in results:
            context += f"Title: {r['title']}\nSnippet: {r['body']}\n\n"
        return context
    except Exception as e:
        print(f"DDGS Error: {e}")
        return ""

def extract_metrics(college_name):
    # Search for college data
    q1 = f"{college_name} highest median placement LPA service based recruiter percentage 2023 2024"
    q2 = f"{college_name} BTech tuition fee hostel mess fee structure"
    q3 = f"{college_name} campus infrastructure hostel mess review rating"
    
    context = search_web(q1) + search_web(q2) + search_web(q3)
    
    prompt = f"""
    You are an expert admission counselor extracting metrics from search results for {college_name}.
    Based on the following search snippets, extract the numerical metrics requested.
    If a metric is not found, make an educated estimation based on similar colleges in India.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly (no markdown formatting, no comments):
    {{
      "highest_placement_lpa": float,
      "median_placement_lpa": float,
      "mass_recruiter_percent": int (0-100),
      "tuition_fee": int,
      "hostel_fee": int,
      "mess_fee": int,
      "city_avg_pg_cost": int,
      "infrastructure_score": float (0-10),
      "alumni_network_score": float (0-10),
      "hostel_rating": float (0-10),
      "mess_rating": float (0-10)
    }}
    """
    
    try:
        print(f"Trying Groq Llama-3 for {college_name}...")
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        data = response.choices[0].message.content
        return json.loads(data)
    except Exception as e:
        print(f"Groq failed: {e}. Falling back to Gemini...")
        try:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            data = response.text
            # Clean markdown if present
            if data.startswith("```json"):
                data = data[7:-3]
            return json.loads(data)
        except Exception as e2:
            print(f"Gemini failed: {e2}")
            return None

def extract_cutoffs(college_name):
    print(f"\n--- Testing Cutoff Extraction for {college_name} ---")
    q1 = f"{college_name} MHT CET cutoffs category wise GOPEN OBC SC ST 2023 2024"
    q2 = f"{college_name} JEE Mains Advanced cutoff percentiles 2023"
    q3 = f"{college_name} Direct Second Year Diploma DSE cutoff percentiles"
    
    context = search_web(q1) + search_web(q2) + search_web(q3)
    
    prompt = f"""
    You are an expert admission counselor extracting cutoff metrics from search results for {college_name}.
    Based on the following search snippets, extract the cutoff percentiles for various exams.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly:
    {{
      "cutoffs": [
        {{
          "exam_type": "MHT-CET", // or "JEE", "JEE-Adv", "Diploma"
          "category": "GOPEN", // or OBC, SC, ST, EWS
          "percentile": 99.4,
          "sml": 120 // or null if not found
        }}
      ]
    }}
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print("Testing Pipeline B (Placements/Fees)...")
    res1 = extract_metrics("COEP Pune Computer Engineering")
    print(json.dumps(res1, indent=2))
    
    print("\nTesting Pipeline A (Cutoffs)...")
    res2 = extract_cutoffs("COEP Pune Computer Engineering")
    print(json.dumps(res2, indent=2))
