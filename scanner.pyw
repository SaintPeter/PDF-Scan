import os
import re
import cv2
import sys
import glob
import time
import shutil
import logging
import numpy as np
from PIL import Image
import pytesseract
import multiprocessing
import dateutil.parser as parser
from dateutil.parser import ParserError
from pdf2image import convert_from_path

# Check Command Line options
if len(sys.argv) >= 3:
    search_path = sys.argv[1]
    prefix = sys.argv[2]
    debug = len(sys.argv) == 4 and sys.argv[3] == 'debug'
else:
    print("Invalid number of parameters, 2 required")
    print("Params: ")
    print(sys.argv)
    sys.exit(1)

# Regex for various tests
find_invoice = re.compile(r"(?!4)\d{6}", re.MULTILINE)
ignore_processed = re.compile(prefix + "_|Error_")
invoice_filename_test = re.compile(r"^\d{5,}")
date_test = re.compile(r"\d+/\d+/\d+")

logging.basicConfig(
    filename='pdf_scanner_log_' + prefix + '.txt',
    level=logging.DEBUG,
    format='%(asctime)s %(message)s',
    datefmt='[%m/%d/%Y %I:%M:%S %p]')


# From https://stackoverflow.com/a/65634189/1420506
def convert_from_cv2_to_image(img: np.ndarray) -> Image:
    # return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    return Image.fromarray(img)


# From https://stackoverflow.com/a/65634189/1420506
def convert_from_image_to_cv2(img: Image) -> np.ndarray:
    # return cv2.cvtColor(numpy.array(img), cv2.COLOR_RGB2BGR)
    return np.asarray(img)


def image_clean_for_ocr(img: Image):
    """
    Takes an image and applies a blur, then threshold to get a better image for OCR
    :param img: PIL Image to Clean
    :return: PIL Cleaned Image
    """
    cv_img = convert_from_image_to_cv2(img)
    cv2.medianBlur(cv_img, 5, cv_img)
    cv2.threshold(cv_img, 140, 255, cv2.THRESH_BINARY, cv_img)
    return convert_from_cv2_to_image(cv_img)


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
        new_count = len(glob.glob(os.path.join(search_path, "*.pdf")))
        if monitor_file_count != new_count:
            logging.info("Change Detected, Old: %d New: %d" % (monitor_file_count, new_count))
            countdown = 4
            monitor_file_count = new_count
            change = True
        else:
            logging.info("Remaining: %d" % countdown)
            countdown -= 1

    return change


def read_pdf_to_img_on_queue(PDF_file, outputQueue: multiprocessing.Queue):
    """
    Reads a PDF specified by PDF_File and pushes the resulting image data onto the output queue
    :param PDF_file:string Full path and filename of file to process
    :param outputQueue:multiprocessing.Queue Queue to hold returned image data
    """
    # Ignore processing errors
    try:
        # More about suppressing Console:
        # https://stackoverflow.com/questions/52011902/python-pdf2image-hide-consoles
        img = convert_from_path(PDF_file, 500, last_page=1)[0]
        outputQueue.put(img)
    except:
        logging.info("Error Reading " + PDF_file)
        pass


def process_files():
    for PDF_file in glob.glob(os.path.join(search_path, "*.pdf")):
        check_file = ignore_processed.search(PDF_file)
        if check_file:
            logging.info("Skip File: " + PDF_file)
            continue

        logging.info("Processing: " + PDF_file)

        if prefix in ['Job', 'Estimate', 'Timesheet']:
            # Start the conversion as a process
            outputQueue = multiprocessing.Queue()
            process = multiprocessing.Process(target=read_pdf_to_img_on_queue, args=(PDF_file, outputQueue))
            process.start()

            # Wait up to 20 seconds to finish
            start_time = time.time()
            while outputQueue.empty() and (time.time() - start_time < 20):
                delta = time.time() - start_time
                time.sleep(1)

            # If the queue is empty then we've timed out or errored out
            if outputQueue.empty():
                # Kill the process
                process.terminate()
                bad_filename = os.path.join(search_path, "Error_" + os.path.basename(PDF_file))
                logging.info("Timeout File: " + bad_filename)
                print(bad_filename)
                shutil.move(PDF_file, bad_filename)
                continue
            else:
                img = outputQueue.get()

            # --------------------------- Job / Estimate Parse ----------------------
            if prefix in ['Job', 'Estimate']:
                # Left, Top, Right, Bottom
                invoice_size = (
                    int(img.width * 6 / 8.5),
                    1,
                    img.width - 1,
                    int(img.height * 0.5 / 11)
                )
                invoice_crop_data = img.crop(invoice_size)

                # Recognize the text as string in image using pytesserct
                try:
                    text = str((pytesseract.image_to_string(invoice_crop_data)))
                except:
                    text = ""

                # strip certain newlines
                text = text.replace('-\n', '')

                result = find_invoice.search(text)

                if result:
                    new_filename = os.path.join(search_path,
                                                prefix + "_" + result[0] + "_from_" + os.path.basename(PDF_file))
                    logging.info("New File: " + new_filename)
                    # crop_data.save(new_filename + ".jpg", "JPEG")
                    shutil.move(PDF_file, new_filename)
                else:
                    bad_filename = os.path.join(search_path, prefix + "_Unknown_from_" + os.path.basename(PDF_file))
                    logging.info("Bad File: " + bad_filename)
                    logging.info("Found Text: '%s'" % text)
                    # crop_data.save(bad_filename + ".jpg", "JPEG")
                    shutil.move(PDF_file, bad_filename)
            else:
                # ---------------------------- Timesheet Parse ------------------------

                # Invoice Number
                # Left, Top, Right, Bottom
                invoice_size = (
                    int(img.width * 0.5 / 11),
                    int(img.height * (1 + 3 / 8) / 8.5),
                    int(img.width * 1.5 / 11),
                    int(img.height * (1 + 3 / 4) / 8.5)
                )
                invoice_crop_data = img.crop(invoice_size)

                # Clean Image
                invoice_crop_data = image_clean_for_ocr(invoice_crop_data)

                # Recognize the text as string in image using pytesserct
                try:
                    invoice_number = str((pytesseract.image_to_string(invoice_crop_data)))
                except:
                    invoice_number = ""

                # strip certain newlines
                invoice_number = invoice_number.replace('-\n', '')

                invoice = find_invoice.search(invoice_number)

                # Date
                # Left, Top, Right, Bottom
                date_size = (
                    int(img.width * (1 + 5 / 8) / 11),
                    int(img.height * (1 + 3 / 8) / 8.5),
                    int(img.width * (2 + 7 / 8) / 11),
                    int(img.height * (1 + 3 / 4) / 8.5)
                )
                date_crop_data = img.crop(date_size)

                # Clean up Image
                date_crop_data = image_clean_for_ocr(date_crop_data)

                # Recognize the text as string in image using pytesserct
                try:
                    date_text = str((pytesseract.image_to_string(date_crop_data)))
                except:
                    date_text = ""

                # strip certain newlines
                date_text = date_text.replace('-\n', '')

                try:
                    parsed_date = parser.parse(date_text)
                    invoice_date = parsed_date.strftime("%Y-%m-%d")
                except ParserError:
                    invoice_date = 'Unknown_Date'
                except OverflowError:
                    invoice_date = 'Unknown_Date'

                if invoice:
                    new_filename = os.path.join(search_path,
                                                "{0}_{1}_{2}_from_{3}".format(prefix, invoice[0], invoice_date,
                                                                              os.path.basename(PDF_file)))
                    logging.info("New File: " + new_filename)
                    if debug:
                        invoice_crop_data.save(new_filename + "_invoice.jpg", "JPEG")
                        date_crop_data.save(new_filename + "_date.jpg", "JPEG")

                    shutil.move(PDF_file, new_filename)
                else:
                    bad_filename = os.path.join(search_path,
                                                "{0}_Unknown_{1}_from_{2}".format(prefix, invoice_date,
                                                                                  os.path.basename(PDF_file)))
                    logging.info("Bad File: " + bad_filename)
                    logging.info("Found Text: '%s'" % invoice_number)
                    shutil.move(PDF_file, bad_filename)

                    if debug:
                        invoice_crop_data.save(bad_filename + "_invoice.jpg", "JPEG")
                        date_crop_data.save(bad_filename + "_date.jpg", "JPEG")
        elif prefix == 'Invoice':
            # ------------------------------------ Invoice Parse -------------------------
            # Scan Filename
            result = invoice_filename_test.search(os.path.basename(PDF_file))
            if result:
                new_filename = os.path.join(search_path,
                                            prefix + "_" + result[0] + "_from_" + os.path.basename(PDF_file))
                logging.info("New File: " + new_filename)
                shutil.move(PDF_file, new_filename)
            else:
                bad_filename = os.path.join(search_path, prefix + "_Unknown_from_" + os.path.basename(PDF_file))
                logging.info("Bad File: " + bad_filename)
                shutil.move(PDF_file, bad_filename)
        else:
            logging.error('Unrecognized Prefix')
            sys.exit(0)


if __name__ == '__main__':
    # Prevent multiple copies from running
    try:
        lock_file = os.open(prefix + ".lock", os.O_CREAT | os.O_EXCL | os.O_TEMPORARY)
        logging.info("---- Processing Started ----")
    except:
        # logging.error("Aborted: Can only run one instance of this script")
        sys.exit(0)

    monitor_file_count = len(glob.glob(os.path.join(search_path, "*.pdf")))

    monitor_for_changes()
    process_files()
    while monitor_for_changes():
        process_files()

    logging.info("---- Processing Complete ----")
