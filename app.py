import os
import json
import requests
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import sqlite3
from threading import Thread
import time
from bs4 import BeautifulSoup
try:
    import openrouter
    OPENROUTER_AVAILABLE = True
except ImportError:
    OPENROUTER_AVAILABLE = False
    print("Warning: openrouter module not available. AI features will use mock responses.")
import logging
from urllib.parse import urljoin, urlparse
import re
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not found in environment variables")

# Database setup
def init_db():
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id TEXT UNIQUE,
        title TEXT,
        organization TEXT,
        category TEXT,
        department TEXT,
        published_date TEXT,
        closing_date TEXT,
        tender_url TEXT,
        description TEXT,
        budget_amount REAL,
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
                        closing_date = cols[2].get_text(strip=True)
                        
                        tender = {
                            'title': title,
                            'organization': org,
                            'closing_date': closing_date,
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
                    'organization': 'Jharkhand Government',
                    'tender_url': full_url,
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
                    'organization': 'Government e-Marketplace',
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
                            'organization': 'Central Public Procurement Portal',
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
                        'organization': 'Bihar Urban Infrastructure Development Company',
                        'tender_url': full_url,
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
                        'organization': urlparse(base_url).netloc,
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    
    saved_count = 0
    for tender in tenders:
        try:
            tender_id = str(uuid.uuid4())
            c.execute('''INSERT OR IGNORE INTO tenders 
                        (tender_id, title, organization, category, department, 
                         published_date, closing_date, tender_url, description, 
                         budget_amount, status, source_portal)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (tender_id, 
                      tender.get('title', ''),
                      tender.get('organization', ''),
                      tender.get('category', ''),
                      tender.get('department', ''),
                      tender.get('published_date', ''),
                      tender.get('closing_date', ''),
                      tender.get('tender_url', ''),
                      tender.get('description', ''),
                      tender.get('budget_amount'),
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
    if not OPENROUTER_AVAILABLE:
        # Mock AI responses for testing purposes
        import random
        mock_responses = {
            "proposal": "This is a mock proposal response. In a real implementation, this would contain a detailed proposal based on the tender requirements.",
            "risk": "This is a mock risk analysis. In a real implementation, this would analyze specific risks related to the tender.",
            "question": "This is a mock question generation. In a real implementation, this would generate relevant questions about the tender.",
            "summary": "This is a mock summary. In a real implementation, this would provide a concise summary of the tender.",
            "default": "This is a mock AI response. The OpenRouter module is not available in this environment."
        }
        
        if "proposal" in prompt.lower():
            return mock_responses["proposal"]
        elif "risk" in prompt.lower():
            return mock_responses["risk"]
        elif "question" in prompt.lower() or "ask" in prompt.lower():
            return mock_responses["question"]
        elif "summar" in prompt.lower():
            return mock_responses["summary"]
        else:
            return mock_responses["default"]
    
    if not OPENROUTER_API_KEY:
        return "OpenRouter API key not configured"
    
    try:
        response = openrouter.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenRouter API error: {str(e)}")
        return f"AI service error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('tenders.db')
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

@app.route('/api/tenders')
@login_required
def get_tenders():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    
    query = "SELECT * FROM tenders WHERE status='active'"
    params = []
    
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR organization LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category}%")
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, (page - 1) * limit])
    
    c.execute(query, params)
    tenders = c.fetchall()
    
    # Get total count for pagination
    count_query = "SELECT COUNT(*) FROM tenders WHERE status='active'"
    count_params = []
    
    if search:
        count_query += " AND (title LIKE ? OR description LIKE ? OR organization LIKE ?)"
        count_params.extend([search_param, search_param, search_param])
    
    if category:
        count_query += " AND category LIKE ?"
        count_params.append(f"%{category}%")
    
    c.execute(count_query, count_params)
    total = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'tenders': [
            {
                'id': t[0],
                'tender_id': t[1],
                'title': t[2],
                'organization': t[3],
                'category': t[4],
                'department': t[5],
                'published_date': t[6],
                'closing_date': t[7],
                'tender_url': t[8],
                'description': t[9],
                'budget_amount': t[10],
                'status': t[11],
                'source_portal': t[12],
                'created_at': t[13]
            } for t in tenders
        ],
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    })

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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, organization FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, organization = tender
    
    if custom_prompt:
        prompt = custom_prompt
    else:
        prompt = f"""Draft a comprehensive proposal for the following tender:

Title: {title}
Organization: {organization}
Description: {description}

The proposal should include executive summary, technical approach, methodology, timeline, team qualifications, and pricing strategy."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('tenders.db')
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, organization, closing_date FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, organization, closing_date = tender
    
    prompt = f"""Analyze the risk factors for this tender:
Title: {title}
Organization: {organization}
Description: {description}
Closing Date: {closing_date}

Provide a risk assessment with categories: High Risk, Medium Risk, Low Risk. Include financial, technical, regulatory, and deadline risks."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('tenders.db')
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, organization FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, organization = tender
    
    prompt = f"""Generate important questions to ask about this tender for better understanding:
Title: {title}
Organization: {organization}
Description: {description}"""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('tenders.db')
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, organization FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if not tender:
        return jsonify({'error': 'Tender not found'})
    
    title, description, organization = tender
    
    prompt = f"""Summarize this tender in a clear, concise way highlighting key points:
Title: {title}
Organization: {organization}
Description: {description}

Include key requirements, deadlines, and opportunities."""

    response = get_ai_response(prompt)
    
    # Save AI response
    conn = sqlite3.connect('tenders.db')
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT title, description, organization FROM tenders WHERE tender_id=?", (tender_id,))
    tender = c.fetchone()
    conn.close()
    
    if tender:
        title, description, organization = tender
        full_prompt = f"Tender Information:\nTitle: {title}\nOrganization: {organization}\nDescription: {description}\n\nUser Query: {prompt}"
    else:
        full_prompt = prompt

    response = get_ai_response(full_prompt)
    
    # Save AI response
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("INSERT INTO ai_responses (tender_id, prompt_type, response) VALUES (?, ?, ?)",
              (tender_id, 'custom', response))
    conn.commit()
    conn.close()
    
    return jsonify({'response': response})

@app.route('/api/ai/responses/<tender_id>')
@login_required
def get_ai_responses(tender_id):
    conn = sqlite3.connect('tenders.db')
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
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    
    # Total tenders
    c.execute("SELECT COUNT(*) FROM tenders WHERE status='active'")
    total_tenders = c.fetchone()[0]
    
    # Tenders by category
    c.execute("SELECT category, COUNT(*) FROM tenders WHERE status='active' GROUP BY category")
    category_counts = dict(c.fetchall())
    
    # Tenders expiring soon (next 7 days)
    c.execute("""SELECT COUNT(*) FROM tenders 
                WHERE status='active' 
                AND closing_date IS NOT NULL 
                AND closing_date != ''
                AND date(closing_date) BETWEEN date('now') AND date('now', '+7 days')""")
    expiring_soon = c.fetchone()[0]
    
    # Recent activity (last 24 hours)
    c.execute("SELECT COUNT(*) FROM tenders WHERE created_at >= datetime('now', '-1 day')")
    recent_added = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_tenders': total_tenders,
        'categories': category_counts,
        'expiring_soon': expiring_soon,
        'recently_added': recent_added
    })

@app.route('/api/export_tenders', methods=['GET'])
@login_required
def export_tenders():
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tenders WHERE status='active' ORDER BY created_at DESC")
    tenders = c.fetchall()
    conn.close()
    
    # Convert to CSV format
    csv_content = "ID,Title,Organization,Category,Department,Published Date,Closing Date,Tender URL,Description,Budget Amount,Status,Source Portal,Created At\n"
    for tender in tenders:
        csv_content += f"{tender[1]},{tender[2]},{tender[3]},{tender[4]},{tender[5]},{tender[6]},{tender[7]},{tender[8]},{tender[9]},{tender[10]},{tender[11]},{tender[12]},{tender[13]}\n"
    
    return csv_content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=tenders_export.csv'
    }

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)