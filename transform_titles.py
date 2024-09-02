import sqlite3
import csv
import openai
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Load OpenAI API key from environment variables
openai.api_key = os.getenv('OPENAI_API_KEY')

def extract_unique_links(database_path, output_csv):
    """ Extract unique product links from the products table """
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    query = "SELECT DISTINCT product_link FROM products"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    # Write the unique links to a CSV file
    with open(output_csv, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['product_link'])  # Write the header
        writer.writerows(rows)

    print(f"Unique product links extracted to {output_csv}.")

def map_titles_to_links(database_path, links_csv, products_csv):
    """ Map unique links to products and extract titles """
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    with open(links_csv, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        headers = next(reader)  # Skip the header row

        links = [row[0] for row in reader]

    query = """
        SELECT p.id, p.title, p.product_link
        FROM products p
        WHERE p.product_link IN ({seq})
    """.format(seq=','.join(['?']*len(links)))

    cursor.execute(query, links)
    rows = cursor.fetchall()
    conn.close()

    # Write the data to a CSV file
    with open(products_csv, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['id', 'title', 'product_link'])  # Write the headers
        writer.writerows(rows)

    print(f"Products mapped by unique links and saved to {products_csv}.")

def transform_titles_using_openai(input_csv, output_csv):
    """ Transform product titles using OpenAI API """
    link_to_transformed_title = {}

    with open(input_csv, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        headers = next(reader)  # Skip the header row

        for row in reader:
            if len(row) < 3:
                print(f"Skipping invalid row: {row}")
                continue

            product_id, title, product_link = row[0], row[1], row[2]

            # Clean up title for better API response
            title = title.replace('\n', ' ').strip()

            if product_link not in link_to_transformed_title:
                prompt = (
                    f"Extract and format the following product title into three parts: Category, Brand, and Series. "
                    f"Format the output as 'Category: [category], Brand: [brand], Series: [series]'.\n\nTitle: {title}"
                )

                response = openai.Completion.create(
                    model="gpt-3.5-turbo-instruct",  # Ensure you use a text model suitable for completions
                    prompt=prompt,
                    max_tokens=50,
                    n=1,
                    stop=None,
                    temperature=0.5,
                )
                transformed_title = response.choices[0].text.strip()
                link_to_transformed_title[product_link] = transformed_title

    # Write the transformed titles to a CSV file
    with open(output_csv, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['product_link', 'transformed_title'])  # Write headers
        for link, title in link_to_transformed_title.items():
            writer.writerow([link, title])

    print(f"Transformed titles saved to {output_csv}.")

def update_titles_in_database(database_path, transformed_csv):
    """ Update the product titles in the database with transformed titles """
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Create a dictionary of product links to transformed titles
    link_to_transformed_title = {}
    with open(transformed_csv, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        headers = next(reader)  # Skip the header row
        for row in reader:
            product_link, transformed_title = row
            link_to_transformed_title[product_link] = transformed_title

    # Update all products with the same product_link
    for product_link, transformed_title in link_to_transformed_title.items():
        cursor.execute("""
            UPDATE products
            SET title = ?
            WHERE product_link = ?
        """, (transformed_title, product_link))

    conn.commit()
    conn.close()

    print(f"Database updated with transformed titles.")

def main():
    database_path = 'apps/db.sqlite3'  # Replace with the path to your SQLite database
    links_csv = 'unique_product_links.csv'
    products_csv = 'products_by_links.csv'
    transformed_csv = 'transformed_product_titles.csv'
    
    # Step 1: Extract unique links to CSV
    extract_unique_links(database_path, links_csv)

    # Step 2: Map links to products and extract titles
    map_titles_to_links(database_path, links_csv, products_csv)

    # Step 3: Transform Titles Using OpenAI API
    transform_titles_using_openai(products_csv, transformed_csv)

    # Step 4: Update the Transformed Titles in the Database
    update_titles_in_database(database_path, transformed_csv)

if __name__ == "__main__":
    main()
