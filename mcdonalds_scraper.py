from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import time
import psycopg2
from psycopg2.extras import execute_values

def add_unique_constraint(conn):
    """Add unique constraint to name column if it doesn't exist"""
    with conn.cursor() as cur:
        try:
            cur.execute("""
                ALTER TABLE mcdonalds_outlets 
                ADD CONSTRAINT mcdonalds_outlets_name_key UNIQUE (name)
            """)
            conn.commit()
            print("Added unique constraint to name column")
        except psycopg2.Error as e:
            if "already exists" in str(e):
                print("Unique constraint already exists")
            else:
                raise e

def insert_outlets_to_db(conn, outlets):
    """Insert outlets data into the database"""
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
        cur.execute("DELETE FROM mcdonalds_outlets")
        
        # Then insert all new records
        execute_values(cur, """
            INSERT INTO mcdonalds_outlets 
            (name, address, telephone, latitude, longitude, waze_link)
            VALUES %s
        """, values)
    conn.commit()

def scrape_mcdonalds_outlets():
    # Setup Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Commented out to see the browser
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Setup Chrome driver with webdriver-manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 10)
    
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            dbname="mcdonalds_ai",
            user="postgres",  # Replace with your PostgreSQL username
            password="postgres",  # Replace with your PostgreSQL password
            host="localhost",
            port="5432"
        )
        
        # Add unique constraint if it doesn't exist
        add_unique_constraint(conn)
        
        # Navigate to the McDonald's location page
        driver.get("https://www.mcdonalds.com.my/locate-us")
        
        # Wait for the state dropdown to be present and select Kuala Lumpur
        state_dropdown = wait.until(EC.presence_of_element_located((By.ID, "states")))
        state_dropdown.click()  # Open the dropdown
        
        # Select Kuala Lumpur option
        kuala_lumpur_option = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//select[@id='states']/option[@value='Kuala Lumpur']")))
        kuala_lumpur_option.click()
        
        # Wait for results to load
        time.sleep(5)  # Give some time for the results to load
        
        # Wait for the results container
        results_container = wait.until(EC.presence_of_element_located((By.ID, "results")))
        
        # Find all outlet boxes within the results container
        outlet_boxes = results_container.find_elements(By.CSS_SELECTOR, "div[data-v-6bf80f8c].columns")
        
        outlets = []
        for box in outlet_boxes:
            try:
                # Extract JSON data from script tag
                script_tag = box.find_element(By.TAG_NAME, "script")
                json_data = json.loads(script_tag.get_attribute("textContent"))
                
                # Only include outlets in Kuala Lumpur
                address = json_data.get("address", "").lower()
                if "kuala lumpur" in address:
                    # Extract outlet information
                    outlet_info = {
                        "name": json_data.get("name", ""),
                        "address": json_data.get("address", ""),
                        "telephone": json_data.get("telephone", ""),
                        "latitude": json_data.get("geo", {}).get("latitude", ""),
                        "longitude": json_data.get("geo", {}).get("longitude", ""),
                        "waze_link": f"https://www.waze.com/live-map/directions?navigate=yes&to=ll.{json_data.get('geo', {}).get('latitude', '')}%2C{json_data.get('geo', {}).get('longitude', '')}"
                    }
                    
                    outlets.append(outlet_info)
                    print(f"Found outlet: {outlet_info['name']}")
                
            except Exception as e:
                print(f"Error processing an outlet: {str(e)}")
                continue
        
        # Insert data into database
        insert_outlets_to_db(conn, outlets)
        
        # Save results to a JSON file as backup
        with open("mcdonalds_outlets.json", "w", encoding="utf-8") as f:
            json.dump(outlets, f, indent=4, ensure_ascii=False)
            
        print(f"\nSuccessfully scraped {len(outlets)} Kuala Lumpur outlets.")
        print("Data saved to database and mcdonalds_outlets.json")
        
    except TimeoutException:
        print("Timeout waiting for elements to load")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Add a delay before closing to see the results
        time.sleep(5)
        driver.quit()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    scrape_mcdonalds_outlets() 