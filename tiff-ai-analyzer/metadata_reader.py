from PIL import Image
from PIL.ExifTags import TAGS
import exifread

class MetadataReader:
    def __init__(self, file_path):
        self.file_path = file_path
        
    def extract_metadata(self):
        # Extract EXIF, IPTC, and XMP data
        # Return dictionary with existing tags, people names, keywords
        pass
