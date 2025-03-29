from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import time
import os
import platform
import subprocess
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

def setup_driver():
    """Setup and return a configured Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        # For Mac ARM64, use system ChromeDriver
        if platform.system() == 'Darwin' and platform.machine() == 'arm64':
            try:
                # Check if ChromeDriver is installed via Homebrew
                result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
                if result.returncode == 0:
                    service = Service(result.stdout.strip())
                else:
                    print("ChromeDriver not found. Installing via Homebrew...")
                    subprocess.run(['brew', 'install', 'chromedriver'], check=True)
                    service = Service('/usr/local/bin/chromedriver')
            except subprocess.CalledProcessError as e:
                print(f"Error installing ChromeDriver: {str(e)}")
                print("\nPlease try installing ChromeDriver manually:")
                print("1. Run: brew install chromedriver")
                print("2. If you get a security warning, go to System Settings > Privacy & Security > Security")
                print("3. Look for ChromeDriver and click 'Allow Anyway'")
                return None
        else:
            # For other systems, use webdriver-manager
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        
        # Create and return the Chrome driver
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error initializing Chrome driver: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Make sure Chrome browser is installed")
        print("2. Try running: pip install --upgrade selenium")
        print("3. If on Mac, try: brew install chromedriver")
        return None

def setup_database():
    """Setup database connection and create table if it doesn't exist"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database credentials from environment variables
        db_params = {
            'dbname': os.getenv('POSTGRES_DB'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD'),
            'host': os.getenv('POSTGRES_HOST'),
            'port': os.getenv('POSTGRES_PORT')
        }
        
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        
        # Create table if it doesn't exist
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mcdonalds_ai (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE,
                    address TEXT,
                    telephone VARCHAR(50),
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    waze_link TEXT
                )
            """)
            conn.commit()
        
        return conn
    except Exception as e:
        print(f"Error setting up database: {str(e)}")
        return None

def insert_outlets_to_db(conn, outlets):
    """Insert outlets data into the database"""
    try:
        with conn.cursor() as cur:
            # Prepare the data for insertion
            values = [(
                outlet['name'],
                outlet['address'],
                outlet['telephone'],
                outlet['latitude'],
                outlet['longitude'],
                outlet['waze_link']
            ) for outlet in outlets]
            
            # First, delete existing records
            cur.execute("DELETE FROM mcdonalds_ai")
            
            # Then insert all new records
            execute_values(cur, """
                INSERT INTO mcdonalds_ai 
                (name, address, telephone, latitude, longitude, waze_link)
                VALUES %s
            """, values)
        conn.commit()
        print("Data successfully inserted into database")
    except Exception as e:
        print(f"Error inserting data into database: {str(e)}")
        conn.rollback()

def scrape_mcdonalds_outlets():
    """Main function to scrape McDonald's outlets data"""
    driver = setup_driver()
    if not driver:
        return
    
    # Setup database connection
    conn = setup_database()
    if not conn:
        print("Failed to setup database connection")
        return
    
    wait = WebDriverWait(driver, 10)
    outlets = []
    
    try:
        # Navigate to the McDonald's location page
        print("Navigating to McDonald's location page...")
        driver.get("https://www.mcdonalds.com.my/locate-us")
        
        # Wait for the state dropdown to be present
        print("Waiting for state dropdown...")
        state_dropdown = wait.until(EC.presence_of_element_located((By.ID, "states")))
        state_dropdown.click()
        
        # Select Kuala Lumpur
        print("Selecting Kuala Lumpur...")
        kuala_lumpur_option = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//select[@id='states']/option[@value='Kuala Lumpur']")))
        kuala_lumpur_option.click()
        
        # Wait for results to load
        print("Waiting for results to load...")
        time.sleep(5)
        
        # Wait for the results container
        results_container = wait.until(EC.presence_of_element_located((By.ID, "results")))
        
        # Find all outlet boxes
        print("Finding outlet boxes...")
        outlet_boxes = results_container.find_elements(By.CSS_SELECTOR, "div[data-v-6bf80f8c].columns")
        
        # Process each outlet
        for box in outlet_boxes:
            try:
                # Extract JSON data from script tag
                script_tag = box.find_element(By.TAG_NAME, "script")
                json_data = json.loads(script_tag.get_attribute("textContent"))
                
                # Only include outlets in Kuala Lumpur
                address = json_data.get("address", "").lower()
                if "kuala lumpur" in address:
                    # Get latitude and longitude
                    latitude = json_data.get("geo", {}).get("latitude", "")
                    longitude = json_data.get("geo", {}).get("longitude", "")
                    
                    # Create Waze link
                    waze_link = f"https://www.waze.com/live-map/directions?navigate=yes&to=ll.{latitude}%2C{longitude}"
                    
                    outlet_info = {
                        "name": json_data.get("name", ""),
                        "address": json_data.get("address", ""),
                        "telephone": json_data.get("telephone", ""),
                        "latitude": latitude,
                        "longitude": longitude,
                        "waze_link": waze_link
                    }
                    
                    outlets.append(outlet_info)
                    print(f"Found outlet: {outlet_info['name']}")
                
            except Exception as e:
                print(f"Error processing an outlet: {str(e)}")
                continue
        
        # Save results to a JSON file
        print(f"\nSaving {len(outlets)} outlets to mcdonalds_outlets.json...")
        with open("mcdonalds_outlets.json", "w", encoding="utf-8") as f:
            json.dump(outlets, f, indent=4, ensure_ascii=False)
        
        # Insert data into database
        print("Inserting data into database...")
        insert_outlets_to_db(conn, outlets)
            
        print(f"\nSuccessfully scraped {len(outlets)} Kuala Lumpur outlets.")
        print("Data saved to mcdonalds_outlets.json and database")
        
    except TimeoutException:
        print("Timeout waiting for elements to load")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Add a delay before closing to see the results
        time.sleep(5)
        driver.quit()
        conn.close()

if __name__ == "__main__":
    scrape_mcdonalds_outlets() 