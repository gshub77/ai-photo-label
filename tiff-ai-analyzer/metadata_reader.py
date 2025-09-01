from PIL import Image
from PIL.ExifTags import TAGS
import exifread

class MetadataReader:
    def __init__(self, file_path):
        self.file_path = file_path
        
    def extract_metadata(self):
        metadata = {}
        
        try:
            # Read with PIL for basic EXIF
            with Image.open(self.file_path) as img:
                exifdata = img.getexif()
                
                if exifdata:
                    for tag_id, value in exifdata.items():
                        tag = TAGS.get(tag_id, tag_id)
                        metadata[tag] = value
                
                # Get IPTC info if available
                if hasattr(img, 'info'):
                    metadata['info'] = img.info
            
            # Read with exifread for more detailed EXIF
            with open(self.file_path, 'rb') as f:
                tags = exifread.process_file(f)
                for tag, value in tags.items():
                    metadata[f'EXIF_{tag}'] = str(value)
                    
        except Exception as e:
            print(f"Error reading metadata: {e}")
            
        return metadata
