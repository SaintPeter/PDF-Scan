import os
import re
import sys
import glob
import time
import shutil
import pytesseract
from pdf2image import convert_from_path
import logging
logging.basicConfig(
    filename='pdf_scanner_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s %(message)s',
    datefmt='[%m/%d/%Y %I:%M:%S %p]')


# Check Command Line options
if len(sys.argv) == 3:
    search_path = sys.argv[1]
    prefix = sys.argv[2]
else:
    logging.error("Invalid number of parameters, 2 required")
    logging.error("Params: ")
    logging.error(sys.argv)
    sys.exit(1)

# Prevent multiple copies from running
try:
    lock_file = os.open(prefix + ".lock", os.O_CREAT | os.O_EXCL | os.O_TEMPORARY)
    logging.info("---- Processing Started ----")
except:
    logging.error("Aborted: Can only run one instance of this script")
    sys.exit(0)

# Regex for various tests
find_invoice = re.compile(r"(?!4)\d{6}", re.MULTILINE)
ignore_processed = re.compile(prefix + "_")

monitor_file_count = len(glob.glob(os.path.join(search_path,"*.pdf")))


def monitor_for_changes():
    """
    Checks the search_path for changes since
    :return:
        Boolean:Change Detected from initial startup
    """
    global monitor_file_count
    countdown = 4
    logging.info("Checking for file changes, Initial Count: %d" % monitor_file_count)
    change = False
    while countdown > 0:
        time.sleep(1)
        new_count = len(glob.glob(os.path.join(search_path,"*.pdf")))
        if monitor_file_count != new_count:
            logging.info("Change Detected, Old: %d New: %d" % (monitor_file_count, new_count))
            countdown = 4
            monitor_file_count = new_count
            change = True
        else:
            logging.info("Remaining: %d" % countdown)
            countdown -= 1

    return change


def process_files():
    for PDF_file in glob.glob(os.path.join(search_path,"*.pdf")):
        check_file = ignore_processed.search(PDF_file)
        if check_file:
            logging.info("Skip File: " + PDF_file)
            continue

        logging.info("Processing: " + PDF_file)

        # Ignore processing errors
        try:
            # More about suppressing Console:
            # https://stackoverflow.com/questions/52011902/python-pdf2image-hide-consoles
            img = convert_from_path(PDF_file, 500)[0]
        except:
            logging.info("Error Reading " + PDF_file)
            continue

        # Left, Top, Right, Bottom
        size = (
            int(img.width * 6 / 8.5),
            1,
            img.width - 1,
            int(img.height * 0.5 / 11)
        )
        crop_data = img.crop(size)

        # Recognize the text as string in image using pytesserct
        try:
            text = str((pytesseract.image_to_string(crop_data)))
        except:
            text = ""

        # strip certain newlines
        text = text.replace('-\n', '')

        result = find_invoice.search(text)

        if result:
            new_filename = os.path.join(search_path, prefix + "_" + result[0] + "_from_"+ os.path.basename(PDF_file))
            logging.info("New File: " + new_filename)
            # crop_data.save(new_filename + ".jpg", "JPEG")
            shutil.move(PDF_file, new_filename)
        else:
            bad_filename = os.path.join(search_path, prefix + "_Unknown_from_" + os.path.basename(PDF_file))
            logging.info("Bad File: " + bad_filename)
            logging.info("Found Text: '%s'" % text)
            # crop_data.save(bad_filename + ".jpg", "JPEG")
            shutil.move(PDF_file,bad_filename)


monitor_for_changes()
process_files()
while monitor_for_changes():
    process_files()

logging.info("---- Processing Complete ----")