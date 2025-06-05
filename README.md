# ASIC Gazette Scraper V2

A robust Python web scraper for extracting Australian Securities and Investments Commission (ASIC) Gazette data from their official website. This tool automates the collection of historical gazette publications from 2011-2020 and exports the data to CSV format for analysis.

## Features

- **Dynamic Content Handling**: Automatically expands accordion sections and waits for dynamic content to load
- **Intelligent Table Detection**: Uses content analysis to identify the correct data table for each year
- **Flexible Data Extraction**: Handles variable column layouts and multiple links within single cells
- **Dynamic CSV Generation**: Automatically discovers and creates columns based on the actual data structure found
- **Comprehensive Error Handling**: Robust error handling with detailed logging for debugging
- **Resource Management**: Proper WebDriver lifecycle management using context managers

## Prerequisites

- Python 3.7+
- Chrome browser installed
- ChromeDriver (automatically managed by Selenium 4.x)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/asic-gazette-scraper.git
cd asic-gazette-scraper
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Dependencies

```
selenium>=4.0.0
```

## Usage

### Basic Usage

Run the scraper with default settings:

```bash
python asic_scraper.py
```

### Advanced Configuration

Customize the scraper by modifying the `ScraperConfig` in the `main()` function:

```python
config = ScraperConfig(
    target_url="https://asic.gov.au/about-asic/corporate-publications/asic-gazette/asic-gazettes-2011-2020/",
    csv_filename="asic_gazettes_custom.csv",
    headless=False,  # Set to False to see browser window
    page_load_timeout=60,
    element_wait_timeout=15
)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_url` | str | ASIC Gazette URL | Target webpage to scrape |
| `csv_filename` | str | "asic_gazettes.csv" | Output CSV filename |
| `base_url` | str | "https://asic.gov.au" | Base URL for resolving relative links |
| `headless` | bool | True | Run browser in headless mode |
| `page_load_timeout` | int | 30 | Page load timeout in seconds |
| `element_wait_timeout` | int | 10 | Element wait timeout in seconds |
| `delay_between_years` | float | 1.0 | Delay between processing years |

## Output

The scraper generates a CSV file with the following structure:

- **Year**: Publication year (2011-2020)
- **Date**: Publication date
- **ASIC_Gazette_title/url**: ASIC Gazette publication titles and URLs
- **Business_Gazette_title/url**: Business Gazette publication titles and URLs
- **Other_title/url**: Other publication types
- **Notes_title/url**: Additional notes and links

For cells containing multiple links, the scraper automatically creates numbered columns (e.g., `ASIC_Gazette_title_2`, `ASIC_Gazette_url_2`).

## How It Works

1. **Page Loading**: Navigates to the ASIC Gazette archive page
2. **Accordion Expansion**: Finds and expands all year-based accordion sections
3. **Table Detection**: Analyzes multiple tables to identify the correct data table for each year
4. **Data Extraction**: Extracts gazette information including titles, URLs, and metadata
5. **CSV Export**: Generates a structured CSV with dynamic columns based on discovered data

## Logging

The scraper provides comprehensive logging to track progress and debug issues:

```
2024-06-05 10:30:15 - INFO - Chrome WebDriver initialized successfully
2024-06-05 10:30:20 - INFO - Found 10 accordion buttons using selector: button[aria-expanded]
2024-06-05 10:30:25 - INFO - Processing year section 1/10: 2020
2024-06-05 10:30:30 - INFO - ✅ Added 52 rows for year 2020
```

## Error Handling

The scraper includes robust error handling for common scenarios:

- Network timeouts and connection issues
- Missing or changed page elements
- Variable table structures
- Dynamic content loading delays

## Troubleshooting

### Common Issues

**ChromeDriver not found**
- Ensure Chrome browser is installed
- Selenium 4.x automatically manages ChromeDriver

**Timeout errors**
- Increase `page_load_timeout` and `element_wait_timeout` values
- Check internet connection stability

**No data extracted**
- Verify the target URL is accessible
- Check if website structure has changed
- Run with `headless=False` to observe browser behavior

### Debug Mode

Run with visible browser window for debugging:

```python
config = ScraperConfig(
    headless=False,  # Show browser window
    page_load_timeout=60
)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This scraper is designed for educational and research purposes. Please ensure compliance with:

- ASIC's website terms of use
- Applicable data protection regulations
- Responsible scraping practices (reasonable delays, respectful request rates)

## Acknowledgments

- Australian Securities and Investments Commission (ASIC) for providing public access to gazette data
- Selenium WebDriver team for the automation framework

## Support

If you encounter issues or have questions:

1. Check the [Issues](https://github.com/markcastorm/ASIC_Gazzette_Scrapper-version-2/issues) page
2. Review the troubleshooting section above
3. Create a new issue with detailed information about your problem

---

**Note**: This scraper targets the specific structure of the ASIC website as of June 2024. Website changes may require code updates.
