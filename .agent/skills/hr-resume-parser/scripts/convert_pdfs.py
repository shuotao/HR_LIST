import os
import sys
import io
from markitdown import MarkItDown

# Ensure UTF-8 output on Windows terminals (prevents cp950 UnicodeEncodeError)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    base_dir = r"c:\Users\01102088\Desktop\HRMD"
    pdf_files = [f for f in os.listdir(base_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found to convert.")
        return

    md_converter = MarkItDown()
    
    for pdf in pdf_files:
        pdf_path = os.path.join(base_dir, pdf)
        md_path = os.path.join(base_dir, os.path.splitext(pdf)[0] + '.md')
        
        # 冪等設計：若 .md 已存在且有內容（>10 bytes），跳過不重複轉換。
        # 若需強制重轉，先手動刪除對應的 .md 檔案。
        if os.path.exists(md_path) and os.path.getsize(md_path) > 10:
            continue
            
        print(f"Converting {pdf} to Markdown using Python API...")
        try:
            result = md_converter.convert(pdf_path)
            with open(md_path, 'w', encoding='utf-8') as f_out:
                f_out.write(result.text_content)
        except Exception as e:
            print(f"Error converting {pdf}: {e}")
            sys.exit(1) # Fail fast according to Halt on Error rules

    print(f"All {len(pdf_files)} PDF conversions complete.")

if __name__ == "__main__":
    main()
