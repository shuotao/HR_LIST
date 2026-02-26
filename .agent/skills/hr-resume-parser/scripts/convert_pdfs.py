import os
import sys
from markitdown import MarkItDown

def main():
    base_dir = r"c:\Users\01102088\Desktop\HRMD"
    pdf_files = [f for f in os.listdir(base_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found to convert.")
        return

    md_converter = MarkItDown()
    
    for pdf in pdf_files:
        pdf_path = os.path.join(base_dir, pdf)
        md_path = os.path.join(base_dir, pdf.replace('.pdf', '.md'))
        
        # skip if already exists and has content
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
