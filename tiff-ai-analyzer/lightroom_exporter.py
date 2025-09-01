from xml.dom import minidom
from PIL import Image
from PIL.ExifTags import TAGS

class LightroomExporter:
    def __init__(self):
        pass
        
    def write_metadata(self, image_path, metadata):
        try:
            # For now, create an XMP sidecar file
            xmp_path = image_path.replace('.tif', '.xmp').replace('.tiff', '.xmp')
            
            # Pretty-print embedded XMP XML (if present)
            xmp_src = None
            if isinstance(metadata, dict):
                xmp_src = metadata.get('xmp_xml')
                if xmp_src is None:
                    info = metadata.get('info')
                    if isinstance(info, dict):
                        # Try some common keys PIL may use
                        for k in ('XML:com.adobe.xmp', 'xmp', 'XMP'):
                            val = info.get(k)
                            if val:
                                xmp_src = val.decode('utf-8', errors='ignore') if isinstance(val, (bytes, bytearray)) else str(val)
                                break
            if xmp_src:
                try:
                    dom = minidom.parseString(xmp_src if isinstance(xmp_src, (bytes, bytearray)) else xmp_src.encode('utf-8'))
                    pretty_xml = dom.toprettyxml(indent="  ").decode('utf-8') if isinstance(pretty_xml := dom.toprettyxml(indent="  "), (bytes, bytearray)) else pretty_xml
                    print("Embedded XMP (pretty):")
                    print(pretty_xml)
                except Exception as e:
                    print(f"Failed to parse embedded XMP. Raw XML follows:\n{xmp_src}")
            
            # Build XMP content
            xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        <rdf:Description rdf:about=""
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
'''
            
            # Add description
            if 'description' in metadata:
                xmp_content += f'''            <dc:description>
                <rdf:Alt>
                    <rdf:li xml:lang="x-default">{metadata['description']}</rdf:li>
                </rdf:Alt>
            </dc:description>
'''
            
            # Add keywords
            if 'keywords' in metadata:
                xmp_content += '''            <dc:subject>
                <rdf:Bag>
'''
                for keyword in metadata['keywords']:
                    xmp_content += f'                    <rdf:li>{keyword}</rdf:li>\n'
                xmp_content += '''                </rdf:Bag>
            </dc:subject>
'''
            
            xmp_content += '''        </rdf:Description>
    </rdf:RDF>
</x:xmpmeta>'''
            
            # Write XMP file
            with open(xmp_path, 'w') as f:
                f.write(xmp_content)
            
            print(f"Metadata written to: {xmp_path}")
            
        except Exception as e:
            print(f"Error writing metadata: {e}")
