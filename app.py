from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, UserMixin
from sqlalchemy.orm import DeclarativeBase
from functools import wraps
from werkzeug.security import check_password_hash
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config
import logging
import os
from datetime import timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

# Define User model for Flask-Login
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

    @staticmethod
    def get(user_id):
        if user_id == Config.ADMIN_USERNAME:
            return User(user_id)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configure the Flask application
    app.config.from_object(Config)

    # Set secret key from environment variable with a secure fallback
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))

    # Set session timeout
    app.permanent_session_lifetime = timedelta(hours=1)

    # Initialize SQLAlchemy with the app
    db.init_app(app)

    # Initialize Flask-Migrate
    migrate.init_app(app, db)

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'admin_login'

    # Configure SQLAlchemy connection pool
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    return app

app = create_app()

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handle admin login"""
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            if not username or not password:
                flash('Please provide both username and password', 'danger')
                return render_template('admin/login.html')

            if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
                session.permanent = True
                session['admin_logged_in'] = True
                logger.info(f"Admin login successful for user: {username}")
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))

            flash('Invalid credentials', 'danger')
            logger.warning(f"Failed login attempt for username: {username}")
            return render_template('admin/login.html')

        return render_template('admin/login.html')
    except Exception as e:
        logger.error(f"Error in admin_login: {str(e)}", exc_info=True)
        flash('An error occurred during login. Please try again.', 'danger')
        return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    """Handle admin logout"""
    try:
        session.pop('admin_logged_in', None)
        session.clear()
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('admin_login'))
    except Exception as e:
        logger.error(f"Error in admin_logout: {str(e)}", exc_info=True)
        flash('An error occurred during logout.', 'danger')
        return redirect(url_for('admin_login'))

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    """Admin dashboard route"""
    from models import BotPersonality, User, Message

    try:
        if request.method == 'POST':
            new_persona = request.form.get('persona')
            if not new_persona:
                flash('Persona text cannot be empty', 'danger')
                return redirect(url_for('admin_dashboard'))

            try:
                personality = BotPersonality(persona=new_persona)
                db.session.add(personality)
                db.session.commit()
                flash('Bot personality updated successfully!', 'success')
                logger.info("Bot personality updated")
            except Exception as db_error:
                db.session.rollback()
                logger.error(f"Database error updating personality: {str(db_error)}", exc_info=True)
                flash('Error updating bot personality. Please try again.', 'danger')

        personality = BotPersonality.query.order_by(BotPersonality.created_at.desc()).first()
        users_count = User.query.count()
        messages_count = Message.query.count()

        return render_template(
            'admin/dashboard.html',
            personality=personality,
            users_count=users_count,
            messages_count=messages_count
        )
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {str(e)}", exc_info=True)
        flash('An error occurred while loading the dashboard.', 'danger')
        return redirect(url_for('admin_login'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    logger.error(f"404 error: {error}")
    return render_template('admin/error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"500 error: {error}")
    db.session.rollback()
    return render_template('admin/error.html', error="Internal server error"), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            import models
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}", exc_info=True)

        # Start the Flask server
        app.run(host='0.0.0.0', port=3000, debug=True)