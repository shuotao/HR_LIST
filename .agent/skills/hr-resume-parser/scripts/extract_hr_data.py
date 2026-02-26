import os
import csv
import re
import unicodedata

def normalize_text(text):
    # Convert Kangxi Radicals and other variants to standard CJK characters
    return unicodedata.normalize('NFKC', text)

def extract_from_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
    except Exception:
        return ["Error", "", "", "", "", ""]

    content = normalize_text(raw_content)
    # Clean up page breaks and extra carriage returns
    content = content.replace('\x0c', '\n').replace('\r', '\n')
    lines = [l.strip() for l in content.split('\n')]
    
    name = ""
    age = ""
    education = ""
    recent_work = ""
    seniority = ""
    companies = []

    # 1. Name & Age
    for line in lines:
        if "歲" in line and ("男" in line or "女" in line):
            m = re.search(r'^([^\s\d]+?)\s+(\d+)歲', line)
            if m:
                name = m.group(1).strip()
                age = m.group(2).strip()
                break
            else:
                m2 = re.search(r'(\d+)歲', line)
                if m2:
                    age = m2.group(1)
                    name = line.split(age)[0].strip()
                    break

    # Extract Blocks helper
    def get_block(start_kw, stop_kws):
        start_idx = -1
        for i, l in enumerate(lines):
            # removing spaces to match strictly
            if start_kw in l.replace(" ", "") and len(l) < 20: 
                start_idx = i
                break
        
        if start_idx == -1: return ""
        
        block_lines = []
        for j in range(start_idx + 1, len(lines)):
            l = lines[j]
            if not l: continue
            if any(stop in l.replace(" ", "") for stop in stop_kws):
                break
            block_lines.append(l)
            
        return " ".join(block_lines).strip()

    # 2. Education
    education = get_block("最高學歷", ["希望職稱", "最近工作", "總年資", "居住地", "代碼"])

    # 3. Recent Work
    recent_work = get_block("最近工作", ["居住地", "E-mail", "聯絡電話", "更新日", "工作經歷", "Email"])

    # 4. Total Seniority
    seniority_block = get_block("總年資", ["最近工作", "居住地", "電機裝修", "代碼", "工作經歷"])
    if seniority_block:
        num_m = re.search(r'(\d+)', seniority_block)
        if num_m:
            seniority = num_m.group(1)
            
    # Fallback for seniority if it wasn't caught due to block limits
    if not seniority:
        for i, l in enumerate(lines):
            if "總年資" in l.replace(" ", ""):
                for j in range(i+1, min(i+4, len(lines))):
                    num = re.search(r'(\d+)', lines[j])
                    if num:
                        seniority = num.group(1)
                        break
                if seniority: break

    # 5. Work History for Previous 2 Companies
    exp_idx = -1
    for i, l in enumerate(lines):
        if "工作經歷" in l.replace(" ", ""):
            exp_idx = i
            break
            
    if exp_idx != -1:
        for j in range(exp_idx + 1, len(lines)):
            l = lines[j]
            # Match company and date, e.g. "公司名稱 職稱 2020/01~"
            if re.search(r'\d{4}/\d{2}~', l):
                parts = l.split()
                if parts:
                    cname = parts[0].strip()
                    if cname and cname not in companies and not any(x in cname for x in ["總年資", "更新日", "代碼"]):
                        companies.append(cname)
                        
    # The first company is usually the recent one. We need the previous 2 (index 1 and 2)
    prev_companies = "、".join(companies[1:3]) if len(companies) > 1 else ""

    # Last resort fallback name from filename
    if not name:
        name = os.path.splitext(os.path.basename(file_path))[0]

    return [name, age, education, recent_work, seniority, prev_companies]

def process_all():
    base_dir = r"c:\Users\01102088\Desktop\HRMD"
    md_files = sorted([f for f in os.listdir(base_dir) if f.lower().endswith('.md') and not f.startswith('README') and f != 'GEMINI.md'])
    
    data = []
    header = ['姓名', '年紀', '學歷', '近期工作', '總年資', '前二次任職公司']
    
    for f in md_files:
        row = extract_from_md(os.path.join(base_dir, f))
        data.append(row)
        
    csv_path = os.path.join(base_dir, 'HR_Data_Summary.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        writer.writerows(data)
        
    print(f"Processed {len(data)} files successfully. Output: HR_Data_Summary.csv")

    # === 新增：程式自動防幻覺雙重檢驗 ===
    import random
    print("\n--- 🤖 Python 自動防幻覺檢驗程序啟動 (零 Token 消耗) ---")
    indices = list(range(len(data)))
    sample_indices = random.sample(indices, min(5, len(data)))
    
    for idx in sample_indices:
        md_file = md_files[idx]
        name, age, edu, work, senior, prev = data[idx]
        
        md_path = os.path.join(base_dir, md_file)
        try:
            with open(md_path, 'r', encoding='utf-8') as f_read:
                # Same normalization applied for checking
                raw_text = unicodedata.normalize('NFKC', f_read.read()).replace('\x0c', '\n').replace('\r', '\n')
            
            # Simple inclusion check. To prevent empty string matching issues, we check if truthy
            name_ok = (name in raw_text) if name else False
            age_ok = (age in raw_text) if age else False
            
            print(f"📌 抽檢檔案: {md_file}")
            print(f"  ✓ 擷取姓名: {name} (原檔比對: {'通過' if name_ok else '未通過'})")
            print(f"  ✓ 擷取年紀: {age} (原檔比對: {'通過' if age_ok else '未通過'})")
        except Exception as e:
            print(f"📌 抽檢檔案: {md_file} 讀檔比對失敗 ({e})")
    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    process_all()
