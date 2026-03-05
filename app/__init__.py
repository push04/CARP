"""
Main application package initialization
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from app.extensions import db
import os

# Initialize extensions
login_manager = LoginManager()
scheduler = APScheduler()


def create_app():
    """Application factory pattern"""
    # Set template folder to include BOTH app/templates AND root templates
    root_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(root_dir)
    template_dirs = os.path.join(project_root, 'templates')
    
    app = Flask(__name__, template_folder=template_dirs)
    # Also add app/templates as a Jinja loader
    import jinja2
    app.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(os.path.join(root_dir, 'templates')),
        jinja2.FileSystemLoader(template_dirs),
    ])
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    
    # Database - use absolute path
    db_path = os.path.join(project_root, 'instance', 'tenders.db')
    db_path = os.path.abspath(db_path)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    scheduler.init_app(app)
    
    # Ensure database tables exist
    with app.app_context():
        db.create_all()
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.main import main_bp
    app.register_blueprint(main_bp)
    
    return app