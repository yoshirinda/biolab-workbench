"""Single-password authentication for BioLab Workbench."""
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


auth_bp = Blueprint('auth', __name__)


PUBLIC_ENDPOINTS = {
    'auth.login',
    'auth.logout',
    'main.health',
    'static',
}


def auth_enabled():
    return bool(current_app.config.get('AUTH_ENABLED', True))


def is_authenticated():
    return not auth_enabled() or bool(session.get('authenticated'))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if is_authenticated():
            return view(*args, **kwargs)
        return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path))
    return wrapped


@auth_bp.before_app_request
def require_login():
    if not auth_enabled() or is_authenticated():
        return None

    endpoint = request.endpoint or ''
    if endpoint in PUBLIC_ENDPOINTS or endpoint.startswith('static'):
        return None

    if request.path.startswith('/static/'):
        return None

    return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if not auth_enabled():
        return redirect(url_for('main.index'))

    if session.get('authenticated'):
        return redirect(request.args.get('next') or url_for('main.index'))

    password_hash = current_app.config.get('PASSWORD_HASH')
    password_configured = bool(password_hash)

    if request.method == 'POST':
        password = request.form.get('password', '')
        if password_configured and check_password_hash(password_hash, password):
            session.clear()
            session['authenticated'] = True
            return redirect(request.form.get('next') or url_for('main.index'))
        flash('Invalid BioLab password.', 'danger')

    return render_template(
        'login.html',
        next_url=request.args.get('next', ''),
        password_configured=password_configured,
    )


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
