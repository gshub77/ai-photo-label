from openai import OpenAI
import httpx
from PIL import Image
import base64
import io
import re
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
                    for k in ('people', 'persons', 'faces', 'Persons', 'PersonsInImage', 'RegionList', 'Name'):
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
                print('DEBUG: Extracted keywords:', keywords)
                print('DEBUG: Extracted people from metadata:', people)

                # Try to extract face regions (names and normalized locations) from embedded XMP
                def _extract_people_regions_from_xmp(xmp_str):
                    try:
                        xml_str = xmp_str.decode('utf-8', errors='ignore') if isinstance(xmp_str, (bytes, bytearray)) else str(xmp_str)
                        # Strip XMP packet PIs and BOM if present
                        xml_str = xml_str.lstrip('\ufeff')
                        xml_str = re.sub(r'<\?xpacket[^>]*\?>', '', xml_str, flags=re.IGNORECASE)
                        root = ET.fromstring(xml_str)

                        # Helpers to ignore namespaces by matching local tag/attr names
                        def _has_local_tag(el, local):
                            t = el.tag
                            return isinstance(t, str) and (t.endswith('}' + local) or t == local)

                        def _get_local_attr(attrs, local):
                            for k, v in attrs.items():
                                if isinstance(k, str) and (k.endswith('}' + local) or k == local):
                                    return v
                            return None

                        regions = []

                        # Iterate any Description elements that contain an Area child
                        for desc in root.iter():
                            if not _has_local_tag(desc, 'Description'):
                                continue

                            # Find Area child (namespace-agnostic)
                            area = None
                            for child in desc:
                                if _has_local_tag(child, 'Area'):
                                    area = child
                                    break
                            if area is None:
                                continue

                            typ = _get_local_attr(desc.attrib, 'Type')
                            name = _get_local_attr(desc.attrib, 'Name')
                            rotation_raw = _get_local_attr(desc.attrib, 'Rotation')
                            try:
                                rotation_val = float(rotation_raw) if rotation_raw is not None else None
                            except Exception:
                                rotation_val = None

                            def _getf(attr):
                                val = _get_local_attr(area.attrib, attr)
                                try:
                                    return float(val) if val is not None else None
                                except Exception:
                                    return None

                            region = {
                                'name': name or '',
                                'x': _getf('x'),
                                'y': _getf('y'),
                                'w': _getf('w'),
                                'h': _getf('h'),
                                'rotation': rotation_val
                            }

                            # Include entries that look like regions: have area coords or name/type hints
                            if any(region[k] is not None for k in ('x', 'y', 'w', 'h')) or name or (typ and str(typ).lower() == 'face'):
                                print('DEBUG: Found region (namespace-agnostic):', region)
                                regions.append(region)

                        return regions
                    except Exception as e:
                        print('DEBUG: Exception in _extract_people_regions_from_xmp:', e)
                        return []

                face_regions = []
                # Try several likely locations for embedded XMP
                xmp_src = (
                    existing_metadata.get('xmp_xml')
                    or existing_metadata.get('xmp')
                    or existing_metadata.get('XMP')
                    or existing_metadata.get('XMLPacket')
                    or existing_metadata.get('XML:com.adobe.xmp')
                    or existing_metadata.get('embedded_xmp')
                    or existing_metadata.get('raw_xmp')
                )
                if xmp_src is None:
                    info = existing_metadata.get('info')
                    if isinstance(info, dict):
                        for k in (
                            'XML:com.adobe.xmp',
                            'XMLPacket',
                            'xmp',
                            'XMP',
                            'xmp_xml',
                            'raw_xmp',
                            'embedded_xmp'
                        ):
                            val = info.get(k)
                            if val:
                                xmp_src = val
                                break
                if xmp_src:
                    face_regions = _extract_people_regions_from_xmp(xmp_src)
                    print('DEBUG: Extracted face regions from XMP:', face_regions)
                    for r in face_regions:
                        nm = r.get('name')
                        if nm:
                            people.append(nm)

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
                    print("DEBUG: Final context for image analysis:\n", context)
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{context}Analyze this image. If tags or names are provided, incorporate them into the description when applicable. Provide: 1) A brief description, 2) Keywords for Lightroom (comma-separated), 3) Any people or faces visible, use the location data being provided to confirm the person and refer to them by the name provided. Format as JSON with keys: description, keywords, people"
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
