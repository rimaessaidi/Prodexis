import sqlite3
from sqlalchemy import text
from datetime import datetime, timedelta
import time
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import atexit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from transform_title import transform_title
from transform_category import extract_category, standardize_category

DB_PATH = 'apps/db.sqlite3'

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-cache')
    options.binary_location = "C:/Users/rymae/AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe"
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.126 Safari/537.36 Brave/1.67.123")
    return webdriver.Chrome(options=options)

def scrape_product_details(driver, product_url):
    def is_valid_url(url):
        return url.startswith("http://") or url.startswith("https://")

    def scrape_jarir(driver):
        try:
            # Locate the gallery__slide-item div
            slide_item = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.gallery__slide-item'))
            )
            
            # Locate the lazyload-wrapper div within the gallery__slide-item div
            lazyload_wrapper = slide_item.find_element(By.CSS_SELECTOR, 'div.lazyload-wrapper.pointer.image.image--gallery')
            
            # Locate the second img element within the lazyload-wrapper div
            image_element = lazyload_wrapper.find_elements(By.CSS_SELECTOR, 'img.image.image--contain')[1]  # Index 1 for the second image
            
            # Extract the src attribute
            image_url = image_element.get_attribute('src')
            print(f"Extracted Image URL: {image_url}")
        except Exception as e:
            image_url = "N/A"
            print(f"Error extracting image URL: {e}")

        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h2.product-title__title'))
            )
            title = title_element.text.strip()
        except Exception as e:
            title = "N/A"
            print(f"Error extracting title from Noon: {e}")

        try:
            currency = "SAR"
            price_now_element = driver.find_element(By.CSS_SELECTOR, 'div.product-view__price div.price-box__row div.price-box__column div.price.price--pdp span.price_alignment')
            current_price_text = price_now_element.find_element(By.CSS_SELECTOR, 'span:nth-child(2)').text.strip().replace(',', '')
            current_price = float(current_price_text) if current_price_text else 0.0

            price_was_element = driver.find_element(By.CSS_SELECTOR, 'div.product-view__price div.price-box__row div.price-box__column.price-box__column--align-start div.price.price--old-red span.price_alignment')
            old_price_text = price_was_element.find_element(By.CSS_SELECTOR, 'span:nth-child(2)').text.strip().replace(',', '')
            old_price = float(old_price_text) if old_price_text else 0.0

            price_saving_element = driver.find_element(By.CSS_SELECTOR, 'div.notification__save span.notification__price span.price-box div.price span.price_alignment')
            price_saving_text = price_saving_element.find_element(By.CSS_SELECTOR, 'span:nth-child(2)').text.strip().replace('SR', '').strip().replace(',', '')
            price_saving = float(price_saving_text) if price_saving_text else 0.0

            discount_element = driver.find_element(By.CSS_SELECTOR, 'div.product-view__price div.price-box__row div.price-box__column.price-box__column--align-start div.badge.badge--discount')
            discount_text = discount_element.text.strip().replace('%', '').replace('-', '').strip()
            discount = float(discount_text) if discount_text else 0.0

            if discount == 0.0 and old_price != 0.0:
                discount = ((old_price - current_price) / old_price) * 100
        except Exception as e:
            current_price, old_price, price_saving, discount = 0.0, 0.0, 0.0, 0.0
            print(f"Error extracting price details from Noon: {e}")

        return [current_datetime, image_url, product_url, title, currency, current_price, old_price, price_saving, discount], image_url

    def scrape_noon(driver):
        try:
            image_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.sc-d8caf424-2.fJBKzl img'))
            )
            image_url = image_element.get_attribute('src')
        except Exception as e:
            image_url = "N/A"
            print(f"Error extracting image URL from Jarir: {e}")

        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h1[starts-with(@data-qa, 'pdp-name-')]"))
            )
            title = title_element.text.strip()
        except Exception as e:
            title = "N/A"
            print(f"Error extracting title from Jarir: {e}")

        try:
            currency = "SAR"
            price_now_element = driver.find_element(By.CSS_SELECTOR, 'div.priceNow')
            current_price_text = price_now_element.text.strip().replace('SAR', '').replace('Inclusive of VAT', '').strip().replace(',', '')
            current_price = float(current_price_text) if current_price_text else 0.0

            price_was_element = driver.find_element(By.CSS_SELECTOR, 'div.priceWas')
            old_price_text = price_was_element.text.strip().replace('SAR', '').strip().replace(',', '')
            old_price = float(old_price_text) if old_price_text else 0.0

            price_saving_element = driver.find_element(By.CSS_SELECTOR, 'div.priceSaving')
            price_saving_text = price_saving_element.text.strip().split('\n')[0].replace('SAR', '').strip().replace(',', '')
            price_saving = float(price_saving_text) if price_saving_text else 0.0

            discount_element = driver.find_element(By.CSS_SELECTOR, 'span.profit')
            discount_text = discount_element.text.strip().replace('% Off', '').strip()
            discount = float(discount_text) if discount_text else 0.0

            if discount == 0.0 and old_price != 0.0:
                discount = ((old_price - current_price) / old_price) * 100
        except Exception as e:
            current_price, old_price, price_saving, discount = 0.0, 0.0, 0.0, 0.0
            print(f"Error extracting price details from Jarir: {e}")

        return [current_datetime, image_url, product_url, title, currency, current_price, old_price, price_saving, discount], image_url
    
    def scrape_extra(driver):
        try:
            # Extract the image URL
            image_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'picture img.product-image'))
            )
            image_url = image_element.get_attribute('src')
            print(f"Extracted Image URL: {image_url}")
        except Exception as e:
            image_url = "N/A"
            print(f"Error extracting image URL: {e}")

        try:
            # Extract the product title
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.product-name'))
            )
            title = title_element.text.strip()
            print(f"Extracted Title: {title}")
        except Exception as e:
            title = "N/A"
            print(f"Error extracting title: {e}")

        try:
            # Extract the currency and current price
            price_now_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'section.product-price-new-container section.price strong'))
            )
            currency = "SAR"
            current_price_text = price_now_element.text.strip().replace(',', '').replace('SAR', '').replace('Incl. VAT', '').strip()
            current_price = float(current_price_text) if current_price_text else 0.0
            print(f"Extracted Currency: {currency}, Current Price: {current_price_text}")

            # Extract the old price
            old_price_element = driver.find_element(By.CSS_SELECTOR, 'section.product-price-new-container section.savings span.striked-off')
            old_price_text = old_price_element.text.strip().replace(',', '').replace('SAR', '').strip()
            old_price = float(old_price_text) if old_price_text else 0.0
            print(f"Extracted Old Price: {old_price_text}")

            # Extract the price saving
            price_saving_element = driver.find_element(By.CSS_SELECTOR, 'section.product-price-new-container section.savings strong')
            price_saving_text = price_saving_element.text.strip().replace('SAR', '').replace('Save', '').replace(',', '').strip()
            price_saving = float(price_saving_text) if price_saving_text else 0.0
            print(f"Extracted Price Saving: {price_saving_text}")

            # Extract the discount
            discount_element = driver.find_element(By.CSS_SELECTOR, 'section.product-price-new-container section.save-percent-tag')
            discount_text = discount_element.text.strip().replace('% Off', '').strip()
            discount = float(discount_text) if discount_text else 0.0
            print(f"Extracted Discount: {discount_text}")

            if discount == 0.0 and old_price != 0.0:
                discount = ((old_price - current_price) / old_price) * 100
        except Exception as e:
            current_price, old_price, price_saving, discount = 0.0, 0.0, 0.0, 0.0
            print(f"Error extracting price details from eXtra: {e}")

        return [current_datetime, image_url, product_url, title, currency, current_price, old_price, price_saving, discount], image_url
    
    def scrape_tunisianet(driver):
        try:
            # Extract the image URL
            image_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.images-container img#zoom'))
            )
            image_url = image_element.get_attribute('src')
            print(f"Extracted Image URL: {image_url}")
        except Exception as e:
            image_url = "N/A"
            print(f"Error extracting image URL: {e}")

        try:
            # Extract the product title
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.h1[itemprop="name"]'))
            )
            title = title_element.text.strip()
            print(f"Extracted Title: {title}")
        except Exception as e:
            title = "N/A"
            print(f"Error extracting title: {e}")

        try:
            # Extract the current price
            price_now_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.product-prices span[itemprop="price"]'))
            )
            currency = "TND"  # Adjust currency if needed
            current_price_text = price_now_element.text.strip().replace(',', '.').replace('DT', '').strip()
            current_price = float(current_price_text) if current_price_text else 0.0
            print(f"Extracted Currency: {currency}, Current Price: {current_price_text}")

            # The old price, price saving, and discount might not be available in the provided HTML
            old_price, price_saving, discount = 0.0, 0.0, 0.0
        except Exception as e:
            current_price, old_price, price_saving, discount = 0.0, 0.0, 0.0, 0.0
            print(f"Error extracting price details: {e}")

        return [current_datetime, image_url, product_url, title, currency, current_price, old_price, price_saving, discount], image_url
    
    def scrape_mytek(driver):
        try:
            # Extract the image URL
            image_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.carousel-item.active img#productimg'))
            )
            image_url = image_element.get_attribute('src')
            print(f"Extracted Image URL: {image_url}")
        except Exception as e:
            image_url = "N/A"
            print(f"Error extracting image URL: {e}")

        try:
            # Extract the product title
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.page-title-wrapper.product h1.page-title span.base'))
            )
            title = title_element.text.strip()
            print(f"Extracted Title: {title}")
        except Exception as e:
            title = "N/A"
            print(f"Error extracting title: {e}")

        try:
            # Extract the current price and currency
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.price-box.price-final_price span.price-wrapper span.price'))
            )
            currency_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'meta[itemprop="priceCurrency"]'))
            )
            currency = currency_element.get_attribute('content')
            current_price_text = price_element.text.strip().replace(',', '.').replace('DT', '').strip()
            current_price = float(current_price_text) if current_price_text else 0.0
            print(f"Extracted Currency: {currency}, Current Price: {current_price_text}")

            # The old price, price saving, and discount might not be available in the provided HTML
            old_price, price_saving, discount = 0.0, 0.0, 0.0
        except Exception as e:
            current_price, old_price, price_saving, discount = 0.0, 0.0, 0.0, 0.0
            print(f"Error extracting price details: {e}")

        return [current_datetime, image_url, product_url, title, currency, current_price, old_price, price_saving, discount], image_url

    if not is_valid_url(product_url):
        print(f"Invalid URL: {product_url}")
        return ["N/A"] * 9, "N/A"

    driver.get(product_url)
    time.sleep(5)
    current_datetime = datetime.now()

    if "noon" in product_url:
        return scrape_noon(driver)
    elif "jarir" in product_url:
        return scrape_jarir(driver)
    elif "extra" in product_url:
        return scrape_extra(driver)
    elif "tunisianet" in product_url:
        return scrape_tunisianet(driver)
    elif "mytek" in product_url:
        return scrape_mytek(driver)
    else:
        print(f"Unknown site for URL: {product_url}")
        return ["N/A"] * 9, "N/A"


def scrape_and_load_data():
    driver = get_driver()
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Fetch product links from the links table
        cursor.execute('SELECT id, product_link FROM links')
        link_rows = cursor.fetchall()

        for link_id, product_link in link_rows:
            product_details, image_url = scrape_product_details(driver, product_link)

            # Check if the product already exists
            cursor.execute('''
                SELECT id, title, category FROM products
                WHERE product_link = ?
            ''', (product_link,))

            result = cursor.fetchone()

            if result:
                # Product exists, use the existing title and category
                product_id, existing_title, existing_category = result
                title = existing_title
                category = existing_category
                logging.info(f'Product already exists. Using existing title: {title} and category: {category}')
            else:
                # Product does not exist, use the scraped title and transform it
                title = product_details[3]  # Assuming the scraped title is the 4th element in product_details
                category = extract_category(title)
                category = standardize_category(category)
                title = transform_title(title)
                logging.info(f'Product does not exist. Using transformed title: {title} and extracted category: {category}')

            # Insert product details into the products table
            cursor.execute('''
                INSERT INTO products (date, image_url, product_link, title, category, currency, current_price, old_price, price_saving, discount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_details[0], image_url, product_link, title, category, product_details[4], product_details[5], product_details[6], product_details[7], product_details[8]))

            # Get the ID of the newly inserted product
            product_id = cursor.lastrowid

            # Get the project IDs associated with the current product_link
            project_ids = get_project_ids_for_product(cursor, link_id)

            # Insert associations into project_product table
            for project_id in project_ids:
                cursor.execute('''
                    INSERT INTO project_product (project_id, product_id)
                    VALUES (?, ?)
                ''', (project_id, product_id))

            # Update the image URL in the links table
            cursor.execute('''
                UPDATE links
                SET image_url = ?
                WHERE id = ?
            ''', (image_url, link_id))

        # Commit and close the connection
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"An error occurred while scraping and loading data: {e}")
    finally:
        driver.quit()        

def get_project_ids_for_product(cursor, link_id):
    # Query to get the project_ids associated with the given link_id
    cursor.execute('''
        SELECT project_id
        FROM project_link
        WHERE link_id = ?
    ''', (link_id,))

    results = cursor.fetchall()
    project_ids = [row[0] for row in results]
    return project_ids

def schedule_scraping():
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # Schedule the scraping task at 10:32 AM every day
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scrape_and_load_data, trigger='cron', hour=15, minute=14)
    scheduler.start()

    # Log when the scheduler starts
    logging.info('Scheduler started successfully.')

    # Register shutdown of scheduler on exit
    atexit.register(lambda: scheduler.shutdown())
    logging.info('Scheduler shutdown registered.')
    
def scrape_single_product(product_url):
    logging.debug(f'Starting scrape for URL: {product_url}')
    
    driver = get_driver()
    try:
        # Scrape product details
        product_details, image_url = scrape_product_details(driver, product_url)
        
        # Connect to SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if the product already exists
        cursor.execute('''
            SELECT id, title, category FROM products
            WHERE product_link = ?
        ''', (product_url,))
        
        result = cursor.fetchone()

        if result:
            # Product exists, use the existing title and category
            product_id, existing_title, existing_category = result
            title = existing_title
            category = existing_category
            logging.info(f'Product already exists. Using existing title: {title} and category: {category}')
        else:
            # Product does not exist, use the scraped title and transform it
            title = product_details[3]  # Assuming the scraped title is the 4th element in product_details
            category = extract_category(title)
            category = standardize_category(category)
            title = transform_title(title)
            logging.info(f'Product does not exist. Using transformed title: {title} and extracted category: {category}')
        
        # Insert product details into the products table
        cursor.execute('''
            INSERT INTO products (date, image_url, product_link, title, category, currency, current_price, old_price, price_saving, discount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_details[0], image_url, product_url, title, category, product_details[4], product_details[5], product_details[6], product_details[7], product_details[8]))

        # Get the ID of the newly inserted product
        product_id = cursor.lastrowid

        # Update the image URL in the links table based on the product URL
        cursor.execute('''
            UPDATE links
            SET image_url = ?
            WHERE product_link = ?
        ''', (image_url, product_url))

        # Fetch project IDs related to the product link from project_link
        cursor.execute('''
            SELECT project_id
            FROM project_link
            WHERE link_id = (SELECT id FROM links WHERE product_link = ?)
        ''', (product_url,))

        project_ids = cursor.fetchall()

        for project_id in project_ids:
            project_id = project_id[0]

            # Check if the product is already associated with the project
            cursor.execute('''
                SELECT 1
                FROM project_product
                WHERE project_id = ? AND product_id = ?
            ''', (project_id, product_id))

            if cursor.fetchone() is None:
                # Insert association into project_product table
                cursor.execute('''
                    INSERT INTO project_product (project_id, product_id)
                    VALUES (?, ?)
                ''', (project_id, product_id))
                logging.info(f'Product ID {product_id} associated with Project ID {project_id}.')
            else:
                logging.info(f'Product ID {product_id} is already associated with Project ID {project_id}.')

        # Commit the changes
        conn.commit()
        logging.info(f'Product details and image URL updated for URL: {product_url}')
        
    except Exception as e:
        logging.error(f"An error occurred while scraping and updating product: {e}")
    finally:
        conn.close()
        driver.quit()

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def schedule_single_scrape(product_url):
    logging.debug(f'Starting scheduling for URL: {product_url}')
    
    scheduler = BackgroundScheduler()
    # Schedule the scrape to run immediately
    scheduler.add_job(func=scrape_single_product, trigger='date', run_date=datetime.now() + timedelta(seconds=1), args=[product_url])
    scheduler.start()

    # Log when the scheduler starts
    logging.info(f'Single scrape scheduled for URL: {product_url}.')

    # Register shutdown of scheduler on exit
    atexit.register(lambda: scheduler.shutdown())
    logging.info('Scheduler shutdown registered.')


# Call the schedule function when the script runs
if __name__ == '__main__':
    schedule_scraping()
