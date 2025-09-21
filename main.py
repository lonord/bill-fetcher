import imaplib
import email
import os
import argparse
import yaml
import logging
import base64
import quopri

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_parsers():
    """Load all available parsers from the parsers package."""
    from parsers import PARSERS
    return PARSERS


def save_attachment(part, output_dir, filename):
    """Save email attachment to the output directory."""
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(part.get_payload(decode=True))
    return filepath


def resolve_path(path, base_dir):
    """Convert relative path to absolute path based on base directory."""
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(base_dir, path))


def decode_mime_header(header_value):
    """Decode MIME-encoded email header values (RFC 2047)."""
    if not header_value:
        return ""
    
    try:
        # Use email.header.decode_header to decode MIME headers
        decoded_parts = email.header.decode_header(header_value)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    # If no encoding specified, try UTF-8
                    try:
                        decoded_string += part.decode('utf-8')
                    except UnicodeDecodeError:
                        # If UTF-8 fails, use latin-1 as fallback
                        decoded_string += part.decode('latin-1')
            else:
                decoded_string += part
        
        return decoded_string
    except Exception as e:
        logging.warning(f"Failed to decode header '{header_value}': {e}")
        return header_value


def process_emails(config, output_dir, parsers):
    """Process emails: fetch, parse and save attachments."""
    imap_server = config["imap_server"]
    email_user = config["email_user"]
    email_pass = config["email_pass"]
    mailbox = config.get("mailbox", "INBOX")

    # Connect to IMAP
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_user, email_pass)
    
    # Select mailbox and check if successful
    status, data = mail.select(mailbox)
    if status != "OK":
        logging.error(f"Failed to select mailbox '{mailbox}': {data}")
        logging.info("Available mailboxes:")
        status, mailboxes = mail.list()
        if status == "OK":
            for mailbox_info in mailboxes:
                logging.info(f"  {mailbox_info.decode()}")
        mail.logout()
        return False

    # Build search criteria
    search_criteria = ["UNSEEN"]  # Default search for unread emails
    
    # If sender filter is configured, add to search criteria
    sender_filter = config.get("sender_filter")
    if sender_filter:
        if isinstance(sender_filter, list):
            # Multiple senders, use OR condition
            sender_conditions = []
            for sender in sender_filter:
                sender_conditions.append(f'FROM "{sender}"')
            search_criteria.append(f"({' OR '.join(sender_conditions)})")
        else:
            # Single sender
            search_criteria.append(f'FROM "{sender_filter}"')
    
    # Build complete search criteria
    search_query = f"({' '.join(search_criteria)})"
    logging.info(f"Searching with criteria: {search_query}")
    
    # Search emails with criteria
    status, messages = mail.search(None, search_query)
    if status != "OK":
        logging.error("Failed to search emails")
        mail.close()
        mail.logout()
        return False

    for num in messages[0].split():
        status, data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            logging.error(f"Failed to fetch email ID {num.decode()}")
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_header(msg.get("Subject", ""))
        sender = decode_mime_header(msg.get("From", ""))

        logging.info(
            f"Processing email ID {num.decode()} - Subject: {subject}, From: {sender}"
        )

        # Try all parsers
        parsed_success = False
        for parser in parsers:
            if parser["match"](subject, sender):
                success = parser["parse"](msg, num.decode(), output_dir)
                if success:
                    parsed_success = True
                    # Mark as read
                    mail.store(num, "+FLAGS", "\\Seen")
                    logging.info(
                        f"Email ID {num.decode()} parsed successfully using {parser['name']} parser and marked as read"
                    )
                    break
        if not parsed_success:
            mail.store(num, "-FLAGS", "\\Seen")
            logging.info(f"No parser matched for email ID {num.decode()}")

    mail.close()
    mail.logout()
    return True


def run_extract(output_dir, extract_dir, parsers, extra_params, keep_files=False):
    """Run extract operation on files in output_dir."""
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        for parser in parsers:
            supported, success = parser["extract"](
                filepath, extract_dir, extra_params
            )
            if not supported:
                continue
            if not success:
                logging.error(
                    f"Extract failed for {filename} using {parser['name']} parser"
                )
                continue
            
            # Extract successful, conditionally delete the original file
            if not keep_files:
                try:
                    os.remove(filepath)
                    logging.info(f"Successfully extracted and deleted {filename}")
                except OSError as e:
                    logging.error(f"Failed to delete {filename}: {e}")
            else:
                logging.info(f"Successfully extracted {filename} (keeping original file)")
            break


def main():
    arg_parser = argparse.ArgumentParser(description="IMAP Email Reader and Parser")
    arg_parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: ./config.yaml)",
    )
    arg_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep intermediate files in output_dir after successful extract",
    )
    arg_parser.add_argument(
        "-p",
        "--parse-only",
        action="store_true",
        help="Only perform email fetching and parsing, skip extract operation",
    )
    arg_parser.add_argument(
        "-e",
        "--extract-only",
        action="store_true",
        help="Only perform extract operation, skip email fetching and parsing",
    )
    args = arg_parser.parse_args()
    
    # Validate that p and e parameters are not specified together
    if args.parse_only and args.extract_only:
        logging.error("Error: -p and -e parameters cannot be specified together")
        return

    # Get config file directory for resolving relative paths
    config_dir = os.path.dirname(os.path.abspath(args.config))

    # Load config
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validate required IMAP connection parameters (only needed if not extract-only)
    if not args.extract_only:
        required_params = ["imap_server", "email_user", "email_pass"]
        missing_params = []
        
        for param in required_params:
            if param not in config or not config[param]:
                missing_params.append(param)
        
        if missing_params:
            logging.error(f"Missing or empty required parameters: {', '.join(missing_params)}")
            logging.error("Please check your config file and ensure all required parameters are set.")
            return

    output_dir = resolve_path(config.get("output_dir", "output"), config_dir)
    extract_dir = resolve_path(config.get("extract_dir", "extract"), config_dir)
    extra_params = config.get("extra_params", {})

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(extract_dir, exist_ok=True)

    parsers = load_parsers()

    # Execute based on parameters
    if args.extract_only:
        # Only run extract operation
        logging.info("Running extract-only mode")
        run_extract(output_dir, extract_dir, parsers, extra_params, args.keep)
    elif args.parse_only:
        # Only run email processing
        logging.info("Running parse-only mode")
        process_emails(config, output_dir, parsers)
    else:
        # Run both email processing and extract
        logging.info("Running full mode: email processing + extract")
        if process_emails(config, output_dir, parsers):
            run_extract(output_dir, extract_dir, parsers, extra_params, args.keep)


if __name__ == "__main__":
    main()
