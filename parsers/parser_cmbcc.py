import os
import csv
import io
import re
from bs4 import BeautifulSoup


def match(subject, sender):
    return "招商银行信用卡" in (subject or "") or "招商银行信用卡" in (sender or "")


def parse(msg, msg_id, output_dir):
    try:
        body_html = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    body_html = part.get_payload(decode=True).decode(
                        charset, errors="ignore"
                    )
                    break
        else:
            if msg.get_content_type() == "text/html":
                charset = msg.get_content_charset() or "utf-8"
                body_html = msg.get_payload(decode=True).decode(
                    charset, errors="ignore"
                )

        if not body_html:
            print("  No HTML body found")
            return False

        filepath = os.path.join(output_dir, f"cmbcc_{msg_id}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(body_html)

        print(f"  Email HTML saved: {filepath}")
        return True

    except Exception as e:
        print(f"  Error parsing CMBCC email: {e}")
        return False


def extract(filename, extract_dir, config):
    """
    Extracts credit card transaction details from a CMB CC html bill file
    and saves it as a CSV file.

    Args:
        filename (str): The path to the input html file.
        extract_dir (str): The directory where the output CSV file will be saved.
        config (dict): Configuration dictionary (unused in this implementation).
    """
    try:
        # Validate filename format
        base_filename = os.path.basename(filename)
        if not (base_filename.startswith("cmbcc_") and base_filename.endswith(".html")):
            print(f"Error: Filename {base_filename} does not match expected format (should start with 'cmbcc_' and end with '.html')")
            return False, False

        with open(filename, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')
        
        header = ['交易日', '记账日', '交易摘要', '人民币金额', '卡号末四位', '交易地金额', '交易地']
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        
        # Find all transaction rows - they have specific style attributes
        transaction_rows = soup.find_all('tr', style=lambda x: x and 'width:608px' in x and 'height:17px' in x)
        
        for tr in transaction_rows:
            inner_table = tr.find('table')
            if inner_table:
                cells = inner_table.find_all('td')
                if len(cells) >= 7:  # At least 7 columns (first one is empty)
                    # Extract text from each cell, skipping the first empty cell
                    data = []
                    for i in range(1, 8):  # Skip first cell (index 0), get cells 1-7
                        if i < len(cells):
                            cell_text = cells[i].get_text(strip=True).replace('\n', ' ').replace('\r', '')
                            # Clean up currency symbols and extra spaces
                            if '¥' in cell_text:
                                cell_text = cell_text.replace('¥', '').replace('&nbsp;', '').strip()
                            data.append(cell_text)
                        else:
                            data.append('')
                    
                    # Only write rows that have meaningful data (not just empty cells)
                    if any(data) and len(data) == 7:
                        writer.writerow(data)
        
        # Extract year and month from HTML content
        year_month = "unknown"
        
        # Try to find date pattern like "2025年7月17日" or "2025年07月17日"
        date_pattern = r'(\d{4})年(\d{1,2})月'
        date_match = re.search(date_pattern, html_content)
        
        if date_match:
            year = date_match.group(1)
            month = date_match.group(2).zfill(2)  # Ensure month is 2 digits
            year_month = f"{year}_{month}"
        else:
            # Fallback: try to find any 4-digit year followed by month
            fallback_pattern = r'(\d{4}).*?(\d{1,2})月'
            fallback_match = re.search(fallback_pattern, html_content)
            if fallback_match:
                year = fallback_match.group(1)
                month = fallback_match.group(2).zfill(2)
                year_month = f"{year}_{month}"
        
        csv_filename = f"cmbcc_{year_month}.csv"
        csv_filepath = os.path.join(extract_dir, csv_filename)
        
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as f:
            f.write(output.getvalue())
            
        print(f"Successfully extracted data to {csv_filepath}")
        return True, True

    except FileNotFoundError:
        print(f"Error: The file was not found at {filename}")
        return False, False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, False
