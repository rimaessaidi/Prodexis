import sqlite3
from apps.authentication.models import Users
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound
import logging
from apps import db
from sqlalchemy import text
from .models import ProductLink, Project, project_link
from scraper import schedule_single_scrape
from apps.authentication.forms import CreateAccountForm, EditCountryForm, ProductLinkForm, ProjectForm, CountryForm
from chatbot import get_chatbot_response

# Path to database
DB_PATH = 'apps/db.sqlite3'

# Define the upload folder and allowed file extensions
UPLOAD_FOLDER = '/media'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the Blueprint instance
blueprint = Blueprint('home_blueprint', __name__, url_prefix='/home')

@blueprint.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    print("chatting...")

    # Get chatbot response from chatbot.py
    response = get_chatbot_response(user_input)
    return jsonify({'response': response})

@blueprint.route('/')
@login_required
def homepage():
    segment = get_segment(request)
    
    # Get filters and project ID from request or session
    selected_sources = request.args.getlist('source')
    selected_category = request.args.get('category')
    project_id = request.args.get('project_id') or session.get('selectedProjectId')

    user_id = current_user.id

    try:
        # Fetch projects associated with the user
        projects_query = text("""
            SELECT p.id, p.name 
            FROM projects p
            JOIN project_user pu ON p.id = pu.project_id
            WHERE pu.user_id = :user_id
        """)
        projects_result = db.session.execute(projects_query, {'user_id': user_id})
        projects = projects_result.fetchall()

        # Handle no projects case
        if not projects:
            print("No projects found for the user in the database.")
        
        # Handle project ID from request or session
        if project_id:
            session['selectedProjectId'] = project_id

        # Build the source conditions for the SQL query
        source_conditions = []
        for idx, source in enumerate(selected_sources):
            source_conditions.append(f"p1.product_link LIKE :source_{idx}")

        # Join source conditions into a single SQL condition
        source_query_condition = " OR ".join(source_conditions) if source_conditions else "1=1"

        # Prepare the bind parameters for sources
        bind_params = {f'source_{idx}': f'%{source}%' for idx, source in enumerate(selected_sources)}
        bind_params['selected_category'] = selected_category
        bind_params['project_id'] = project_id
        
        # Define the SQL query with dynamic source filtering
        query = text(f"""
            WITH filtered_products AS (
                SELECT p1.id, p1.date, p1.image_url, p1.product_link, p1.title, p1.currency, p1.current_price, p1.old_price, p1.price_saving, p1.discount, p1.category,
                    CASE
                        WHEN p1.product_link LIKE '%noon%' THEN 'noon'
                        WHEN p1.product_link LIKE '%jarir%' THEN 'jarir'
                        WHEN p1.product_link LIKE '%extra%' THEN 'extra'
                        WHEN p1.product_link LIKE '%tunisianet%' THEN 'tunisianet'
                        WHEN p1.product_link LIKE '%mytek%' THEN 'mytek'
                        ELSE 'other'
                    END AS source_category
                FROM products p1
                JOIN project_product pp ON p1.id = pp.product_id
                WHERE ((:project_id IS NULL OR :project_id = '') OR pp.project_id = :project_id)
                AND ({source_query_condition})
                AND ((:selected_category IS NULL OR :selected_category = '') OR p1.category = :selected_category)
            ),
            latest_products AS (
                SELECT p1.id, p1.date, p1.image_url, p1.product_link, p1.title, p1.currency, p1.current_price, p1.old_price, p1.price_saving, p1.discount, p1.source_category, p1.category
                FROM filtered_products p1
                INNER JOIN (
                    SELECT title, currency, MAX(date) AS MaxDateTime
                    FROM filtered_products
                    GROUP BY title, currency
                ) p2
                ON p1.title = p2.title AND p1.currency = p2.currency AND p1.date = p2.MaxDateTime
            )
            SELECT * FROM latest_products
            ORDER BY date DESC
        """)

        result = db.session.execute(query, bind_params)
        products = [dict(row) for row in result.mappings().all()]
        
        # Fetch unique product sources
        sources_query = text("""
            SELECT DISTINCT 
                   CASE
                       WHEN product_link LIKE '%noon%' THEN 'noon'
                       WHEN product_link LIKE '%jarir%' THEN 'jarir'
                       WHEN product_link LIKE '%extra%' THEN 'extra'
                       WHEN product_link LIKE '%tunisianet%' THEN 'tunisianet'
                       WHEN product_link LIKE '%mytek%' THEN 'mytek'
                       ELSE 'other'
                   END AS source_category
            FROM products
        """)
        sources_result = db.session.execute(sources_query)
        source_list = [source[0] for source in sources_result]

        # Fetch unique categories
        categories_query = text("SELECT DISTINCT category FROM products")
        categories_result = db.session.execute(categories_query)
        category_list = [category[0] for category in categories_result]
        
        tunisianet_image_url = url_for('static', filename='assets/images/tunisianet.png')

    except Exception as e:
        print(f"An error occurred: {e}")
        products = []
        source_list = []
        category_list = []
        projects = []

    return render_template(
        'home/home_page.html', 
        segment=segment, 
        products=products, 
        sources=source_list, 
        categories=category_list,
        selected_sources=selected_sources, 
        selected_category=selected_category,
        selected_project_id=project_id, 
        projects=projects,
        tunisianet_image_url=tunisianet_image_url
    )


@blueprint.route('/index', methods=['GET'])
@login_required
def index():
    segment = get_segment(request)
    project_id = request.args.get('project_id') or session.get('selectedProjectId')
    if project_id:
        session['selectedProjectId'] = project_id
    else:
        project_id = None
    
    # Check if user is authenticated and has an id
    if not current_user.is_authenticated:
        print("User is not authenticated")
        return redirect(url_for('authentication_blueprint.login'))  # Redirect to login page or handle as needed

    user_id = current_user.id
    
    # Define the query with a filter for the selected project
    query = text("""
        SELECT Title, MIN(Current_Price) as Lowest_Price, MAX(Current_Price) as Highest_Price, Current_Price, Currency, Date, Image_URL, Product_Link,
               CASE
                   WHEN Product_Link LIKE '%noon%' THEN 'noon'
                   WHEN Product_Link LIKE '%jarir%' THEN 'jarir'
                   WHEN Product_Link LIKE '%extra%' THEN 'extra'
                   WHEN Product_Link LIKE '%tunisianet%' THEN 'tunisianet'
                   WHEN Product_Link LIKE '%mytek%' THEN 'mytek'
                   ELSE 'other'
               END AS category
        FROM products
        WHERE (:project_id IS NULL OR EXISTS (
            SELECT 1
            FROM project_product pp
            WHERE pp.product_id = products.id AND pp.project_id = :project_id
        ))
        GROUP BY Title, Currency, Date, Image_URL, Product_Link
        ORDER BY Date DESC
    """)

    try:
        # Execute the query with the project_id parameter
        result = db.session.execute(query, {'project_id': project_id})
        products_data = result.fetchall()

        # Prepare data for the chart
        kpi_data = {}
        for row in products_data:
            title = row[0]  # Access Title field by index
            title = title.replace("\n", ", ").replace("\r", ", ")
            category = row[8]  # Access Category field by index
            if title not in kpi_data:
                kpi_data[title] = {
                    'price_fluctuations': [],
                    'image_url': row[6],  # Access Image_URL field by index
                    'product_link': row[7],  # Access Product_Link field by index
                    'currency': row[4],  # Access Currency field by index
                    'category': category  # Access Category field by index
                }
            kpi_data[title]['price_fluctuations'].append({
                'date': row[5],
                'price': row[3]  # Access Current_Price field by index
            })

        # Calculate lowest price for each product
        for title, data in kpi_data.items():
            data['lowest_price'] = min(f['price'] for f in data['price_fluctuations'])
            data['current_price'] = data['price_fluctuations'][0]['price']

        # Convert the kpi_data dict to a list for rendering in the template
        kpi_data_list = [
            {
                'title': title,
                'lowest_price': data['lowest_price'],
                'current_price': data['current_price'],
                'currency': data['currency'],
                'price_fluctuations': data['price_fluctuations'],
                'image_url': data['image_url'],
                'product_link': data['product_link'],
                'category': data['category']  # Include category in the rendered data
            }
            for title, data in kpi_data.items()
        ]

    except Exception as e:
        # Log and handle any exceptions
        print(f"An error occurred while fetching data: {e}")
        kpi_data_list = []

    # Fetch projects for the dropdown menu associated with the user
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user up ON p.id = up.project_id
        WHERE up.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': user_id})
        projects = projects_result.fetchall()
        
        # Check if there are any projects and set a default project if none is selected
        if not projects:
            print("No projects found for the user in the database.")
            project_id = None  # No projects available
        else:
            # Set the default project if none is selected
            if not project_id:
                project_id = projects[0].id  # Default to the first project
                session['selectedProjectId'] = project_id
                
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    # Render the template with data
    return render_template('home/index.html', segment=segment, kpi_data=kpi_data_list, projects=projects, selected_project_id=project_id)


@blueprint.route('/hover_table', methods=['GET'])
@login_required
def hover_table():
    segment = get_segment(request)
    
    # Retrieve the selected project ID from the request or session
    project_id = request.args.get('project_id') or session.get('selectedProjectId')
    
    if not current_user.is_authenticated:
        return redirect(url_for('authentication_blueprint.login'))  # Redirect to login page if user is not authenticated
    
    user_id = current_user.id

    try:
        # Fetch projects associated with the current user
        projects_query = text("""
            SELECT p.id, p.name 
            FROM projects p
            JOIN project_user up ON p.id = up.project_id
            WHERE up.user_id = :user_id
        """)
        projects_result = db.session.execute(projects_query, {'user_id': user_id})
        projects = projects_result.fetchall()

        # Check if there are any projects and set a default project if none is selected
        if not projects:
            print("No projects found for the user in the database.")
            project_id = None  # No projects available
        else:
            # Set the default project if none is selected
            if not project_id:
                project_id = projects[0].id  # Default to the first project
                session['selectedProjectId'] = project_id

        # Get the tab ID and filter date from the request
        tab_id = request.args.get('tab_id', '#pills-home')  # Default to home tab if not specified
        filter_date = request.args.get('filter_date')

        # SQL query to filter products and links based on the selected project and filter date
        query = text("""
        WITH filtered_products AS (
            SELECT p1.id, p1.date, p1.image_url, p1.product_link, p1.title, p1.currency, p1.current_price, p1.old_price, p1.price_saving, p1.discount,
                CASE
                    WHEN p1.product_link LIKE '%noon%' THEN 'noon'
                    WHEN p1.product_link LIKE '%jarir%' THEN 'jarir'
                    WHEN p1.product_link LIKE '%extra%' THEN 'extra'
                    WHEN p1.product_link LIKE '%tunisianet%' THEN 'tunisianet'
                    WHEN p1.product_link LIKE '%mytek%' THEN 'mytek'
                    ELSE 'other'
                END AS category
            FROM products p1
            JOIN project_product pp ON p1.id = pp.product_id
            WHERE (:project_id IS NULL OR pp.project_id = :project_id)
            AND (:filter_date IS NULL OR DATE(p1.date) = :filter_date)
        ),
        latest_products AS (
            SELECT p1.id, p1.date, p1.image_url, p1.product_link, p1.title, p1.currency, p1.current_price, p1.old_price, p1.price_saving, p1.discount, p1.category
            FROM filtered_products p1
            INNER JOIN (
                SELECT title, currency, MAX(date) as MaxDateTime
                FROM filtered_products
                GROUP BY title, currency
            ) p2
            ON p1.title = p2.title AND p1.currency = p2.currency AND p1.date = p2.MaxDateTime
        )
        SELECT * FROM latest_products
        ORDER BY date DESC
        """)

        result = db.session.execute(query, {'project_id': project_id, 'filter_date': filter_date})
        products = result.fetchall()

        # Query to fetch links related to the project
        links_query = text("""
            SELECT l.id, l.image_url, l.product_link,
                CASE
                    WHEN l.product_link LIKE '%noon%' THEN 'noon'
                    WHEN l.product_link LIKE '%jarir%' THEN 'jarir'
                    WHEN l.product_link LIKE '%extra%' THEN 'extra'
                    WHEN l.product_link LIKE '%tunisianet%' THEN 'tunisianet'
                    WHEN l.product_link LIKE '%mytek%' THEN 'mytek'
                    ELSE 'other'
                END AS category
            FROM links l
            JOIN project_link pl ON l.id = pl.link_id
            WHERE (:project_id IS NULL OR pl.project_id = :project_id)
        """)
        links_result = db.session.execute(links_query, {'project_id': project_id})
        links = links_result.fetchall()

        # Filter products based on links
        link_product_links = {link.product_link for link in links}
        filtered_products = [product for product in products if product.product_link in link_product_links]

        # Determine if no products are found
        no_products_found = len(filtered_products) == 0

    except Exception as e:
        print(f"An error occurred: {e}")
        filtered_products = []
        links = []
        projects = []
        no_products_found = True

    # Render the template with products, links, and projects
    return render_template(
        'home/tbl_bootstrap.html', 
        segment=segment, 
        tab_id=tab_id, 
        products=filtered_products, 
        links=links, 
        no_products_found=no_products_found, 
        projects=projects, 
        selected_project=Project.query.get(project_id) if project_id else None
    )


@blueprint.route('/update_product/<int:id>', methods=['GET', 'POST'])
@login_required
def update_product(id):
    project_id = request.args.get('project_id') or session.get('selectedProjectId')
    if project_id:
        session['selectedProjectId'] = project_id
    link_entry = ProductLink.query.get(id)

    if not link_entry:
        flash('The link entry does not exist.', 'warning')
        logger.warning(f'Tried to update non-existent link entry with id {id}.')
        return redirect(url_for('home_blueprint.hover_table', id=id))

    form = ProductLinkForm(obj=link_entry)

    if form.validate_on_submit():
        new_link = form.product_link.data

        try:
            link_entry.product_link = new_link
            db.session.commit()
            flash('Link updated successfully!', 'success')
            logger.info(f'Link for id {id} updated successfully to {new_link}.')
            return redirect(url_for('home_blueprint.hover_table'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating link: {e}', 'danger')
            logger.error(f'Error updating link for id {id} to {new_link}: {e}')

    # Fetch projects for the dropdown menu
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user up ON p.id = up.project_id
        WHERE up.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': current_user.id})
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/update_product.html', form=form, id=id, selected_project=Project.query.get(project_id) if project_id else None, projects=projects)


@blueprint.route('/add_product/<int:project_id>', methods=['GET', 'POST'])
@login_required
def add_product(project_id):
    if request.method == 'POST':
        product_link = request.form['product_link']
        image_url = request.form.get('image_url', '')

        try:
            # Add the product link to the database
            new_link = ProductLink(image_url=image_url, product_link=product_link)
            db.session.add(new_link)
            db.session.commit()

            # Create association with the project in the project_link table
            if project_id:
                new_project_link = text("""
                    INSERT INTO project_link (project_id, link_id)
                    VALUES (:project_id, :link_id)
                """)
                db.session.execute(new_project_link, {'project_id': project_id, 'link_id': new_link.id})
                db.session.commit()

            flash('Product link added successfully!', 'success')
            return redirect(url_for('home_blueprint.hover_table', project_id=project_id))
        except Exception as e:
            print(f'Error adding product link: {e}')
            flash(f'Error adding product link: {e}', 'danger')
            db.session.rollback()

    # Fetch projects for the dropdown menu
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user up ON p.id = up.project_id
        WHERE up.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': current_user.id})
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/add_product.html', project_id=project_id, selected_project=Project.query.get(project_id) if project_id else None, projects=projects)


@blueprint.route('/delete_product/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    # Your delete product logic here
    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/scrape_product', methods=['POST'])
def scrape_product():
    logging.debug('Scrape product route called.')

    product_link = request.form.get('product_link')
    logging.debug(f'Received product_link: {product_link}')

    if not product_link:
        logging.warning('No product_link provided in the request.')
        return redirect(url_for('home_blueprint.hover_table'))

    # Connect to SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Fetch the product link details using the product link
        cursor.execute('SELECT id FROM links WHERE product_link = ?', (product_link,))
        link_id = cursor.fetchone()

        if link_id:
            link_id = link_id[0]
            # Schedule scraping based on product link
            schedule_single_scrape(product_link)
            logging.info(f'Scraping initiated for product link: {product_link}')
        else:
            logging.warning(f'No product found with link: {product_link}')

    except Exception as e:
        logging.error(f"An error occurred while fetching product link: {e}")
    finally:
        conn.close()
    
    return redirect(url_for('home_blueprint.hover_table'))


@blueprint.route('/super_admin_index')
@login_required
def super_admin_index():
    segment = get_segment(request)
    project_id = request.args.get('project_id') or session.get('selectedProjectId')
    if project_id:
        session['selectedProjectId'] = project_id
    else:
        project_id = None

    # Fetch users
    users = Users.query.all()

    # Fetch projects associated with the current user
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user pu ON p.id = pu.project_id
        WHERE pu.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': current_user.id})
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    # Fetch all projects excluding those associated with the current user
    all_projects_query = text("""
        SELECT DISTINCT p.id, p.name
        FROM projects p
        LEFT JOIN project_user pu ON p.id = pu.project_id
    """)
    try:
        all_projects_result = db.session.execute(all_projects_query, {'user_id': current_user.id})
        all_projects = all_projects_result.fetchall()
        print("Fetched projects excluding current user:", all_projects)
    except Exception as e:
        print(f"An error occurred while fetching all projects: {e}")
        all_projects = []

    # Fetch project-user associations
    project_user_query = text("""
        SELECT p.name AS project_name, u.username AS user_name, u.id as user_id
        FROM users u
        LEFT JOIN project_user pu ON pu.user_id = u.id
        LEFT JOIN projects p ON pu.project_id = p.id
        GROUP BY u.username, u.id, p.name
    """)
    try:
        project_user_result = db.session.execute(project_user_query)
        project_user_associations = project_user_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching project-user associations: {e}")
        project_user_associations = []

    # Fetch country-user associations
    country_user_query = text("""
        SELECT u.country AS country, u.username AS user_name
        FROM users u
        GROUP BY u.country, u.username
    """)
    try:
        country_user_result = db.session.execute(country_user_query)
        country_user_associations = country_user_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching country-user associations: {e}")
        country_user_associations = []
        
    session['user_id'] = current_user.id
    session['username'] = current_user.username
    session['country'] = current_user.country

    return render_template('home/super_admin_index.html', 
                           segment=segment,
                           users=users, 
                           selected_project=Project.query.get(project_id) if project_id else None, 
                           projects=projects,
                           project_user_associations=project_user_associations,
                           all_projects=all_projects,
                           country_user_associations=country_user_associations)


@blueprint.route('/add_user', methods=['GET', 'POST'])
def add_user():
    form = CreateAccountForm()
    if form.validate_on_submit():
        # Create and add the new user
        new_user = Users(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            role=form.role.data,
            country=form.country.data
        )
        db.session.add(new_user)
        db.session.commit()

        # Assign the projects to the new user if projects are selected
        project_ids = request.form.getlist('project_ids')
        if project_ids:
            for project_id in project_ids:
                new_project_user_query = text("""
                    INSERT INTO project_user (project_id, user_id)
                    VALUES (:project_id, :user_id)
                """)
                db.session.execute(new_project_user_query, {'project_id': project_id, 'user_id': new_user.id})
            db.session.commit()

        flash('User added successfully!', 'success')
        return redirect(url_for('home_blueprint.super_admin_index'))

    # Fetch projects for the checkboxes
    projects_query = text("""
        SELECT id, name 
        FROM projects
    """)
    try:
        projects_result = db.session.execute(projects_query)
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/add_user.html', form=form, projects=projects)


@blueprint.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    # Fetch the user by ID
    user = Users.query.get_or_404(user_id)
    form = CreateAccountForm(obj=user)

    if form.validate_on_submit():
        # Update user details
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.country = form.country.data

        db.session.commit()

        # Update the user's project associations if any were selected
        project_ids = request.form.getlist('project_ids')
        if project_ids:
            # Clear existing associations
            user.projects = []
            for project_id in project_ids:
                project = Project.query.get(project_id)
                if project:
                    user.projects.append(project)

            db.session.commit()

        flash('User updated successfully!', 'success')
        return redirect(url_for('home_blueprint.super_admin_index'))

    # Fetch projects for the checkboxes
    projects = Project.query.all()  # Get all projects
    user_project_ids = [project.id for project in user.projects]  # Get the IDs of the projects associated with the user

    return render_template('home/edit_user.html', form=form, user=user, projects=projects, user_project_ids=user_project_ids)


@blueprint.route('/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    # Fetch the user by id
    user = Users.query.get_or_404(id)
    
    try:
        # Delete the user and related records (cascading delete)
        db.session.delete(user)
        db.session.commit()
        flash('User and related records deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the user: {e}', 'danger')

    return redirect(url_for('home_blueprint.super_admin_index'))


@blueprint.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    project_id = request.args.get('project_id') or session.get('selectedProjectId')
    if project_id:
        session['selectedProjectId'] = project_id
    form = ProjectForm()

    if form.validate_on_submit():
        project_name = form.name.data

        try:
            # Add the new project to the database
            new_project = Project(name=project_name)
            db.session.add(new_project)
            db.session.commit()

            flash('Project added successfully!', 'success')
            return redirect(url_for('home_blueprint.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding project: {e}', 'danger')

    # Fetch projects for the dropdown menu (if needed)
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user up ON p.id = up.project_id
        WHERE up.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': current_user.id})
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/add_project.html', form=form, selected_project=Project.query.get(project_id) if project_id else None, projects=projects)


@blueprint.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        new_name = request.form.get('name')
        if new_name:
            project.name = new_name
            try:
                db.session.commit()
                flash('Project name updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating project name: {e}', 'danger')
        else:
            flash('Project name cannot be empty.', 'danger')
        return redirect(url_for('home_blueprint.super_admin_index'))

    return render_template('home/edit_project.html', project=project)


@blueprint.route('/edit_user_projects/<int:user_id>', methods=['GET', 'POST'])
def edit_user_projects(user_id):
    user = Users.query.get_or_404(user_id)
    if request.method == 'POST':
        # Update project assignments
        selected_projects = request.form.getlist('project_ids')
        
        # Remove existing project assignments
        db.session.execute(text("DELETE FROM project_user WHERE user_id = :user_id"), {'user_id': user_id})
        
        # Add new project assignments
        for project_id in selected_projects:
            db.session.execute(text("INSERT INTO project_user (project_id, user_id) VALUES (:project_id, :user_id)"), {'project_id': project_id, 'user_id': user_id})
        db.session.commit()
        flash('Project assignments updated successfully!', 'success')
        
        return redirect(url_for('home_blueprint.super_admin_index'))

    # Fetch all projects
    projects = db.session.execute(text("SELECT id, name FROM projects")).fetchall()
    # Fetch user's current projects
    user_projects = db.session.execute(text("SELECT project_id FROM project_user WHERE user_id = :user_id"), {'user_id': user_id}).fetchall()
    user_project_ids = [project.project_id for project in user_projects]
    
    return render_template('home/edit_user_projects.html', user=user, projects=projects, user_project_ids=user_project_ids)


@blueprint.route('/delete_user_projects/<int:user_id>', methods=['POST'])
def delete_user_projects(user_id):
    # Remove all project assignments for the user
    db.session.execute(text("DELETE FROM project_user WHERE user_id = :user_id"), {'user_id': user_id})
    db.session.commit()
    flash('All project assignments removed for the user!', 'success')
    
    return redirect(url_for('home_blueprint.super_admin_index'))


@blueprint.route('/add_country', methods=['GET', 'POST'])
@login_required
def add_country():
    form = CountryForm()

    if form.validate_on_submit():
        country_name = form.name.data

        try:
            # Update users to include the new country if necessary
            users = Users.query.all()
            for user in users:
                if user.country == 'International':
                    user.country = country_name
            db.session.commit()

            flash('Country added successfully!', 'success')
            return redirect(url_for('home_blueprint.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding country: {e}', 'danger')
            
    # Fetch projects for the dropdown menu
    projects_query = text("""
        SELECT p.id, p.name 
        FROM projects p
        JOIN project_user up ON p.id = up.project_id
        WHERE up.user_id = :user_id
    """)
    try:
        projects_result = db.session.execute(projects_query, {'user_id': current_user.id})
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/add_country.html', form=form, projects=projects)


@blueprint.route('/edit_country/<string:country_name>', methods=['GET', 'POST'])
@login_required
def edit_country(country_name):
    form = EditCountryForm()

    # Fetch the country name for the given country_name
    if form.validate_on_submit():
        new_country_name = form.country.data
        if new_country_name:
            # Update the country name in the user records
            db.session.query(Users).filter_by(country=country_name).update({'country': new_country_name})
            db.session.commit()
            flash('Country updated successfully', 'success')
            return redirect(url_for('home_blueprint.super_admin_index'))

    form.country.data = country_name

    # Fetch users assigned to the country
    assigned_users = db.session.query(Users).filter_by(country=country_name).all()

    # Fetch available users to add
    available_users = db.session.query(Users).filter(Users.country != country_name).all()
    
    # Fetch projects for the checkboxes
    projects_query = text("""
        SELECT id, name 
        FROM projects
    """)
    try:
        projects_result = db.session.execute(projects_query)
        projects = projects_result.fetchall()
    except Exception as e:
        print(f"An error occurred while fetching projects: {e}")
        projects = []

    return render_template('home/edit_country.html', form=form, country=country_name, assigned_users=assigned_users, available_users=available_users, projects=projects)


@blueprint.route('/manage_users/<string:country_name>', methods=['POST'])
@login_required
def manage_users(country_name):
    user_ids = request.form.getlist('users')
    for user_id in user_ids:
        user = db.session.query(Users).filter_by(id=user_id).first()
        if user:
            user.country = country_name
    db.session.commit()
    flash('Users added successfully', 'success')

    return redirect(url_for('home_blueprint.edit_country', country_name=country_name))


@blueprint.route('/remove_user/<string:country_name>/<int:user_id>', methods=['POST'])
@login_required
def remove_user(country_name, user_id):
    user = db.session.query(Users).filter_by(id=user_id).first()
    if user:
        user.country = 'International'  # or another default value
        db.session.commit()
        flash('User removed successfully', 'success')
    else:
        flash('User not found', 'danger')

    return redirect(url_for('home_blueprint.edit_country', country_name=country_name))


@blueprint.route('/delete_country/<string:country_name>', methods=['POST'])
@login_required
def delete_country(country_name):
    try:
        # Optional: Check if the country exists
        country = db.session.query(Users).filter_by(country=country_name).first()
        if not country:
            flash('Country not found', 'danger')
            return redirect(url_for('home_blueprint.super_admin_index'))

        # Delete the country
        db.session.query(Users).filter_by(country=country_name).delete()
        db.session.commit()
        flash('Country deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('home_blueprint.super_admin_index'))


@blueprint.route('/<template>')
@login_required
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'homepage'
        return segment
    except:
        return None
