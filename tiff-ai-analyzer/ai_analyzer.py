from openai import OpenAI
import httpx
from PIL import Image
import base64
import io
from xml.etree import ElementTree as ET
from config import OPENAI_API_KEY, MAX_IMAGE_SIZE

class AIAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client())
        
    def analyze_image(self, image_path, existing_metadata=None):
        try:
            # Open and resize image
            with Image.open(image_path) as img:
                img.thumbnail(MAX_IMAGE_SIZE)
                
                # Convert to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Build prompt with existing metadata context
            context = ""
            if existing_metadata:
                def _normalize_list(val):
                    if not val:
                        return []
                    if isinstance(val, str):
                        return [p.strip() for p in val.split(',') if p.strip()]
                    # Try to iterate/flatten common containers
                    try:
                        result = []
                        for item in val:
                            if item is None:
                                continue
                            if isinstance(item, str):
                                parts = [p.strip() for p in item.split(',') if p.strip()]
                                result.extend(parts)
                            elif isinstance(item, (list, tuple, set)):
                                for sub in item:
                                    if sub is None:
                                        continue
                                    if isinstance(sub, str):
                                        parts = [p.strip() for p in sub.split(',') if p.strip()]
                                        result.extend(parts)
                                    else:
                                        result.append(str(sub))
                            elif isinstance(item, dict):
                                # Attempt to pick a representative value
                                for v in item.values():
                                    if v is None:
                                        continue
                                    if isinstance(v, str):
                                        parts = [p.strip() for p in v.split(',') if p.strip()]
                                        result.extend(parts)
                                    else:
                                        result.append(str(v))
                            else:
                                result.append(str(item))
                        return result
                    except TypeError:
                        s = str(val).strip()
                        return [s] if s else []

                def _gather_context(meta):
                    kw_set = set()
                    people_set = set()

                    def _add(val, target_set):
                        for v in _normalize_list(val):
                            if v:
                                target_set.add(v)

                    # Common keyword keys
                    for k in ('keywords', 'tags', 'subject', 'subjects', 'dc:subject', 'Keywords'):
                        if k in meta:
                            _add(meta.get(k), kw_set)

                    # Common people keys
                    for k in ('people', 'persons', 'faces', 'Persons', 'PersonsInImage', 'microsoft_people', 'PeopleNames'):
                        if k in meta:
                            _add(meta.get(k), people_set)

                    # Lightroom hierarchical subjects (e.g., "People|Alice Smith|Family")
                    for k in ('lr:hierarchicalSubject', 'hierarchicalSubject'):
                        if k in meta:
                            for entry in _normalize_list(meta.get(k)):
                                parts = [p for p in str(entry).split('|') if p]
                                if parts:
                                    # Treat leaf as a keyword
                                    kw_set.add(parts[-1])
                                    # If under People|..., extract names as people
                                    if parts[0].lower() == 'people' and len(parts) >= 2:
                                        for name in parts[1:]:
                                            people_set.add(name)

                    # Also scan a nested "info" dict for loose keys
                    info = meta.get('info')
                    if isinstance(info, dict):
                        for k, v in info.items():
                            lk = str(k).lower()
                            if 'subject' in lk or 'keyword' in lk or 'tags' in lk:
                                _add(v, kw_set)
                            if 'people' in lk or 'person' in lk or 'faces' in lk:
                                _add(v, people_set)

                    # Return as sorted lists for stable output
                    return sorted(kw_set), sorted(people_set)

                keywords, people = _gather_context(existing_metadata)

                # Try to extract face regions (names and normalized locations) from embedded XMP
                def _extract_people_regions_from_xmp(xmp_str):
                    try:
                        xml_str = xmp_str.decode('utf-8', errors='ignore') if isinstance(xmp_str, (bytes, bytearray)) else str(xmp_str)
                        root = ET.fromstring(xml_str)
                        NS = {
                            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                            'mwg-rs': 'http://www.metadataworkinggroup.org/schemas/regions/',
                            'stArea': 'http://ns.adobe.com/xmp/sType/Area#'
                        }
                        regions = []
                        for desc in root.findall('.//rdf:li/rdf:Description', NS):
                            typ = desc.get('{http://www.metadataworkinggroup.org/schemas/regions/}Type')
                            name = desc.get('{http://www.metadataworkinggroup.org/schemas/regions/}Name')
                            if (typ and typ.lower() == 'face') or name:
                                area = desc.find('mwg-rs:Area', NS)
                                if area is not None:
                                    def _getf(attr):
                                        v = area.get(f'{{{NS["stArea"]}}}{attr}')
                                        try:
                                            return float(v) if v is not None else None
                                        except Exception:
                                            return None
                                    regions.append({
                                        'name': name or '',
                                        'x': _getf('x'),
                                        'y': _getf('y'),
                                        'w': _getf('w'),
                                        'h': _getf('h'),
                                        'rotation': desc.get('{http://www.metadataworkinggroup.org/schemas/regions/}Rotation')
                                    })
                        return regions
                    except Exception:
                        return []

                face_regions = []
                xmp_src = existing_metadata.get('xmp_xml')
                if xmp_src is None:
                    info = existing_metadata.get('info')
                    if isinstance(info, dict):
                        for k in ('XML:com.adobe.xmp', 'xmp', 'XMP'):
                            val = info.get(k)
                            if val:
                                xmp_src = val
                                break
                if xmp_src:
                    face_regions = _extract_people_regions_from_xmp(xmp_src)
                    for r in face_regions:
                        if r.get('name'):
                            people.append(r['name'])

                # Build context strings
                if people:
                    context += f"Known people in image: {', '.join(sorted(set(people)))}. "
                if keywords:
                    context += f"Existing keywords: {', '.join(keywords)}. "
                if face_regions:
                    locs = []
                    for r in face_regions:
                        nm = r.get('name') or 'Unknown'
                        locs.append(f"{nm}(x={r.get('x')}, y={r.get('y')}, w={r.get('w')}, h={r.get('h')})")
                    context += "Face regions (normalized 0-1): " + "; ".join(locs) + ". "
                if context:
                    print("Context for image analysis:")
                    print(context)
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{context}Analyze this image. If tags or names are provided, incorporate them into the description when applicable. Provide: 1) A brief description, 2) Keywords for Lightroom (comma-separated), 3) Any people or faces visible. Format as JSON with keys: description, keywords, people"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ]
            )
            
            # Parse response
            import json
            result_text = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to text parsing
            try:
                result = json.loads(result_text)
            except:
                # Fallback: create structured data from text
                result = {
                    'description': result_text,
                    'keywords': [],
                    'people': []
                }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing image: {e}")
            return {}
