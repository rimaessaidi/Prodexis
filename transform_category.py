import openai
import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from fuzzywuzzy import fuzz, process
from collections import defaultdict

# Load environment variables from .env file
load_dotenv()

# Load OpenAI API key from environment variables
openai.api_key = os.getenv('OPENAI_API_KEY')

# SQLAlchemy setup
DATABASE_URI = 'sqlite:///apps/db.sqlite3'
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Predefined categories
STANDARD_CATEGORIES = [
    "Smartphone", "Earbuds", "Laptop", "Tablet", "Headphones", "Camera",
    "Smart TV", "Fitness Tracker", "Gaming Console", "Portable Speaker",
    "Powerbank", "SSD", "USB Drive", "Smart Band", "Gaming Headphones", "Adapter"
]

# Function to extract category from title using OpenAI's API
def extract_category(title):
    response = openai.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=f"Extract the category from the following product title: {title}. The category should be a single word or two words at maximum. Example categories include 'Smartphone', 'Laptop', 'Camera', etc.",
        max_tokens=10
    )
    category = response.choices[0].text.strip()
    return category

# Function to standardize categories with fuzzy matching
def standardize_category(category):
    best_match, score = process.extractOne(category.lower(), STANDARD_CATEGORIES, scorer=fuzz.ratio)
    
    if score >= 70:  # Set a threshold for matching
        return best_match
    else:
        print(f"Unmapped category found: {category}")
        return category