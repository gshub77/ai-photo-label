from PIL import Image
from PIL.ExifTags import TAGS
import exifread
import xml.etree.ElementTree as ET

class MetadataReader:
    def __init__(self, file_path):
        self.file_path = file_path
        
    def parse_xmp_tags(self, xmp_text):
        """Parses XMP metadata to extract tags from <lr:weightedFlatSubject>."""
        try:
            root = ET.fromstring(xmp_text)
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'lr': 'http://ns.adobe.com/lightroom/1.0/'
            }
            tags = root.find(".//lr:weightedFlatSubject/rdf:Bag", namespaces)
            if tags is not None:
                return [li.text for li in tags.findall("rdf:li", namespaces)]
        except ET.ParseError as e:
            print(f"Error parsing XMP: {e}")
        return []

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
            
        # Extract embedded XMP packet (XML) from TIFF bytes
        try:
            with open(self.file_path, 'rb') as fh:
                blob = fh.read()
            start = blob.find(b'<x:xmpmeta')
            if start != -1:
                end = blob.find(b'</x:xmpmeta>', start)
                if end != -1:
                    end += len(b'</x:xmpmeta>')
                    xmp_text = blob[start:end].decode('utf-8', errors='replace')
                    metadata['xmp_xml'] = xmp_text

                    # Parse tags from XMP
                    metadata['tags'] = self.parse_xmp_tags(xmp_text)

                    # Print extracted tags
                    print(f"Extracted tags: {', '.join(metadata['tags'])}")
        except Exception as xe:
            print(f"Error extracting XMP: {xe}")

        return metadata
