import openai
import csv
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load OpenAI API key from environment variables
openai.api_key = os.getenv('OPENAI_API_KEY')

def transform_title(title):
    """Transform a product title using OpenAI API."""
    prompt = (
        f"Extract and format the following product title into three parts: Category, Brand, and Series. "
        f"Format the output as 'Category: [category], Brand: [brand], Series: [series]'.\n\nTitle: {title}"
    )

    response = openai.completions.create(
        model="gpt-3.5-turbo-instruct",  # Ensure you use a text model suitable for completions
        prompt=prompt,
        max_tokens=50,
        n=1,
        stop=None,
        temperature=0.5,
    )
    
    transformed_title = response.choices[0].text.strip()
    return transformed_title
