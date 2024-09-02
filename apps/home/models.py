from apps import db

# Association Tables
project_product = db.Table('project_product',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id')),
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'))
)

project_link = db.Table('project_link',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id')),
    db.Column('link_id', db.Integer, db.ForeignKey('links.id'))
)

project_user = db.Table('project_user',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'))
)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    
    def __repr__(self):
        return f'<Project {self.name}>'

    # Relationships
    products = db.relationship('Product', secondary=project_product, back_populates='projects')
    links = db.relationship('ProductLink', secondary=project_link, back_populates='projects')
    users = db.relationship('Users', secondary=project_user, back_populates='projects')

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    product_link = db.Column(db.String, nullable=False)
    image_url = db.Column(db.String, nullable=False)
    currency = db.Column(db.String, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    old_price = db.Column(db.Float, nullable=False)
    price_saving = db.Column(db.String, nullable=False)
    discount = db.Column(db.Float, nullable=True)
    category = db.Column(db.String, nullable=True)  # New column

    # Relationships
    projects = db.relationship('Project', secondary=project_product, back_populates='products')

class ProductLink(db.Model):
    __tablename__ = 'links'
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    product_link = db.Column(db.String(500), nullable=False)

    # Relationships
    projects = db.relationship('Project', secondary=project_link, back_populates='links')
