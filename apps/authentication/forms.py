# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, DateField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, DataRequired
from wtforms.widgets import html_params
from markupsafe import Markup

# login and registration


class LoginForm(FlaskForm):
    username = StringField('Username',
                         id='username_login',
                         validators=[DataRequired()])
    password = PasswordField('Password',
                             id='pwd_login',
                             validators=[DataRequired()])
    
class IconSelectWidget(object):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        html = ['<select %s>' % html_params(name=field.name, **kwargs)]
        icons = {
            'Tunisia': 'tunisia.svg',
            'Saudi Arabia': 'saudi_arabia.svg',
            'International': 'international.svg'
        }
        for val, label in field.choices:
            icon = icons.get(label, '')
            if icon:
                icon_html = f'<img src="/static/icons/{icon}" alt="{label}" width="16" height="16"/> '
            else:
                icon_html = ''
            html.append(f'<option value="{val}">{icon_html}{label}</option>')
        html.append('</select>')
        return Markup(''.join(html))


class CreateAccountForm(FlaskForm):
    username = StringField('Username',
                         id='username_create',
                         validators=[DataRequired()])
    email = StringField('Email',
                      id='email_create',
                      validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             id='pwd_create',
                             validators=[DataRequired()])
    role = StringField('Role', default='user')
    country = SelectField('Country', choices=[('Tunisia', 'Tunisia'), ('Saudi Arabia', 'Saudi Arabia'), ('International', 'International')], default='International', validators=[DataRequired()], widget=IconSelectWidget())


class ProductLinkForm(FlaskForm):
    image_url = StringField('Product Image URL', validators=[DataRequired()])
    product_link = StringField('Product Link', validators=[DataRequired()])
    

class ProjectForm(FlaskForm):
    name = StringField('Project Name', validators=[DataRequired()])
    
class EditCountryForm(FlaskForm):
    country = StringField('Country', validators=[DataRequired()])
    submit = SubmitField('Update Country')
    
class CountryForm(FlaskForm):
    name = StringField('Country Name', validators=[DataRequired()])
    submit = SubmitField('Add Country')