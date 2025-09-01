from xml.dom import minidom
from xml.sax.saxutils import escape
import os

class LightroomExporter:
    def __init__(self):
        pass
        
    def write_metadata(self, image_path, metadata):
        try:
            # For now, create an XMP sidecar file
            root, _ = os.path.splitext(image_path)
            xmp_path = f"{root}.xmp"
            
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
                    xml_str = xmp_src.decode('utf-8', errors='ignore') if isinstance(xmp_src, (bytes, bytearray)) else str(xmp_src)
                    dom = minidom.parseString(xml_str)
                    pretty_xml = dom.toprettyxml(indent="  ")
                    print("Embedded XMP (pretty):")
                    print(pretty_xml)
                except Exception:
                    print("Failed to parse embedded XMP; skipping raw output.")
            
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
                desc = escape(str(metadata['description']))
                xmp_content += f'''            <dc:description>
                <rdf:Alt>
                    <rdf:li xml:lang="x-default">{desc}</rdf:li>
                </rdf:Alt>
            </dc:description>
'''
            
            # Add keywords
            if 'keywords' in metadata:
                xmp_content += '''            <dc:subject>
                <rdf:Bag>
'''
                for keyword in metadata['keywords']:
                    xmp_content += f'                    <rdf:li>{escape(str(keyword))}</rdf:li>\n'
                xmp_content += '''                </rdf:Bag>
            </dc:subject>
'''
            
            xmp_content += '''        </rdf:Description>
    </rdf:RDF>
</x:xmpmeta>'''
            
            # Pretty print and write XMP file
            try:
                dom_out = minidom.parseString(xmp_content)
                pretty_out = dom_out.toprettyxml(indent="  ")
                print("Exported XMP (pretty):")
                print(pretty_out)
            except Exception:
                pretty_out = xmp_content

            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(pretty_out)
            
            print(f"Metadata written to: {xmp_path}")
            
        except Exception as e:
            print(f"Error writing metadata: {e}")
