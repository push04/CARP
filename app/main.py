"""
Main Flask application blueprint
"""
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from app.models import Tender, Supplier, FetchLog
from app.extensions import db
from app.fetchers.tender_fetcher import TenderFetcher
from app.utils.pdf_generator import generate_pdf_report
from app.utils.supplier_matcher import SupplierMatcher
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import threading
import time
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

# Global variable to track auto-fetch status
auto_fetch_enabled = False
auto_fetch_thread = None

# Medical keywords for filtering
MEDICAL_KEYWORDS = [
    'hospital', 'medical', 'health', 'nursing', 'pharmacy', 'doctor', 'clinical',
    'diagnostic', 'treatment', 'patient', 'ambulance', 'medicine', 'drug', 'pharma',
    'surgery', 'surgical', 'operation', 'icu', 'ventilator', 'oxygen', 'covid',
    'vaccine', 'immunization', 'pathology', 'laboratory', 'x-ray', 'mri', 'ct scan',
    'blood', 'blood bank', 'donor', 'eye', 'dental', 'ent', 'orthopedic', 'pediatric',
    'gynec', 'maternity', 'neonatal', 'cardiac', 'cardiology', 'neurology', 'neuro',
    'oncology', 'cancer', 'renal', 'kidney', 'dialysis', 'physiotherapy', 'rehab',
    'aids', 'hiv', 'tb', 'tuberculosis', 'malaria', 'dengue', 'cholera',
    'sanitation', 'swachh', 'toilet', 'waste', 'bio medical', 'biomedical',
    'equipment', 'instrument', 'device', 'consumable', 'disposable', 'gloves',
    'mask', 'ppe', 'sanitizer', ' disinfectant', 'syringe', 'needle',
    'bed', 'wheelchair', 'stretcher', 'monitor', 'defibrillator', 'ecg', 'eeg',
    'anesthesia', 'anesthetic', 'radiology', 'ultrasound', 'xray', 'mammography',
    'nuclear medicine', 'radiotherapy', 'chemotherapy', 'biopsy', 'autopsy',
    'mortuary', 'ambulance', 'emergency', 'trauma', 'burn', 'plastic surgery',
    'mental health', 'psychiatry', 'psychology', 'depression', 'anxiety',
    'nutrition', 'diet', 'dietitian', 'food', 'catering', 'kitchen', 'menu',
    'cleaning', 'housekeeping', 'laundry', 'linen', 'cssd', 'sterilization',
    'security', 'fire safety', 'biomedical waste', 'hazardous waste',
    'health department', 'nhhm', 'national health', 'ayush', 'homoeopathy',
    'unani', 'siddha', 'ayurveda', 'yoga', 'naturopathy',
    'epidemic', 'outbreak', 'quarantine', 'isolation', 'containment',
    'public health', 'community health', 'primary health', 'phc', 'chc', 'sc',
    'sub centre', 'asha', 'anganwadi', 'icds', 'child health', 'rch',
    'family welfare', 'family planning', 'mch', 'mnch', 'jjm', 'jayi',
    'pmjay', 'ayushman', 'health insurance', 'medical college', 'nursing college',
    'paramedical', 'allied health', 'technician', 'therapist', 'radiographer',
    'laboratory technician', 'pharmacist', 'nurse', 'doctor', 'physician',
    'specialist', 'surgeon', 'anesthetist', 'pediatrician', 'gynecologist',
    'obstetrician', 'cardiologist', 'neurologist', 'oncologist', 'nephrologist',
    'urologist', 'gastroenterologist', 'dermatologist', 'psychiatrist',
    'ophthalmologist', 'ent specialist', 'orthopedist', 'pulmonologist',
]


@main_bp.route('/')
def index():
    """Main dashboard page"""
    # Get basic statistics - count all tenders with title
    total_tenders = Tender.query.filter(
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    open_tenders = Tender.query.filter(
        Tender.status == 'open',
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    bihar_tenders = Tender.query.filter(
        Tender.location.ilike('%bihar%'),
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    jharkhand_tenders = Tender.query.filter(
        Tender.location.ilike('%jharkhand%'),
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    # Get recent fetch logs
    recent_logs = FetchLog.query.order_by(FetchLog.created_at.desc()).limit(10).all()
    
    return render_template('index.html',
                         total_tenders=total_tenders,
                         open_tenders=open_tenders,
                         bihar_tenders=bihar_tenders,
                         jharkhand_tenders=jharkhand_tenders,
                         recent_logs=[log.to_dict() for log in recent_logs])


@main_bp.route('/api/tenders')
def api_tenders():
    """API endpoint to get tenders with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 25, type=int), 100)
    
    # Build query - show all tenders but filter out completely invalid ones
    query = Tender.query.filter(
        Tender.title.isnot(None),
        Tender.title != ''
    )
    
    # Medical tender filter
    medical_only = request.args.get('medical', 'false').lower() == 'true'
    if medical_only:
        from sqlalchemy import or_
        medical_conditions = [Tender.title.ilike(f'%{kw}%') for kw in MEDICAL_KEYWORDS]
        query = query.filter(or_(*medical_conditions))
    
    # Apply filters
    state_filter = request.args.get('state')
    if state_filter:
        # Use location for filtering (Bihar/Jharkhand)
        query = query.filter(Tender.location.ilike(f'%{state_filter}%'))
    
    category_filter = request.args.get('category')
    if category_filter:
        query = query.filter(Tender.category == category_filter)
    
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter(Tender.status == status_filter)
    
    # Date range filters
    start_date = request.args.get('start_date')
    if start_date:
        query = query.filter(Tender.publish_date >= datetime.fromisoformat(start_date))
    
    end_date = request.args.get('end_date')
    if end_date:
        query = query.filter(Tender.publish_date <= datetime.fromisoformat(end_date))
    
    # Search filter
    search_term = request.args.get('search')
    if search_term:
        query = query.filter(
            Tender.title.contains(search_term) |
            Tender.description.contains(search_term) |
            Tender.issuing_authority.contains(search_term)
        )
    
    # Sorting
    sort_by = request.args.get('sort_by', 'publish_date')
    sort_order = request.args.get('sort_order', 'desc')
    
    if hasattr(Tender, sort_by):
        column = getattr(Tender, sort_by)
        if sort_order.lower() == 'asc':
            query = query.order_by(column.asc())
        else:
            query = query.order_by(column.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tenders = [tender.to_dict() for tender in pagination.items]
    
    return jsonify({
        'tenders': tenders,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    })


@main_bp.route('/tender/<int:tender_id>')
def tender_detail(tender_id):
    """Detailed view of a specific tender"""
    tender = Tender.query.get_or_404(tender_id)
    
    # Parse JSON string fields so the template can iterate them
    supplier_matches = []
    if tender.supplier_matches:
        try:
            supplier_matches = json.loads(tender.supplier_matches)
            if not isinstance(supplier_matches, list):
                supplier_matches = []
        except (json.JSONDecodeError, TypeError):
            supplier_matches = []
    
    attachments = []
    if tender.attachments:
        try:
            attachments = json.loads(tender.attachments)
            if not isinstance(attachments, list):
                attachments = []
        except (json.JSONDecodeError, TypeError):
            attachments = []
    
    ai_analysis = None
    if tender.ai_analysis:
        try:
            ai_analysis = json.loads(tender.ai_analysis)
        except (json.JSONDecodeError, TypeError):
            ai_analysis = None
    
    return render_template('tender_detail.html',
                         tender=tender,
                         supplier_matches=supplier_matches,
                         attachments=attachments,
                         ai_analysis=ai_analysis)


@main_bp.route('/fetch_manual', methods=['POST'])
def fetch_manual():
    """Manually trigger a fetch operation"""
    from app import create_app
    from app.fetchers.tender_fetcher import TenderFetcher
    
    data = request.json or {}
    sources = data.get('sources', [])  # Specific sources to fetch from
    
    # Run fetch in background thread with app context
    def run_fetch():
        app = create_app()
        with app.app_context():
            fetcher = TenderFetcher()
            result = fetcher.fetch_all(sources=sources if sources else None)
            print(f"Manual fetch completed: {result}")
    
    thread = threading.Thread(target=run_fetch)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'message': 'Fetch operation started'})


@main_bp.route('/toggle_auto_fetch', methods=['POST'])
def toggle_auto_fetch():
    """Toggle auto-fetch functionality"""
    global auto_fetch_enabled, auto_fetch_thread
    
    data = request.json
    enabled = data.get('enabled', False)
    
    if enabled and not auto_fetch_enabled:
        # Start auto-fetch
        auto_fetch_enabled = True
        
        def run_auto_fetch():
            from app import create_app
            app = create_app()
            with app.app_context():
                fetcher = TenderFetcher()
                while auto_fetch_enabled:
                    try:
                        fetcher.fetch_all()
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f'Auto-fetch error: {e}')
                    time.sleep(int(os.getenv('AUTO_FETCH_INTERVAL', 1800)))
        
        auto_fetch_thread = threading.Thread(target=run_auto_fetch)
        auto_fetch_thread.daemon = True
        auto_fetch_thread.start()
        
        return jsonify({'status': 'enabled', 'message': 'Auto-fetch enabled'})
    
    elif not enabled and auto_fetch_enabled:
        # Stop auto-fetch
        auto_fetch_enabled = False
        return jsonify({'status': 'disabled', 'message': 'Auto-fetch disabled'})
    
    return jsonify({'status': 'unchanged'})


@main_bp.route('/delete_old_tenders', methods=['POST'])
def delete_old_tenders():
    """Delete tenders older than a specified number of days"""
    data = request.json
    days_old = data.get('days_old', 90)  # Default 90 days
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    old_tenders = Tender.query.filter(Tender.publish_date < cutoff_date).all()
    
    deleted_count = len(old_tenders)
    for tender in old_tenders:
        db.session.delete(tender)
    
    db.session.commit()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted_count,
        'message': f'Deleted {deleted_count} tenders older than {days_old} days'
    })


@main_bp.route('/export_csv')
def export_csv():
    """Export tenders to CSV file"""
    tenders = Tender.query.all()
    tender_dicts = [tender.to_dict() for tender in tenders]
    
    df = pd.DataFrame(tender_dicts)
    
    # Create temporary file
    temp_filename = f"tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(temp_filename, index=False)
    
    return send_file(temp_filename, as_attachment=True)


@main_bp.route('/export_pdf', methods=['POST'])
def export_pdf():
    """Export selected tenders to PDF report"""
    data = request.json
    tender_ids = data.get('tender_ids', [])
    
    if not tender_ids:
        return jsonify({'error': 'No tender IDs provided'}), 400
    
    tenders = Tender.query.filter(Tender.id.in_(tender_ids)).all()
    
    if not tenders:
        return jsonify({'error': 'No valid tender IDs provided'}), 400
    
    # Generate PDF report
    pdf_filename = generate_pdf_report(tenders, client_name="CARP BIOTECH PRIVATE LIMITED")
    
    return jsonify({'filename': pdf_filename})


@main_bp.route('/download_pdf/<filename>')
def download_pdf(filename):
    """Download generated PDF report"""
    import os
    from flask import send_from_directory
    
    # Get the directory where PDFs are saved
    pdf_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(pdf_dir, filename, as_attachment=True)


@main_bp.route('/get_supplier_matches/<int:tender_id>')
def get_supplier_matches(tender_id):
    """Get supplier matches for a specific tender"""
    tender = Tender.query.get_or_404(tender_id)
    
    matcher = SupplierMatcher()
    matches = matcher.find_supplier_matches(tender)
    
    # Update tender with supplier matches
    tender.supplier_matches = json.dumps(matches) if matches else None
    db.session.commit()
    
    return jsonify(matches)


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page for API keys and configurations"""
    if request.method == 'POST':
        # Update settings from form data
        # This would typically update environment variables or a settings table
        pass
    
    return render_template('settings.html')


@main_bp.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@main_bp.route('/metrics')
def metrics():
    """Metrics endpoint for monitoring"""
    # Count all tenders with title
    total_tenders = Tender.query.filter(
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    open_tenders = Tender.query.filter(
        Tender.status == 'open',
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    closed_tenders = Tender.query.filter(
        Tender.status == 'closed',
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    # Count by location (Bihar/Jharkhand)
    bihar_count = Tender.query.filter(
        Tender.location.ilike('%bihar%'),
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    jharkhand_count = Tender.query.filter(
        Tender.location.ilike('%jharkhand%'),
        Tender.title.isnot(None),
        Tender.title != ''
    ).count()
    
    return jsonify({
        'total_tenders': total_tenders,
        'open_tenders': open_tenders,
        'closed_tenders': closed_tenders,
        'bihar_tenders': bihar_count,
        'jharkhand_tenders': jharkhand_count,
        'auto_fetch_enabled': auto_fetch_enabled
    })


@main_bp.route('/remove_duplicates', methods=['POST'])
def remove_duplicates():
    """Remove duplicate tenders based on source_url and title similarity"""
    data = request.json or {}
    mode = data.get('mode', 'exact')  # exact or fuzzy
    
    deleted_count = 0
    
    if mode == 'exact':
        # Exact duplicate removal based on source_url
        subquery = db.session.query(
            Tender.source_url,
            db.func.max(Tender.id).label('max_id')
        ).group_by(Tender.source_url).subquery()
        
        # Delete all but the first occurrence
        to_delete = Tender.query.filter(
            Tender.id.notin_(
                db.session.query(subquery.c.max_id)
            ),
            Tender.source_url.in_(
                db.session.query(subquery.c.source_url)
            )
        ).all()
        
        for t in to_delete:
            db.session.delete(t)
            deleted_count += 1
        
    else:
        # Fuzzy matching based on title similarity
        all_tenders = Tender.query.all()
        seen_titles = {}
        
        for tender in all_tenders:
            if not tender.title:
                continue
            
            # Normalize title for comparison
            normalized = tender.title.lower().strip()
            
            # Check for similar titles
            found_duplicate = False
            for seen_title in seen_titles:
                # Simple similarity check
                if normalized == seen_title or normalized in seen_title or seen_title in normalized:
                    found_duplicate = True
                    db.session.delete(tender)
                    deleted_count += 1
                    break
            
            if not found_duplicate:
                seen_titles[normalized] = tender.id
    
    db.session.commit()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted_count,
        'message': f'Successfully removed {deleted_count} duplicate tenders'
    })


@main_bp.route('/cleanup_tenders', methods=['POST'])
def cleanup_tenders():
    """Clean up tenders with invalid/empty fields"""
    data = request.json or {}
    
    # Delete tenders with invalid authority
    deleted = Tender.query.filter(
        (Tender.issuing_authority == None) |
        (Tender.issuing_authority == '') |
        (Tender.issuing_authority == 'Unknown') |
        (Tender.issuing_authority.is_(None))
    ).delete(synchronize_session='fetch')
    
    db.session.commit()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted,
        'message': f'Successfully cleaned up {deleted} invalid tenders'
    })


@main_bp.route('/cleanup_junk_tenders', methods=['POST'])
def cleanup_junk_tenders():
    """Remove junk tenders with invalid titles and URLs"""
    data = request.json or {}
    
    # List of patterns to filter out
    junk_patterns = [
        'View', 'view', 'Click Here', 'click here',
        '2016-17', '2017-18', '2018-19', '2019-20',
        '2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26',
        '2006-07', '2007-08', '2008-09', '2009-10', '2010-11', '2011-12', '2012-13', '2013-14', '2014-15', '2015-16'
    ]
    
    # Build query to delete tenders with junk titles
    deleted = 0
    
    # 1. Delete tenders with javascript: URLs
    deleted += Tender.query.filter(
        Tender.source_url.like('javascript:%')
    ).delete(synchronize_session='fetch')
    
    # 2. Delete tenders with very short titles (less than 5 chars)
    deleted += Tender.query.filter(
        db.or_(
            db.and_(Tender.title != None, db.func.length(Tender.title) < 5),
            Tender.title == 'View',
            Tender.title == 'view'
        )
    ).delete(synchronize_session='fetch')
    
    # 3. Delete tenders with fiscal year titles (like 2016-17)
    for pattern in junk_patterns:
        deleted += Tender.query.filter(
            Tender.title == pattern
        ).delete(synchronize_session='fetch')
    
    # 4. Delete tenders with Unknown location and no meaningful data
    deleted += Tender.query.filter(
        Tender.location == None,
        db.or_(
            Tender.title == None,
            Tender.title == '',
            Tender.source_url == None,
            Tender.source_url == ''
        )
    ).delete(synchronize_session='fetch')
    
    db.session.commit()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted,
        'message': f'Successfully cleaned up {deleted} junk tenders'
    })


@main_bp.route('/cleanup_all', methods=['POST'])
def cleanup_all():
    """Complete cleanup: junk + duplicates + older than 90 days"""
    try:
        total_deleted = 0
        cleanup_details = []
        
        # 1. Delete junk tenders
        junk_patterns = [
            'View', 'view', 'Click Here', 'click here',
            '2016-17', '2017-18', '2018-19', '2019-20',
            '2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26',
            '2006-07', '2007-08', '2008-09', '2009-10', '2010-11', '2011-12', '2012-13', '2013-14', '2014-15', '2015-16'
        ]
        
        # Delete javascript URLs
        deleted = Tender.query.filter(Tender.source_url.like('javascript:%')).delete(synchronize_session='fetch')
        total_deleted += deleted
        if deleted > 0:
            cleanup_details.append(f"{deleted} junk (javascript URLs)")
        
        # Delete short/invalid titles
        deleted = Tender.query.filter(
            db.or_(
                db.and_(Tender.title != None, db.func.length(Tender.title) < 5),
                Tender.title == 'View',
                Tender.title == 'view'
            )
        ).delete(synchronize_session='fetch')
        total_deleted += deleted
        if deleted > 0:
            cleanup_details.append(f"{deleted} junk (short titles)")
        
        # Delete fiscal year patterns
        for pattern in junk_patterns:
            deleted = Tender.query.filter(Tender.title == pattern).delete(synchronize_session='fetch')
            total_deleted += deleted
        if deleted > 0:
            cleanup_details.append(f"{deleted} junk (fiscal year)")
        
        db.session.commit()
        
        # 2. Remove duplicates (keep oldest)
        subquery = db.session.query(
            Tender.source_url,
            db.func.min(Tender.id).label('min_id')
        ).group_by(Tender.source_url).having(db.func.count(Tender.id) > 1).subquery()
        
        duplicates = Tender.query.filter(
            Tender.source_url.in_(db.session.query(subquery.c.source_url)),
            Tender.id.notin_(db.session.query(subquery.c.min_id))
        ).all()
        
        deleted = len(duplicates)
        for t in duplicates:
            db.session.delete(t)
        total_deleted += deleted
        if deleted > 0:
            cleanup_details.append(f"{deleted} duplicates")
        
        # 3. Delete tenders older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        old_deleted = Tender.query.filter(
            Tender.publish_date < cutoff_date,
            Tender.publish_date != None
        ).delete(synchronize_session='fetch')
        total_deleted += old_deleted
        if old_deleted > 0:
            cleanup_details.append(f"{old_deleted} older than 90 days")
        
        db.session.commit()
        
        message = f"Cleaned: {', '.join(cleanup_details) if cleanup_details else 'No items removed'}"
        
        return jsonify({
            'status': 'completed',
            'deleted_count': total_deleted,
            'details': cleanup_details,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/get_data_quality')
def get_data_quality():
    """Get data quality statistics"""
    total = Tender.query.count()
    
    # Count valid tenders (meaningful title and valid URL)
    valid = Tender.query.filter(
        db.and_(
            db.func.length(Tender.title) >= 10,
            ~Tender.source_url.like('javascript:%'),
            Tender.source_url != '',
            Tender.source_url != None
        )
    ).count()
    
    # Count by location
    bihar = Tender.query.filter(Tender.location.ilike('%bihar%')).count()
    jharkhand = Tender.query.filter(Tender.location.ilike('%jharkhand%')).count()
    unknown = Tender.query.filter(~Tender.location.ilike('%bihar%'), ~Tender.location.ilike('%jharkhand%')).count()
    
    return jsonify({
        'total': total,
        'valid_tenders': valid,
        'bihar': bihar,
        'jharkhand': jharkhand,
        'unknown': unknown,
        'quality_percentage': round((valid / total * 100) if total > 0 else 0, 1)
    })


# ============== AI-POWERED TENDER ANALYSIS ==============

@main_bp.route('/ai/enhance_tender/<int:tender_id>', methods=['POST'])
def ai_enhance_tender(tender_id):
    """AI enhance and fill in tender data fields"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        tender = Tender.query.get_or_404(tender_id)
        
        analyzer = AIAnalyzer()
        enhanced = analyzer.enhance_tender_data(tender)
        
        # Update tender with enhanced data
        if enhanced.get('title'):
            tender.title = enhanced.get('title', tender.title)
        if enhanced.get('issuing_authority'):
            tender.issuing_authority = enhanced.get('issuing_authority')
        if enhanced.get('department'):
            tender.department = enhanced.get('department')
        if enhanced.get('category'):
            tender.category = enhanced.get('category')
        if enhanced.get('sub_category'):
            tender.sub_category = enhanced.get('sub_category')
        if enhanced.get('location'):
            tender.location = enhanced.get('location')
        if enhanced.get('verification_score'):
            tender.verification_score = enhanced.get('verification_score', 50)
        
        # Store AI analysis as JSON
        tender.ai_analysis = json.dumps(enhanced)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'enhanced_data': enhanced,
            'message': 'Tender data enhanced by AI'
        })
        
    except Exception as e:
        logger.error(f"AI enhance error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/analyze_tender/<int:tender_id>')
def ai_analyze_tender(tender_id):
    """Get comprehensive AI analysis of a tender"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        tender = Tender.query.get_or_404(tender_id)
        
        analyzer = AIAnalyzer()
        analysis = analyzer.analyze_tender_fully(tender)
        
        return jsonify({
            'status': 'success',
            'tender_id': tender_id,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/draft_email/<int:tender_id>', methods=['POST'])
def ai_draft_email(tender_id):
    """Draft email to supplier about a tender"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        data = request.json or {}
        supplier_name = data.get('supplier_name', 'Supplier')
        
        tender = Tender.query.get_or_404(tender_id)
        
        analyzer = AIAnalyzer()
        email = analyzer.draft_supplier_email(tender, supplier_name)
        
        return jsonify({
            'status': 'success',
            'email': email,
            'tender_id': tender_id
        })
        
    except Exception as e:
        logger.error(f"AI email draft error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/batch_analyze', methods=['POST'])
def ai_batch_analyze():
    """Batch analyze multiple tenders with AI"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        data = request.json or {}
        tender_ids = data.get('tender_ids', [])
        analyze_all = data.get('all', False)
        
        # Handle {all: true} - analyze all tenders
        if analyze_all:
            tenders = Tender.query.filter(
                Tender.title.isnot(None),
                Tender.title != ''
            ).limit(100).all()
        elif not tender_ids:
            return jsonify({'status': 'error', 'message': 'No tender IDs provided'}), 400
        else:
            tenders = Tender.query.filter(Tender.id.in_(tender_ids)).all()
        
        if not tenders:
            return jsonify({'status': 'error', 'message': 'No tenders found'}), 400
        
        analyzer = AIAnalyzer()
        results = analyzer.batch_analyze_tenders(tenders)
        
        return jsonify({
            'status': 'success',
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"AI batch analyze error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/similar_tenders/<int:tender_id>')
def ai_similar_tenders(tender_id):
    """Find similar tenders using AI"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        tender = Tender.query.get_or_404(tender_id)
        
        # Get all tenders for comparison (limit to 50 for performance)
        all_tenders = Tender.query.filter(
            Tender.id != tender_id,
            Tender.location.ilike(f'%{tender.location or ""}%')
        ).limit(50).all()
        
        analyzer = AIAnalyzer()
        similar = analyzer.find_similar_tenders(tender, all_tenders)
        
        return jsonify({
            'status': 'success',
            'tender_id': tender_id,
            'similar_tenders': similar
        })
        
    except Exception as e:
        logger.error(f"AI similar tenders error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/filter_sort_tenders', methods=['POST'])
def ai_filter_sort_tenders():
    """AI-powered intelligent filtering and sorting of tenders"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        data = request.json or {}
        preferences = data.get('preferences', {})
        
        # Get base query
        query = Tender.query.filter(
            Tender.title.isnot(None),
            Tender.title != ''
        )
        
        # Apply basic filters first
        state = data.get('state')
        if state:
            query = query.filter(Tender.location.ilike(f'%{state}%'))
        
        category = data.get('category')
        if category:
            query = query.filter(Tender.category == category)
        
        tenders = query.limit(100).all()
        
        # If AI preferences provided, use them to filter/sort
        if preferences:
            analyzer = AIAnalyzer()
            
            scored_tenders = []
            for tender in tenders:
                analysis = analyzer.analyze_tender_fully(tender)
                score = analysis.get('fit_score_for_medical_supplier', 50)
                scored_tenders.append({
                    'tender': tender,
                    'score': score,
                    'analysis': analysis
                })
            
            # Sort by AI score
            reverse = data.get('sort_order', 'desc') == 'desc'
            scored_tenders.sort(key=lambda x: x['score'], reverse=reverse)
            
            # Return top results
            limit = data.get('limit', 25)
            results = [{
                'tender': t['tender'].to_dict(),
                'ai_score': t['score'],
                'ai_analysis': t['analysis']
            } for t in scored_tenders[:limit]]
            
            return jsonify({
                'status': 'success',
                'tenders': results,
                'total': len(results),
                'ai_powered': True
            })
        else:
            # Return normal results
            pagination = query.paginate(page=1, per_page=25, error_out=False)
            return jsonify({
                'status': 'success',
                'tenders': [t.to_dict() for t in pagination.items],
                'total': pagination.total,
                'ai_powered': False
            })
        
    except Exception as e:
        logger.error(f"AI filter/sort error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/ai/health')
def ai_health_check():
    """Check if AI is working"""
    try:
        from app.utils.ai_analyzer import AIAnalyzer
        
        analyzer = AIAnalyzer()
        
        # Simple test
        test_result = analyzer._call_api([
            {"role": "system", "content": "Reply with OK"},
            {"role": "user", "content": "Test"}
        ], max_tokens=10)
        
        return jsonify({
            'status': 'healthy' if test_result else 'error',
            'model': analyzer.model,
            'api_working': test_result is not None
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500