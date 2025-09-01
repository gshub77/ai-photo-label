import os
import sys
from metadata_reader import MetadataReader
from ai_analyzer import AIAnalyzer
from lightroom_exporter import LightroomExporter
from config import SUPPORTED_FORMATS

def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <path_to_tiff_file>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    # Validate file format
    if not any(file_path.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
        print(f"Unsupported file format. Supported formats: {SUPPORTED_FORMATS}")
        sys.exit(1)
        
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"Processing: {file_path}")
    
    # Extract existing metadata
    metadata_reader = MetadataReader(file_path)
    existing_metadata = metadata_reader.extract_metadata()
    if existing_metadata is None:
        existing_metadata = {}
    # print(f"Existing metadata: {existing_metadata}")
    
    # Analyze image with AI
    ai_analyzer = AIAnalyzer()
    ai_metadata = ai_analyzer.analyze_image(file_path)
    if ai_metadata is None:
        ai_metadata = {}
    print(f"AI metadata: {ai_metadata}")
    
    # Combine and write metadata
    lightroom_exporter = LightroomExporter()
    lightroom_exporter.write_metadata(file_path, {**existing_metadata, **ai_metadata})
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
