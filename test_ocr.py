import os
import django

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OCR.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

from ocr_engine.services.document_ocr_service import run_document_ocr

img_path = r'd:\Học\Năm 4 - 2025 - 2026\HK2\TGMT\Project\OCR_APP\OCR\media\uploads\2026\05\23\dl.jpg'

print("Starting OCR test on dl.jpg...")
try:
    res = run_document_ocr(img_path, enhance_contrast=True, denoise=True, binarize=True)
    
    print("\n" + "="*50)
    print("SUCCESSFULLY EXECUTED OCR")
    print("="*50)
    print("Raw text length:", len(res['raw_text']))
    print("Line count:", res.get('line_count'))
    print("Expert features count:", len(res.get('expert_features', [])))
    
    with open('raw_text.txt', 'w', encoding='utf-8') as f:
        f.write(res['raw_text'])
    print("Saved raw text to raw_text.txt")
    
    import json
    with open('expert_features.json', 'w', encoding='utf-8') as f:
        json.dump(res.get('expert_features', []), f, indent=4, ensure_ascii=False)
    print("Saved expert features to expert_features.json")
    
    if res.get('expert_features'):
        print("Expert features saved successfully.")
except Exception as e:
    print("\n" + "="*50)
    print("ERROR OCCURRED:")
    print("="*50)
    import traceback
    traceback.print_exc()
