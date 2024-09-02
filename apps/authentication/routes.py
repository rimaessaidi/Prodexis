# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import session, render_template, redirect, request, url_for, make_response
import logging
from flask_login import (
    current_user,
    login_user,
    logout_user
)
from flask_dance.contrib.github import github

from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users

from apps.authentication.util import verify_pass

@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Login & Registration

@blueprint.route("/github")
def login_github():
    """ Github login """
    if not github.authorized:
        return redirect(url_for("github.login"))

    res = github.get("/user")
    return redirect(url_for('home_blueprint.homepage'))

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:
        # Read form data
        user_id  = request.form['username']  # username or email
        password = request.form['password']

        # Locate user
        user = Users.find_by_username(user_id) or Users.find_by_email(user_id)

        # If user not found
        if not user:
            return render_template('accounts/login.html',
                                   msg='Unknown User or Email',
                                   form=login_form)

        # Check the password
        if verify_pass(password, user.password):
            login_user(user)
            
            # Store user country in the session
            session['user_country'] = user.country
            
            # Store user role in the session
            session['user_role'] = user.role
            
            logging.info(f"User {user_id} with role {session['user_role']} logged in successfully.")
            return redirect(url_for('authentication_blueprint.route_default'))

        # Wrong user or password
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.homepage'))


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']
        role = request.form.get('role', 'user')
        country = request.form['country']  # Get the country value

        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        user = Users(username=username, email=email, role=role, country=country, password=request.form['password'])
        db.session.add(user)
        db.session.commit()

        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)



@blueprint.route('/logout')
def logout():    
    # Debug output before clearing the session
    print("Session before clearing:", dict(session))
    print("Current user before session clear:", current_user.is_authenticated)
    
    # Perform logout
    logout_user()
    
    # Clear the session
    session.clear()
    
    # Debug output after clearing the session
    print("Session after clearing:", dict(session))
    print("Current user after session clear:", current_user.is_authenticated)

    # Clear local storage via JavaScript
    response = make_response(redirect(url_for('authentication_blueprint.login')))
    response.set_cookie('session', '', expires=0)
    return response


# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
