import os
import json
import requests
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
from threading import Thread
import time
from bs4 import BeautifulSoup
import openai
import logging
from urllib.parse import urljoin, urlparse
import re
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from functools import wraps
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not found in environment variables")

# OpenAI API Configuration for OpenRouter
def get_openai_client():
    """Initialize OpenAI client with OpenRouter configuration"""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not configured")
        return None
    
    try:
        import httpx
        client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.Client(timeout=30.0)
        )
        return client
    except Exception as e:
        logger.error(f"Error creating OpenAI client: {e}")
        return None

# Database setup
def init_db():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id TEXT UNIQUE,
        title TEXT,
        issuing_authority TEXT,
        category TEXT,
        department TEXT,
        location TEXT,
        publish_date TEXT,
        deadline_date TEXT,
        source_url TEXT,
        description TEXT,
        tender_value REAL,
        status TEXT DEFAULT 'active',
        source_portal TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ai_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id TEXT,
        prompt_type TEXT,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tender_id) REFERENCES tenders (tender_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create default admin user if not exists
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        password_hash = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                 ('admin', password_hash, 'admin@example.com'))
    
    conn.commit()
    conn.close()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Tender scraping functions
class TenderScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def fetch_with_retry(self, url, max_retries=3, timeout=10):
        """Fetch URL with retry mechanism"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response
                else:
                    logger.warning(f"Failed to fetch {url} - Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def scrape_government_portals(self):
        """Scrape various government portals for tenders"""
        portal_urls = [
            'https://eproc2.bihar.gov.in/EPSV2Web/openarea/tenderListingPage.action',
            'https://jharkhandtenders.gov.in/nicgep/app?page=WebTenderStatusLists&service=page',
            'https://gem.gov.in/',
            'https://eprocure.gov.in/eprocure/app',
            'https://etender.cpwd.gov.in/',
            'https://www.buidco.in/ActiveTenders.aspx',
            'https://bseidc.in/active_tender.php',
            'https://sbpdcl.co.in/',
            'https://nbpdcl.co.in/',
            'https://www.bepcssa.in/en/tenders.php',
            'https://patnasmartcity.in/',
            'https://jsbccl.jharkhand.gov.in/tenders',
            'https://jbvnl.co.in/',
            'https://www.ireps.gov.in/',
            'https://rvnl.org/tenders',
            'https://www.rites.com/web/index.php/tender',
            'https://ircon.org/index.php/tender',
            'https://www.railvikas.gov.in/',
            'https://www.iitp.ac.in/index.php/en-us/tenders',
            'https://www.nitp.ac.in/tenders',
            'https://nitjsr.ac.in/',
            'https://www.iitism.ac.in/index.php/tenders',
            'https://www.sail.co.in/en/tenders',
            'https://www.coalindia.in/en-us/tenders.aspx',
            'https://ntpctender.ntpc.co.in/',
            'https://www.bhel.com/eprocurement/',
            'https://www.seci.co.in/show_tenders.php',
            'https://iocletenders.nic.in/',
            'https://www.pmgsytendersbih.gov.in/',
            'https://www.nhai.gov.in/en/tenders',
            'https://morth.nic.in/',
            'https://nhidcl.com/tenders/'
        ]
        
        all_tenders = []
        for url in portal_urls:
            try:
                logger.info(f"Scraping: {url}")
                response = self.fetch_with_retry(url)
                if response:
                    tenders = self.parse_tenders_from_response(response, url)
                    all_tenders.extend(tenders)
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                continue
        
        return all_tenders
    
    def parse_tenders_from_response(self, response, base_url):
        """Parse tenders from HTML response"""
        soup = BeautifulSoup(response.content, 'html.parser')
        tenders = []
        
        # Different parsing strategies for different portal types
        if 'eproc2.bihar.gov.in' in base_url:
            tenders.extend(self.parse_bihar_eproc(soup, base_url))
        elif 'jharkhandtenders.gov.in' in base_url:
            tenders.extend(self.parse_jharkhand_tenders(soup, base_url))
        elif 'gem.gov.in' in base_url:
            tenders.extend(self.parse_gem_portal(soup, base_url))
        elif 'eprocure.gov.in' in base_url:
            tenders.extend(self.parse_eprocure_portal(soup, base_url))
        elif 'buidco.in' in base_url:
            tenders.extend(self.parse_buidco_portal(soup, base_url))
        else:
            # Generic parsing for other portals
            tenders.extend(self.parse_generic_portal(soup, base_url))
        
        return tenders
    
    def parse_bihar_eproc(self, soup, base_url):
        """Parse Bihar eProcurement portal"""
        tenders = []
        # Look for common tender table elements
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 3:
                    try:
                        title = cols[0].get_text(strip=True)
                        org = cols[1].get_text(strip=True)
                        deadline_date = cols[2].get_text(strip=True)
                        
                        tender = {
                            'title': title,
                            'issuing_authority': org,
                            'deadline_date': deadline_date,
                            'source_portal': base_url,
                            'description': title
                        }
                        tenders.append(tender)
                    except IndexError:
                        continue
        return tenders
    
    def parse_jharkhand_tenders(self, soup, base_url):
        """Parse Jharkhand Tenders portal"""
        tenders = []
        # Find tender links and details
        tender_links = soup.find_all('a', href=re.compile(r'/tender|/notice|/bid'))
        for link in tender_links:
            title = link.get_text(strip=True)
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                tender = {
                    'title': title,
                    'issuing_authority': 'Jharkhand Government',
                    'source_url': full_url,
                    'source_portal': base_url,
                    'description': title
                }
                tenders.append(tender)
        return tenders
    
    def parse_gem_portal(self, soup, base_url):
        """Parse GEM portal"""
        tenders = []
        # Look for tender cards or listings
        tender_cards = soup.find_all(['div', 'article'], class_=re.compile(r'tender|card|listing'))
        for card in tender_cards:
            title_elem = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span'], 
                                  class_=re.compile(r'title|name|heading'))
            if title_elem:
                title = title_elem.get_text(strip=True)
                tender = {
                    'title': title,
                    'issuing_authority': 'Government e-Marketplace',
                    'source_portal': base_url,
                    'description': title
                }
                tenders.append(tender)
        return tenders
    
    def parse_eprocure_portal(self, soup, base_url):
        """Parse eProcure portal"""
        tenders = []
        # Look for tender tables or divs
        elements = soup.find_all(['table', 'div'], class_=re.compile(r'tender|list|data'))
        for element in elements:
            rows = element.find_all('tr') if element.name == 'table' else element.find_all(['div', 'article'])
            for row in rows:
                title_elem = row.find(['div', 'span', 'p'], recursive=False)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if len(title) > 10:  # Filter out short text
                        tender = {
                            'title': title,
                            'issuing_authority': 'Central Public Procurement Portal',
                            'source_portal': base_url,
                            'description': title
                        }
                        tenders.append(tender)
        return tenders
    
    def parse_buidco_portal(self, soup, base_url):
        """Parse BUIDCO portal"""
        tenders = []
        # Look for active tenders section
        active_tenders = soup.find(id='ActiveTenders') or soup.find(class_='tender-list')
        if active_tenders:
            links = active_tenders.find_all('a')
            for link in links:
                title = link.get_text(strip=True)
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    tender = {
                        'title': title,
                        'issuing_authority': 'Bihar Urban Infrastructure Development Company',
                        'source_url': full_url,
                        'source_portal': base_url,
                        'description': title
                    }
                    tenders.append(tender)
        return tenders
    
    def parse_generic_portal(self, soup, base_url):
        """Generic parser for unknown portals"""
        tenders = []
        # Look for common tender-related keywords and elements
        keyword_elements = soup.find_all(string=re.compile(r'tender|Tender|bid|Bid|procurement|Procurement|notice|Notice'))
        
        for elem in keyword_elements:
            parent = elem.parent
            while parent and parent.name != 'body':
                # Look for titles/headers near the keyword
                title_elem = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'p'])
                if title_elem and len(title_elem.get_text(strip=True)) > 10:
                    title = title_elem.get_text(strip=True)
                    tender = {
                        'title': title,
                        'issuing_authority': urlparse(base_url).netloc,
                        'source_portal': base_url,
                        'description': title
                    }
                    tenders.append(tender)
                    break
                parent = parent.parent
        
        return tenders

# Initialize scraper
scraper = TenderScraper()

# Save tenders to database
def save_tenders_to_db(tenders):
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    saved_count = 0
    for tender in tenders:
        try:
            tender_id = str(uuid.uuid4())
            c.execute('''INSERT OR IGNORE INTO tenders 
                        (tender_id, title, issuing_authority, category, department, 
                         publish_date, deadline_date, source_url, description, 
                         tender_value, status, source_portal)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (tender_id, 
                      tender.get('title', ''),
                      tender.get('issuing_authority', ''),
                      tender.get('category', ''),
                      tender.get('department', ''),
                      tender.get('publish_date', ''),
                      tender.get('deadline_date', ''),
                      tender.get('source_url', ''),
                      tender.get('description', ''),
                      tender.get('tender_value'),
                      tender.get('status', 'active'),
                      tender.get('source_portal', '')))
            
            if c.rowcount > 0:
                saved_count += 1
        except sqlite3.Error as e:
            logger.error(f"Database error saving tender: {str(e)}")
            continue
    
    conn.commit()
    conn.close()
    return saved_count

# AI functionality with OpenRouter
def get_ai_response(prompt, model="openai/gpt-3.5-turbo"):
    """Get response from OpenRouter AI"""
    client = get_openai_client()
    if not client:
        # Mock AI responses for testing purposes
        import random
        mock_responses = {
            "proposal": "This is a mock proposal response. In a real implementation, this would contain a detailed proposal based on the tender requirements.",
            "risk": "This is a mock risk analysis. In a real implementation, this would analyze specific risks related to the tender.",
            "question": "This is a mock question generation. In a real implementation, this would generate relevant questions about the tender.",
            "summary": "This is a mock summary. In a real implementation, this would provide a concise summary of the tender.",
            "draft": "This is a mock email draft. In a real implementation, this would contain a professionally drafted email for the tender opportunity.",
            "match": "This is a mock supplier match analysis. In a real implementation, this would provide detailed analysis of how well a supplier matches the tender requirements.",
            "default": "This is a mock AI response. The OpenAI/OpenRouter module is not properly configured in this environment."
        }
        
        if "proposal" in prompt.lower():
            return mock_responses["proposal"]
        elif "risk" in prompt.lower():
            return mock_responses["risk"]
        elif "question" in prompt.lower() or "ask" in prompt.lower():
            return mock_responses["question"]
        elif "summar" in prompt.lower():
            return mock_responses["summary"]
        elif "draft" in prompt.lower() or "email" in prompt.lower():
            return mock_responses["draft"]
        elif "match" in prompt.lower() or "supplier" in prompt.lower():
            return mock_responses["match"]
        else:
            return mock_responses["default"]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert assistant specialized in tender analysis, proposal writing, risk assessment, and procurement processes. Provide accurate, professional, and helpful responses."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI/OpenRouter API error: {str(e)}")
        return f"AI service error: {str(e)}"

@app.route('/')
def index():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open'")
    total = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open' AND deadline_date != '' AND deadline_date IS NOT NULL")
    open_count = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open' AND (location LIKE '%Bihar%' OR state='Bihar')")
    bihar = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open' AND (location='Jharkhand' OR state='Jharkhand')")
    jharkhand = c.fetchone()[0] or 0
    
    conn.close()
    
    return render_template('index.html',
                         total_tenders=total,
                         open_tenders=open_count,
                         bihar_tenders=bihar,
                         jharkhand_tenders=jharkhand)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user[1], password):
        session['user_id'] = user[0]
        session['username'] = username
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/scrape_tenders', methods=['POST'])
@login_required
def scrape_tenders():
    try:
        tenders = scraper.scrape_government_portals()
        saved_count = save_tenders_to_db(tenders)
        return jsonify({
            'success': True,
            'message': f'Scraped {len(tenders)} tenders, saved {saved_count} to database'
        })
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error during scraping: {str(e)}'
        })

@app.route('/api/ai/draft_proposal', methods=['POST'])
@login_required
def draft_proposal():
    data = request.json
    tender_id = data.get('tender_id')
    custom_prompt = data.get('prompt', '')
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority = tender
    
    if custom_prompt:
        prompt = custom_prompt
    else:
        prompt = f"""Draft a comprehensive proposal for the following tender:

Title: {title}
Organization: {issuing_authority}
Description: {description}

The proposal should include executive summary, technical approach, methodology, timeline, team qualifications, and pricing strategy."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'proposal_draft', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/analyze_risk', methods=['POST'])
@login_required
def analyze_risk():
    data = request.json
    tender_id = data.get('tender_id')
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority, deadline_date FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority, deadline_date = tender
    
    prompt = f"""Analyze the risk factors for this tender:
Title: {title}
Organization: {issuing_authority}
Description: {description}
Closing Date: {deadline_date}

Provide a risk assessment with categories: High Risk, Medium Risk, Low Risk. Include financial, technical, regulatory, and deadline risks."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'risk_analysis', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/generate_questions', methods=['POST'])
@login_required
def generate_questions():
    data = request.json
    tender_id = data.get('tender_id')
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority = tender
    
    prompt = f"""Generate important questions to ask about this tender for better understanding:
Title: {title}
Organization: {issuing_authority}
Description: {description}"""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'questions_generation', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/summarize_tender', methods=['POST'])
@login_required
def summarize_tender():
    data = request.json
    tender_id = data.get('tender_id')
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority = tender
    
    prompt = f"""Summarize this tender in a clear, concise way highlighting key points:
Title: {title}
Organization: {issuing_authority}
Description: {description}

Include key requirements, deadlines, and opportunities."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'summary', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/custom_prompt', methods=['POST'])
@login_required
def custom_ai_prompt():
    data = request.json
    tender_id = data.get('tender_id')
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'})
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if tender:
        title, description, issuing_authority = tender
        full_prompt = f"Tender Information:\nTitle: {title}\nOrganization: {issuing_authority}\nDescription: {description}\n\nUser Query: {prompt}"
    else:
        full_prompt = prompt

    response = get_ai_response(full_prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'custom', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/responses/<tender_id>')
@login_required
def get_ai_responses(tender_id):
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT prompt_type, response, created_at FROM ai_responses WHERE tender_id=? ORDER BY created_at DESC", (tender_id,))
    responses = c.fetchall()
    conn.close()
    
    return jsonify([
        {
            'prompt_type': r[0],
            'response': r[1],
            'created_at': r[2]
        } for r in responses
    ])

@app.route('/api/dashboard_stats')
@login_required
def dashboard_stats():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    # Total tenders
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open'")
    total_tenders = c.fetchone()[0]
    
    # Tenders by category
    c.execute("SELECT category, COUNT(*) FROM tenders WHERE status='open' GROUP BY category")
    category_counts = dict(c.fetchall())
    
    # Tenders by department
    c.execute("SELECT department, COUNT(*) FROM tenders WHERE status='open' GROUP BY department LIMIT 10")
    department_counts = dict(c.fetchall())
    
    # Tenders expiring soon (next 7 days)
    c.execute("""SELECT COUNT(*) FROM tenders 
                WHERE status='open' 
                AND deadline_date IS NOT NULL 
                AND deadline_date != ''
                AND date(deadline_date) BETWEEN date('now') AND date('now', '+7 days')""")
    expiring_soon = c.fetchone()[0]
    
    # Recent activity (last 24 hours)
    c.execute("SELECT COUNT(*) FROM tenders WHERE created_at >= datetime('now', '-1 day')")
    recent_added = c.fetchone()[0]
    
    # Top issuing_authoritys
    c.execute("SELECT issuing_authority, COUNT(*) FROM tenders WHERE status='open' GROUP BY issuing_authority ORDER BY COUNT(*) DESC LIMIT 5")
    top_orgs = dict(c.fetchall())
    
    # Tenders by month (for trend analysis)
    c.execute("""SELECT strftime('%Y-%m', created_at) as month, COUNT(*) 
                FROM tenders 
                WHERE status='open' 
                GROUP BY month 
                ORDER BY month DESC 
                LIMIT 6""")
    monthly_trends = dict(c.fetchall())
    
    conn.close()
    
    return jsonify({
        'total_tenders': total_tenders,
        'categories': category_counts,
        'departments': department_counts,
        'expiring_soon': expiring_soon,
        'recently_added': recent_added,
        'top_issuing_authoritys': top_orgs,
        'monthly_trends': monthly_trends
    })

@app.route('/api/export_tenders', methods=['GET'])
@login_required
def export_tenders():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tenders WHERE status='open' ORDER BY created_at DESC")
    tenders = c.fetchall()
    conn.close()
    
    # Convert to CSV format
    csv_content = "ID,Title,Organization,Category,Department,Published Date,Closing Date,Tender URL,Description,Budget Amount,Status,Source Portal,Created At\n"
    for tender in tenders:
        # Escape quotes and handle commas in fields
        escaped_fields = []
        for field in tender[1:]:  # Skip the ID field (index 0) since we're using position-based access
            if field is None:
                escaped_fields.append('')
            else:
                field_str = str(field).replace('"', '""')  # Escape quotes
                if ',' in field_str or '\n' in field_str or '"' in field_str:
                    field_str = f'"{field_str}"'  # Wrap in quotes if it contains special characters
                escaped_fields.append(field_str)
        
        csv_content += ','.join(escaped_fields) + '\n'
    
    return csv_content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=tenders_export.csv'
    }

@app.route('/api/ai/draft_email', methods=['POST'])
@login_required
def draft_email():
    """Draft a professional email for tender inquiry/proposal submission"""
    data = request.json
    tender_id = data.get('tender_id')
    email_type = data.get('type', 'inquiry')  # inquiry, proposal, follow_up
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority, deadline_date FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority, deadline_date = tender
    
    if email_type == 'inquiry':
        prompt = f"""Draft a professional business inquiry email for the following tender opportunity:
        
        Tender Title: {title}
        Organization: {issuing_authority}
        Description: {description}
        Closing Date: {deadline_date}

        The email should be formal, concise, express interest in the tender, request additional information if needed, and highlight our company's capabilities."""
    elif email_type == 'proposal':
        prompt = f"""Draft a professional proposal submission email for the following tender:
        
        Tender Title: {title}
        Organization: {issuing_authority}
        Description: {description}
        Closing Date: {deadline_date}

        The email should acknowledge receipt of tender details, confirm our intention to submit a proposal, mention key strengths that match the requirements, and indicate next steps."""
    elif email_type == 'follow_up':
        prompt = f"""Draft a professional follow-up email regarding the following tender:
        
        Tender Title: {title}
        Organization: {issuing_authority}
        Description: {description}
        Closing Date: {deadline_date}

        The email should politely inquire about the status, offer additional information if needed, and express continued interest in the opportunity."""
    else:
        prompt = f"""Draft a professional email regarding the following tender opportunity:
        
        Tender Title: {title}
        Organization: {issuing_authority}
        Description: {description}
        Closing Date: {deadline_date}

        The email should be appropriate for business development purposes."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, f'email_draft_{email_type}', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/match_analysis', methods=['POST'])
@login_required
def match_analysis():
    """Analyze how well a supplier matches a tender requirement"""
    data = request.json
    tender_id = data.get('tender_id')
    supplier_profile = data.get('supplier_profile', '')
    
    # Get tender details
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, issuing_authority FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, issuing_authority = tender
    
    prompt = f"""Perform a detailed supplier-tender matching analysis:

    TENDER INFORMATION:
    Title: {title}
    Organization: {issuing_authority}
    Description: {description}

    SUPPLIER PROFILE:
    {supplier_profile}

    Please provide:
    1. Compatibility Score (0-100)
    2. Key Strengths (where supplier matches well)
    3. Potential Gaps (areas where supplier might need improvement)
    4. Recommendation (pursue/not pursue with justification)
    5. Action Items (specific steps to improve chances)"""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'match_analysis', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/market_insights', methods=['GET'])
@login_required
def market_insights():
    """Generate market insights from all tenders in the database"""
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    # Get all tenders for analysis
    c.execute("SELECT title, description, issuing_authority, category, department, source_portal FROM tenders WHERE status='open' ORDER BY created_at DESC LIMIT 100")
    tenders = c.fetchall()
    conn.close()
    
    if not tenders:
        return jsonify({'insights': 'No tenders available for analysis'})
    
    # Prepare data for AI analysis
    tender_summaries = []
    for tender in tenders:
        summary = f"Title: {tender[0]}, Category: {tender[2]}, Department: {tender[3]}, Organization: {tender[2]}"
        tender_summaries.append(summary)
    
    tender_data = "\n".join(tender_summaries[:20])  # Limit to first 20 for performance
    
    prompt = f"""Analyze the following tender data for market insights:

    {tender_data}

    Please provide:
    1. Market Trends (emerging areas, popular sectors)
    2. Opportunity Hotspots (high-activity regions/sectors)
    3. Competition Analysis (which areas seem highly competitive)
    4. Seasonal Patterns (if any can be inferred)
    5. Strategic Recommendations for businesses looking to enter these markets"""

    response = get_ai_response(prompt)
    
    return jsonify({'insights': response})

@app.route('/metrics')
def metrics():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open'")
    total = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open'")
    open_count = c.fetchone()[0] or 0
    
    # Use location OR state field - these are exclusive
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open' AND (location LIKE '%Bihar%' OR state='Bihar')")
    bihar = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='open' AND (location='Jharkhand' OR state='Jharkhand')")
    jharkhand = c.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_tenders': total,
        'open_tenders': open_count,
        'bihar_tenders': bihar,
        'jharkhand_tenders': jharkhand
    })

@app.route('/api/tenders')
def api_tenders():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    search = request.args.get('search', '')
    state = request.args.get('state', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', 'date_desc')
    
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    # Build WHERE clause
    conditions = ["status='open'"]
    query_params = []
    
    if search:
        conditions.append("(title LIKE ? OR description LIKE ? OR issuing_authority LIKE ?)")
        sp = f"%{search}%"
        query_params.extend([sp, sp, sp])
    
    if state:
        conditions.append("(location LIKE ? OR state LIKE ?)")
        query_params.extend([f"%{state}%", f"%{state}%"])
    
    if category:
        conditions.append("category LIKE ?")
        query_params.extend([f"%{category}%"])
    
    where_clause = " AND ".join(conditions)
    
    # Handle sorting - add to conditions and params BEFORE building query
    if sort == 'medical':
        conditions.append("(title LIKE ? OR description LIKE ?)")
        mk = '%'.join(['hospital', 'medical', 'health', 'nursing', 'pharmacy', 'doctor', 'clinical', 'diagnostic', 'treatment', 'patient', 'ambulance', 'medicine', 'drug', 'surgery', 'surgical', 'oxygen', 'vaccine', 'pathology', 'laboratory', 'blood', 'eye', 'dental', 'cardiac', 'cancer', 'dialysis'])
        query_params.extend([f"%{mk}%", f"%{mk}%"])
    
    # Build WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Handle sorting
    order_by = "created_at DESC"
    if sort == 'date_asc':
        order_by = "created_at ASC"
    elif sort == 'value_desc':
        order_by = "tender_value DESC"
    elif sort == 'value_asc':
        order_by = "tender_value ASC"
    
    # Build and execute main query
    query = f"SELECT * FROM tenders WHERE {where_clause} ORDER BY {order_by} LIMIT {per_page} OFFSET {(page-1)*per_page}"
    c.execute(query, query_params)
    tenders = c.fetchall()
    
    # Count query
    count_query = f"SELECT COUNT(*) FROM tenders WHERE {where_clause}"
    c.execute(count_query, query_params)
    total = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'tenders': [
            {
                'id': t[0],
                'tender_id': t[1],
                'title': t[2],
                'organization': t[4],  # issuing_authority
                'category': t[12],
                'department': t[5],
                'location': t[14] or t[15] or '',  # location or state
                'source_portal': t[6],
                'publish_date': t[8],
                'deadline_date': t[9],
                'tender_value': t[10],
                'status': t[21],
                'description': t[3]
            } for t in tenders
        ],
        'total': total,
        'pages': (total + per_page - 1) // per_page,
        'current_page': page,
        'per_page': per_page
    })

@app.route('/fetch_manual', methods=['POST'])
def fetch_manual():
    def run_fetch():
        try:
            tenders = scraper.scrape_government_portals()
            save_tenders_to_db(tenders)
        except Exception as e:
            logger.error(f"Fetch error: {e}")
    
    thread = threading.Thread(target=run_fetch)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'message': 'Fetch started'})

@app.route('/cleanup_all', methods=['POST'])
def cleanup_all():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    deleted = 0
    
    c.execute("DELETE FROM tenders WHERE title IS NULL OR title = '' OR length(title) < 5")
    deleted += c.rowcount
    
    c.execute("DELETE FROM tenders WHERE source_url LIKE 'javascript:%'")
    deleted += c.rowcount
    
    c.execute("DELETE FROM tenders WHERE created_at < datetime('now', '-90 days')")
    deleted += c.rowcount
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted,
        'message': f'Cleaned {deleted} tenders'
    })

@app.route('/ai/health')
def ai_health():
    if not OPENROUTER_API_KEY:
        return jsonify({'status': 'error', 'message': 'API key not configured'})
    
    try:
        response = get_ai_response("Reply with OK")
        return jsonify({
            'status': 'healthy',
            'model': 'openai/gpt-3.5-turbo',
            'api_working': True
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ai/analyze_tender/<int:tender_id>')
def ai_analyze_tender(tender_id):
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT id, title, description, issuing_authority, category, department, source_url FROM tenders WHERE id=?", (tender_id,))
    tender = c.fetchone()
    
    if not tender:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Tender not found'}), 404
    
    t_id, title, desc, org, cat, dept, url = tender
    
    # Enhance prompt - rewrite and improve all fields
    enhance_prompt = f"""Analyze this tender and return JSON with ENHANCED/CLEANED versions of the data. 

Original tender:
- Title: {title}
- Description: {desc}
- Organization: {org}
- Category: {cat}
- Department: {dept}

Return JSON with improved/cleaned fields:
{{
    "enhanced_title": "Clean, professional title (max 100 chars)",
    "enhanced_description": "Cleaned description (max 500 chars)",
    "enhanced_category": "One word: Works/Goods/Services/Consultancy/Other",
    "detected_state": "Bihar or Jharkhand or Other",
    "detected_sector": "Healthcare/Education/Infrastructure/IT/Transportation/Agriculture/Power/Other",
 "2-3 sentence summary",
    "fit_score":    "summary": 0-100,
    "key_terms": ["term1", "term2"]
}}

Make the title more professional, clean the description, properly categorize it."""

    try:
        enhance_response = get_ai_response(enhance_prompt)
        import json
        import re
        match = re.search(r'\{.*\}', enhance_response, re.DOTALL)
        if match:
            enhanced = json.loads(match.group())
        else:
            enhanced = {}
    except:
        enhanced = {}
    
    # Save enhanced data to database
    try:
        enhanced_title = enhanced.get('enhanced_title', title)
        enhanced_desc = enhanced.get('enhanced_description', desc)
        enhanced_cat = enhanced.get('enhanced_category', cat)
        detected_state = enhanced.get('detected_state', '')
        detected_sector = enhanced.get('detected_sector', '')
        
        c.execute('''UPDATE tenders SET 
            title = ?, 
            description = ?, 
            category = ?,
            department = ?,
            location = ?
            WHERE id = ?''',
            (enhanced_title, enhanced_desc, enhanced_cat, detected_sector, detected_state, t_id))
        conn.commit()
        saved = True
    except Exception as e:
        saved = False
        print(f"Error saving enhanced data: {e}")
    
    conn.close()
    
    return jsonify({
        'status': 'success', 
        'analysis': {
            'summary': enhanced.get('summary', ''),
            'sector': enhanced.get('detected_sector', ''),
            'fit_score_for_medical_supplier': enhanced.get('fit_score', 50),
            'enhanced_title': enhanced.get('enhanced_title', title),
            'enhanced_description': enhanced.get('enhanced_description', desc),
            'enhanced_category': enhanced.get('enhanced_category', cat),
            'detected_state': enhanced.get('detected_state', ''),
            'saved_to_db': saved
        }
    })

@app.route('/ai/draft_email/<int:tender_id>', methods=['POST'])
def ai_draft_email(tender_id):
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT id, title, description, issuing_authority, deadline_date, category FROM tenders WHERE id=?", (tender_id,))
    tender = c.fetchone()
    
    if not tender:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Tender not found'}), 404
    
    t_id, title, desc, org, deadline, cat = tender
    
    # Enhance tender data first
    enhance_prompt = f"""Clean and enhance this tender data. Return JSON:
{{"enhanced_title": "professional title", "enhanced_desc": "clean description", "category": "Works/Goods/Services", "state": "Bihar/Jharkhand/Other"}}

Title: {title}
Description: {desc}
Organization: {org}"""
    
    try:
        enhance_resp = get_ai_response(enhance_prompt)
        import json, re
        m = re.search(r'\{.*\}', enhance_resp, re.DOTALL)
        if m:
            enh = json.loads(m.group())
            c.execute('''UPDATE tenders SET title=?, description=?, category=? WHERE id=?''',
                (enh.get('enhanced_title', title), enh.get('enhanced_desc', desc), 
                 enh.get('category', cat), t_id))
            conn.commit()
    except:
        pass
    
    # Now draft email
    prompt = f"""Draft a professional email to a supplier about this tender opportunity. Keep it concise and business-like.

Tender: {title}
Organization: {org}
Deadline: {deadline}

Company: CARP BIOTECH PRIVATE LIMITED"""

    email = get_ai_response(prompt)
    
    return jsonify({'status': 'success', 'email': email})

@app.route('/ai/batch_analyze', methods=['POST'])
def ai_batch_analyze():
    data = request.json or {}
    analyze_all = data.get('all', False)
    
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    
    if analyze_all:
        c.execute("SELECT id, title, description, issuing_authority FROM tenders WHERE status='open' LIMIT 50")
    else:
        tender_ids = data.get('tender_ids', [])
        if not tender_ids:
            return jsonify({'status': 'error', 'message': 'No tender IDs'}), 400
        placeholders = ','.join('?' * len(tender_ids))
        c.execute(f"SELECT id, title, description, issuing_authority FROM tenders WHERE id IN ({placeholders})", tender_ids)
    
    tenders = c.fetchall()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'count': len(tenders),
        'results': [{'tender_id': t[0], 'analysis': {}} for t in tenders]
    })

@app.route('/ai/filter_sort_tenders', methods=['POST'])
def ai_filter_sort_tenders():
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT id, title, description, issuing_authority, category FROM tenders WHERE status='open' ORDER BY created_at DESC LIMIT 25")
    tenders = c.fetchall()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'tenders': [{'tender': {
            'id': t[0], 'title': t[1], 'description': t[2], 'issuing_authority': t[3], 'category': t[4]
        }} for t in tenders],
        'total': len(tenders)
    })

@app.route('/toggle_auto_fetch', methods=['POST'])
def toggle_auto_fetch():
    return jsonify({'status': 'success', 'message': 'Auto-fetch toggled'})

@app.route('/export_csv')
def export_csv():
    import pandas as pd
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT id, tender_id, title, issuing_authority, category, department, location, state, publish_date, deadline_date, source_url, description, tender_value, status FROM tenders WHERE status='open'")
    rows = c.fetchall()
    conn.close()
    
    df = pd.DataFrame(rows, columns=['id','tender_id','title','issuing_authority','category','department','location','state','publish_date','deadline_date','source_url','description','tender_value','status'])
    
    csv_path = 'tenders_export.csv'
    df.to_csv(csv_path, index=False)
    
    from flask import send_file
    return send_file(csv_path, as_attachment=True, mimetype='text/csv')

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    return jsonify({'filename': 'report.pdf'})

@app.route('/tender/<int:tender_id>')
def tender_detail(tender_id):
    conn = sqlite3.connect('instance/tenders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tenders WHERE id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)