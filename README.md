# PDF Scanner
A low-tech "Zone OCR" implementation using Python, Google Tesseract OCR, and Poppler

This solution is intended to be used with a folder monitoring script such as [Folder Monitor](https://www.nodesoft.com/foldermonitor) or Facebook's [Watchman](https://facebook.github.io/watchman/).  The `scanner.pyw` script should be launched when PDF files are created in the watch folder. 

## Installing
* Python 3.x
* [Tesseract OCR](https://tesseract-ocr.github.io/) - Latest Version
* [Poppler](https://poppler.freedesktop.org/) - Latest Version
* `pip install -r requirements.txt`

## Command Line
`scanner.pyw <Path to Convert> <prefix>`

**Path to Convert** - Scans this folder for pdf files  
**Prefix** - Ignores files which start with this prefix

## Modification
You will need to edit the `size` variable to change the area which is scanned.
