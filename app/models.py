"""
Database models for the tender tracking system
"""
from app.extensions import db
from datetime import datetime
import json


class User(db.Model):
    """
    User model for authentication
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def check_password(self, password):
        """Check if provided password matches stored hash"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


class Tender(db.Model):
    """
    Main tender model storing all tender information
    """
    __tablename__ = 'tenders'
    
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.String(200), nullable=True, index=True)  # Portal's ID when available
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    issuing_authority = db.Column(db.String(200), nullable=True)
    department = db.Column(db.String(200), nullable=True)
    source_portal = db.Column(db.String(100), nullable=False)  # e.g., GEM, Jharkhand eProc
    source_url = db.Column(db.String(500), nullable=False)  # Full URL
    publish_date = db.Column(db.DateTime, nullable=True)  # ISO 8601
    deadline_date = db.Column(db.DateTime, nullable=True)  # ISO 8601
    tender_value = db.Column(db.Float, nullable=True)  # Numeric value
    currency = db.Column(db.String(10), nullable=True, default='INR')
    category = db.Column(db.String(50), nullable=True)  # works, goods, services
    sub_category = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)  # city/district/state - e.g., "Patna, Bihar" or "Ranchi, Jharkhand"
    attachments = db.Column(db.Text, nullable=True)  # JSON array of URLs
    contact_email = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    raw_html = db.Column(db.Text, nullable=True)  # Store raw if small or filename ref
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='open')  # open/closed/extended
    verification_score = db.Column(db.Integer, default=50)  # 0-100; higher = more confident
    supplier_matches = db.Column(db.Text, nullable=True)  # JSON: top 5 supplier suggestions
    ai_analysis = db.Column(db.Text, nullable=True)  # JSON: AI enhanced analysis
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Tender {self.title[:50]}...>'
    
    def to_dict(self):
        """Convert tender to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'tender_id': self.tender_id,
            'title': self.title,
            'description': self.description,
            'issuing_authority': self.issuing_authority,
            'department': self.department,
            'source_portal': self.source_portal,
            'source_url': self.source_url,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'deadline_date': self.deadline_date.isoformat() if self.deadline_date else None,
            'tender_value': self.tender_value,
            'currency': self.currency,
            'category': self.category,
            'sub_category': self.sub_category,
            'location': self.location,
            'attachments': json.loads(self.attachments) if self.attachments else [],
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'last_checked': self.last_checked.isoformat(),
            'status': self.status,
            'verification_score': self.verification_score,
            'supplier_matches': json.loads(self.supplier_matches) if self.supplier_matches else [],
            'ai_analysis': json.loads(self.ai_analysis) if self.ai_analysis else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @staticmethod
    def from_dict(data):
        """Create tender from dictionary"""
        attachments_json = json.dumps(data.get('attachments', [])) if data.get('attachments') else None
        supplier_matches_json = json.dumps(data.get('supplier_matches', [])) if data.get('supplier_matches') else None
        
        return Tender(
            tender_id=data.get('tender_id'),
            title=data.get('title'),
            description=data.get('description'),
            issuing_authority=data.get('issuing_authority'),
            department=data.get('department'),
            source_portal=data.get('source_portal'),
            source_url=data.get('source_url'),
            publish_date=datetime.fromisoformat(data['publish_date']) if data.get('publish_date') else None,
            deadline_date=datetime.fromisoformat(data['deadline_date']) if data.get('deadline_date') else None,
            tender_value=data.get('tender_value'),
            currency=data.get('currency'),
            category=data.get('category'),
            sub_category=data.get('sub_category'),
            location=data.get('location'),
            attachments=attachments_json,
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone'),
            last_checked=datetime.fromisoformat(data['last_checked']) if data.get('last_checked') else datetime.utcnow(),
            status=data.get('status', 'open'),
            verification_score=data.get('verification_score', 50),
            supplier_matches=supplier_matches_json
        )


class Supplier(db.Model):
    """
    Supplier model for supplier matching functionality
    """
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    products_services = db.Column(db.Text, nullable=True)  # JSON array of products/services
    categories = db.Column(db.Text, nullable=True)  # JSON array of categories
    certifications = db.Column(db.Text, nullable=True)  # JSON array of certifications
    experience_years = db.Column(db.Integer, nullable=True)
    rating = db.Column(db.Float, default=0.0)  # 0-5 rating
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert supplier to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'contact_person': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'products_services': json.loads(self.products_services) if self.products_services else [],
            'categories': json.loads(self.categories) if self.categories else [],
            'certifications': json.loads(self.certifications) if self.certifications else [],
            'experience_years': self.experience_years,
            'rating': self.rating,
            'verified': self.verified,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class FetchLog(db.Model):
    """
    Log model to track fetch operations
    """
    __tablename__ = 'fetch_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    source_portal = db.Column(db.String(100), nullable=False)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    total_processed = db.Column(db.Integer, default=0)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    error_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert log entry to dictionary"""
        return {
            'id': self.id,
            'source_portal': self.source_portal,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'total_processed': self.total_processed,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat()
        }