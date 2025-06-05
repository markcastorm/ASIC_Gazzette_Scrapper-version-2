import csv
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ScraperConfig:
    """Configuration for the ASIC Gazette scraper"""
    target_url: str
    csv_filename: str = "asic_gazettes.csv"
    base_url: str = "https://asic.gov.au"
    headless: bool = True
    page_load_timeout: int = 30
    element_wait_timeout: int = 10
    delay_between_years: float = 1.0

class ASICGazetteScraper:
    """Fixed scraper with correct table selection logic"""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.driver = None
        self.all_data = []
        self.all_columns_found = set()
        
    def __enter__(self):
        self._setup_driver()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        
    def _setup_driver(self):
        """Initialize the Chrome WebDriver with appropriate options"""
        try:
            chrome_options = Options()
            if self.config.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.config.page_load_timeout)
            
            logger.info("Chrome WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
            
    def _cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")
            
    def _resolve_url(self, url: str) -> str:
        """Convert relative URLs to absolute URLs"""
        if not url:
            return ""
        if url.startswith('http'):
            return url
        return urljoin(self.config.base_url, url)
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        cleaned = text.replace('\u00a0', ' ').replace('&nbsp;', ' ')
        return ' '.join(cleaned.split()).strip()
        
    def _extract_multiple_links_data(self, cell) -> Tuple[List[str], List[str]]:
        """Extract titles and URLs from a cell that may contain multiple links"""
        try:
            links = cell.find_elements(By.TAG_NAME, "a")
            
            if not links:
                # Check if cell has text content without links
                text_content = self._clean_text(cell.text)
                if text_content:
                    return [text_content], [""]
                return [], []
            
            titles = []
            urls = []
            
            for link in links:
                title = self._clean_text(link.text)
                url = link.get_attribute("href")
                
                if title:
                    titles.append(title)
                else:
                    titles.append("")
                    
                if url:
                    resolved_url = self._resolve_url(url.strip())
                    urls.append(resolved_url)
                else:
                    urls.append("")
            
            # Debug logging for multiple links
            if len(links) > 1:
                logger.info(f"🔗 Found {len(links)} links in cell: {[t for t in titles if t]}")
            
            return titles, urls
            
        except Exception as e:
            logger.warning(f"Error extracting multiple links data: {e}")
            return [], []
    
    def _store_cell_data(self, result: Dict, prefix: str, titles: List[str], urls: List[str]) -> None:
        """Store cell data with dynamic column naming and track all column names"""
        if not titles and not urls:
            # Store empty data
            result[f"{prefix}_title"] = ""
            result[f"{prefix}_url"] = ""
            self.all_columns_found.add(f"{prefix}_title")
            self.all_columns_found.add(f"{prefix}_url")
            return
        
        # Ensure we have at least as many URLs as titles
        while len(urls) < len(titles):
            urls.append("")
        
        # Store all title/url pairs
        for i, (title, url) in enumerate(zip(titles, urls)):
            if i == 0:
                # First entry uses base column names
                title_col = f"{prefix}_title"
                url_col = f"{prefix}_url"
            else:
                # Additional entries use numbered columns
                title_col = f"{prefix}_title_{i+1}"
                url_col = f"{prefix}_url_{i+1}"
            
            result[title_col] = title
            result[url_col] = url
            
            # Track these column names for later header generation
            self.all_columns_found.add(title_col)
            self.all_columns_found.add(url_col)
        
        # Store any remaining URLs without corresponding titles
        for i in range(len(titles), len(urls)):
            url_col = f"{prefix}_url_{i+1}"
            result[url_col] = urls[i]
            self.all_columns_found.add(url_col)
        
        # Log when we find multiple items
        if len(titles) > 1 or len(urls) > 1:
            logger.info(f"📊 {prefix}: {len(titles)} titles, {len(urls)} URLs")
    
    def _find_correct_table_for_year(self, year: str) -> Optional[object]:
        """Find the correct table for a specific year based on content analysis"""
        try:
            # Get all visible tables
            all_tables = self.driver.find_elements(By.TAG_NAME, "table")
            visible_tables = [table for table in all_tables if table.is_displayed()]
            
            logger.info(f"🔍 Searching {len(visible_tables)} tables for year {year} data...")
            
            # Look for table with data matching the target year
            year_suffix = year[-2:]  # Get last 2 digits (e.g., "20" from "2020")
            
            for table_idx, table in enumerate(visible_tables):
                try:
                    # Get sample rows from this table
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    data_rows = [row for row in rows if not row.find_elements(By.TAG_NAME, "th")]
                    
                    if not data_rows:
                        continue
                    
                    # Check first few rows for year patterns
                    year_match_count = 0
                    total_gazette_links = 0
                    
                    for row in data_rows[:10]:  # Check first 10 rows
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            # Check ASIC Gazette column (usually column 2)
                            asic_cell = cells[1]
                            links = asic_cell.find_elements(By.TAG_NAME, "a")
                            
                            for link in links:
                                link_text = self._clean_text(link.text)
                                if link_text and '/' in link_text:
                                    total_gazette_links += 1
                                    # Check if this link matches our target year
                                    if link_text.endswith(f'/{year_suffix}'):
                                        year_match_count += 1
                            
                            # Also check Business Gazette column if it exists
                            if len(cells) >= 3:
                                business_cell = cells[2]
                                business_links = business_cell.find_elements(By.TAG_NAME, "a")
                                for link in business_links:
                                    link_text = self._clean_text(link.text)
                                    if link_text and '/' in link_text:
                                        total_gazette_links += 1
                                        if link_text.endswith(f'/{year_suffix}'):
                                            year_match_count += 1
                    
                    # Calculate match percentage
                    match_percentage = (year_match_count / total_gazette_links * 100) if total_gazette_links > 0 else 0
                    
                    logger.info(f"   Table {table_idx}: {year_match_count}/{total_gazette_links} links match {year} ({match_percentage:.1f}%)")
                    
                    # If majority of links match our target year, this is our table
                    if match_percentage > 70 and total_gazette_links > 5:  # At least 70% match and reasonable sample size
                        logger.info(f"   ✅ Selected Table {table_idx} for year {year}")
                        return table
                        
                except Exception as e:
                    logger.warning(f"Error analyzing table {table_idx}: {e}")
                    continue
            
            # Fallback: if no table has clear year match, use table order
            # Based on diagnostic: Table 0=2020, Table 1=2019, etc.
            year_to_table_index = {
                '2020': 0, '2019': 1, '2018': 3, '2017': 4, '2016': 5,
                '2015': 6, '2014': 7, '2013': 8, '2012': 9, '2011': 10
            }
            
            if year in year_to_table_index:
                table_idx = year_to_table_index[year]
                if table_idx < len(visible_tables):
                    logger.info(f"   🔄 Fallback: Using table {table_idx} for year {year}")
                    return visible_tables[table_idx]
            
            logger.warning(f"❌ No suitable table found for year {year}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding table for year {year}: {e}")
            return None
            
    def _extract_row_data(self, row, year: str) -> Optional[Dict]:
        """Extract data from a single table row with full dynamic column detection"""
        try:
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) < 4:
                logger.warning(f"Row has fewer than 4 cells ({len(cells)}), skipping")
                return None
            
            # Extract date (column 1)
            date = self._clean_text(cells[0].text)
            
            # Initialize result dictionary
            result = {
                'Year': year,
                'Date': date
            }
            
            # Always track these base columns
            self.all_columns_found.add('Year')
            self.all_columns_found.add('Date')
            
            # Extract ASIC Gazette data (column 2)
            asic_titles, asic_urls = self._extract_multiple_links_data(cells[1])
            self._store_cell_data(result, 'ASIC_Gazette', asic_titles, asic_urls)
            
            # Extract Business Gazette data (column 3)  
            business_titles, business_urls = self._extract_multiple_links_data(cells[2])
            self._store_cell_data(result, 'Business_Gazette', business_titles, business_urls)
            
            # Handle different column layouts for Other/Notes
            if len(cells) == 4:
                # 4-column layout: Date, ASIC Gazette, Business Gazette, Notes
                notes_titles, notes_urls = self._extract_multiple_links_data(cells[3])
                # Also get pure text content for notes
                notes_text = self._clean_text(cells[3].text)
                
                # If we have both links and text, prioritize the full text content
                if notes_text and not notes_titles:
                    notes_titles = [notes_text]
                elif notes_text and notes_titles:
                    # Text might contain more info than just link titles
                    notes_titles[0] = notes_text  # Replace first title with full text
                
                self._store_cell_data(result, 'Other_Notes', notes_titles, notes_urls)
                
            elif len(cells) >= 5:
                # 5-column layout: Date, ASIC Gazette, Business Gazette, Other, Notes
                other_titles, other_urls = self._extract_multiple_links_data(cells[3])
                other_text = self._clean_text(cells[3].text)
                
                notes_titles, notes_urls = self._extract_multiple_links_data(cells[4])
                notes_text = self._clean_text(cells[4].text)
                
                # Store Other column
                if other_text and not other_titles:
                    other_titles = [other_text]
                elif other_text and other_titles:
                    other_titles[0] = other_text
                self._store_cell_data(result, 'Other', other_titles, other_urls)
                
                # Store Notes column  
                if notes_text and not notes_titles:
                    notes_titles = [notes_text]
                elif notes_text and notes_titles:
                    notes_titles[0] = notes_text
                self._store_cell_data(result, 'Notes', notes_titles, notes_urls)
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting row data: {e}")
            return None
            
    def _extract_table_data(self, table, year: str) -> List[Dict]:
        """Extract data from a single table"""
        try:
            data_rows = []
            
            # Find tbody and all data rows
            try:
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
            except NoSuchElementException:
                # Some tables might not have tbody, try direct tr elements
                rows = table.find_elements(By.TAG_NAME, "tr")
                # Filter out header rows (those with th elements)
                rows = [row for row in rows if not row.find_elements(By.TAG_NAME, "th")]
            
            logger.info(f"Processing {len(rows)} rows for year {year}")
            
            for row_idx, row in enumerate(rows):
                row_data = self._extract_row_data(row, year)
                if row_data:
                    data_rows.append(row_data)
                    
                    # Log every 10th row to show progress
                    if (row_idx + 1) % 10 == 0:
                        logger.info(f"  Processed {row_idx + 1}/{len(rows)} rows for {year}")
            
            return data_rows
            
        except Exception as e:
            logger.error(f"Error extracting table data for year {year}: {e}")
            return []
    
    def _generate_dynamic_headers(self) -> List[str]:
        """Generate CSV headers based on ALL columns found during extraction"""
        # Define the preferred order for columns
        ordered_headers = []
        
        # Always start with Year and Date
        ordered_headers.extend(['Year', 'Date'])
        
        # Group columns by type and sort them naturally
        asic_columns = sorted([col for col in self.all_columns_found if col.startswith('ASIC_Gazette')])
        business_columns = sorted([col for col in self.all_columns_found if col.startswith('Business_Gazette')])
        other_columns = sorted([col for col in self.all_columns_found if col.startswith('Other_Notes')])
        other_only_columns = sorted([col for col in self.all_columns_found if col.startswith('Other') and not col.startswith('Other_Notes')])
        notes_columns = sorted([col for col in self.all_columns_found if col.startswith('Notes')])
        
        # Add them in logical order
        ordered_headers.extend(asic_columns)
        ordered_headers.extend(business_columns)
        ordered_headers.extend(other_only_columns)
        ordered_headers.extend(notes_columns)
        ordered_headers.extend(other_columns)
        
        # Add any remaining columns we might have missed
        remaining_columns = sorted([col for col in self.all_columns_found if col not in ordered_headers])
        ordered_headers.extend(remaining_columns)
        
        logger.info(f"🏗️  Generated {len(ordered_headers)} dynamic headers")
        logger.info(f"📊 Column breakdown:")
        logger.info(f"   ASIC Gazette: {len(asic_columns)} columns")
        logger.info(f"   Business Gazette: {len(business_columns)} columns") 
        logger.info(f"   Other/Notes: {len(other_columns + other_only_columns + notes_columns)} columns")
        
        # Show sample of what we found
        asic_max = len([col for col in asic_columns if 'title' in col])
        business_max = len([col for col in business_columns if 'title' in col])
        logger.info(f"🎯 Max items per cell - ASIC: {asic_max}, Business: {business_max}")
        
        return ordered_headers
        
    def _normalize_row_data(self, row_data: Dict, headers: List[str]) -> Dict:
        """Ensure row data has all required columns"""
        normalized = {}
        for header in headers:
            normalized[header] = row_data.get(header, "")
        return normalized
        
    def scrape_data(self) -> List[Dict]:
        """Main scraping method with correct table selection"""
        try:
            logger.info(f"Starting scrape of {self.config.target_url}")
            
            # Load the page
            self.driver.get(self.config.target_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, self.config.element_wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # STEP 1: Find all accordion buttons and expand them first
            logger.info("Step 1: Finding and expanding all accordion sections...")
            
            accordion_buttons = []
            selectors_to_try = [
                "button[aria-expanded]",
                ".accordion-button",
                "h2 button",
                "h3 button",
                "[data-bs-toggle='collapse']",
                "[data-toggle='collapse']",
            ]
            
            for selector in selectors_to_try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    text = self._clean_text(btn.text)
                    if any(year_str in text for year_str in ['2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011']):
                        accordion_buttons.append((btn, text))
                        
                if accordion_buttons:
                    logger.info(f"Found {len(accordion_buttons)} accordion buttons using selector: {selector}")
                    break
            
            if not accordion_buttons:
                logger.warning("No accordion buttons found!")
                return self.all_data
            
            # Expand all accordions first
            expanded_sections = []
            for i, (btn, year_text) in enumerate(accordion_buttons):
                try:
                    is_expanded = btn.get_attribute("aria-expanded")
                    if is_expanded == "false":
                        logger.info(f"Expanding accordion {i+1}/{len(accordion_buttons)}: {year_text}")
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1.5)
                        expanded_sections.append((btn, year_text))
                    else:
                        logger.info(f"Accordion already expanded: {year_text}")
                        expanded_sections.append((btn, year_text))
                except Exception as e:
                    logger.warning(f"Could not expand accordion {year_text}: {e}")
            
            logger.info(f"Expanded {len(expanded_sections)} accordion sections")
            
            # STEP 2: Wait for all content to load
            logger.info("Step 2: Waiting for all content to load...")
            time.sleep(3)
            
            # STEP 3: Process each year with correct table selection
            logger.info("Step 3: Processing each year with correct table selection...")
            
            for i, (btn, year_text) in enumerate(expanded_sections):
                try:
                    # Extract year from text
                    year = "Unknown"
                    for potential_year in ['2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011']:
                        if potential_year in year_text:
                            year = potential_year
                            break
                    
                    logger.info(f"\n{'='*50}")
                    logger.info(f"Processing year section {i+1}/{len(expanded_sections)}: {year}")
                    logger.info(f"{'='*50}")
                    
                    # Find the correct table for this specific year
                    table = self._find_correct_table_for_year(year)
                    
                    if table:
                        year_data = self._extract_table_data(table, year)
                        if year_data:
                            self.all_data.extend(year_data)
                            logger.info(f"✅ Added {len(year_data)} rows for year {year}")
                            logger.info(f"📈 Total columns discovered so far: {len(self.all_columns_found)}")
                        else:
                            logger.warning(f"No data extracted for year {year}")
                    else:
                        logger.warning(f"❌ No table found for year {year}")
                        
                except Exception as e:
                    logger.error(f"Error processing year section {year_text}: {e}")
                    continue
                            
            logger.info(f"\n🎉 Total rows extracted: {len(self.all_data)}")
            logger.info(f"🏗️  Total unique columns discovered: {len(self.all_columns_found)}")
            
            return self.all_data
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            raise
            
    def save_to_csv(self, data: List[Dict]):
        """Save scraped data to CSV file with truly dynamic headers"""
        try:
            if not data:
                logger.warning("No data to save")
                return
                
            # Generate headers based on ALL columns discovered during extraction
            headers = self._generate_dynamic_headers()
            
            # Normalize all row data to have consistent columns
            normalized_data = [self._normalize_row_data(row, headers) for row in data]
            
            with open(self.config.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(normalized_data)
                
            logger.info(f"💾 Data saved to {self.config.csv_filename}")
            logger.info(f"📊 CSV contains {len(headers)} columns and {len(normalized_data)} rows")
            
            # Show a preview of some column names to verify structure
            sample_headers = headers[:10] + (['...'] if len(headers) > 10 else [])
            logger.info(f"🔍 Column preview: {sample_headers}")
            
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            raise

def main():
    """Main execution function"""
    # Configuration for the scraper
    config = ScraperConfig(
        target_url="https://asic.gov.au/about-asic/corporate-publications/asic-gazette/asic-gazettes-2011-2020/",
        csv_filename="asic_gazettes_2011_2020_fixed.csv",
        base_url="https://asic.gov.au",
        headless=True,
        page_load_timeout=30,
        element_wait_timeout=10,
        delay_between_years=1.0
    )
    
    try:
        # Use context manager for proper cleanup
        with ASICGazetteScraper(config) as scraper:
            # Scrape the data
            data = scraper.scrape_data()
            
            # Save to CSV
            scraper.save_to_csv(data)
            
        logger.info("🎉 Scraping completed successfully!")
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise

if __name__ == "__main__":
    main()