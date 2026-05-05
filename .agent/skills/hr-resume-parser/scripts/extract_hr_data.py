import os
import csv
import re
import sys
import io
import unicodedata

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def normalize_text(text):
    # Convert Kangxi Radicals and other variants to standard CJK characters
    return unicodedata.normalize('NFKC', text)

def extract_from_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
    except Exception:
        return ["Error", "", "", "", "", "", "", ""]

    content = normalize_text(raw_content)
    # Clean up page breaks and extra carriage returns
    content = content.replace('\x0c', '\n').replace('\r', '\n')
    lines = [l.strip() for l in content.split('\n')]
    
    name = ""
    age = ""
    education = ""
    recent_work = ""
    recent_work_desc = ""
    seniority = ""
    language_skills = ""
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

    # 通用區塊擷取工具：找到 start_kw 所在行，往下收集直到遇到 stop_kws 中任一關鍵字。
    # 若找不到 start_kw，回傳空字串（靜默失敗，不中斷處理）。
    def get_block(start_kw, stop_kws):
        start_idx = -1
        # Normalize search keyword
        start_kw_norm = normalize_text(start_kw).replace(" ", "")
        stop_kws_norm = [normalize_text(kw).replace(" ", "") for kw in stop_kws]

        for i, l in enumerate(lines):
            # removing spaces to match strictly
            # and normalizing line to catch variations
            l_norm = normalize_text(l).replace(" ", "")
            if start_kw_norm in l_norm and len(l) < 20: 
                start_idx = i
                break
        
        if start_idx == -1: return ""
        
        block_lines = []
        for j in range(start_idx + 1, len(lines)):
            l = lines[j]
            if not l: continue
            l_norm = normalize_text(l).replace(" ", "")
            if any(stop in l_norm for stop in stop_kws_norm):
                break
            block_lines.append(l)
            
        return " ".join(block_lines).strip()

    # 2. Language Skills - Smart pairing to fix MarkItDown split-line issue
    # 已知語言白名單（104 系統常見語種）。不在此清單的語言會被靜默跳過。
    known_langs = ["中文", "英文", "台語", "日文", "粵語", "客家語", "印尼文",
                   "西班牙文", "泰文", "上海話", "韓文", "法文", "德文", "越南文"]
    lang_stop_kws = ["技能專長", "專長", "認證資格", "自傳", "求職條件", "附件", "最高學歷", "教育背景"]
    lang_stop_norms = [normalize_text(kw).replace(" ", "") for kw in lang_stop_kws]

    lang_start = -1
    for i, l in enumerate(lines):
        l_norm = normalize_text(l).replace(" ", "")
        if "語文能力" in l_norm and len(l) < 20:
            lang_start = i
            break

    if lang_start != -1:
        lang_lines = []
        for j in range(lang_start + 1, len(lines)):
            l = lines[j]
            if not l: continue
            l_norm = normalize_text(l).replace(" ", "")
            if any(stop in l_norm for stop in lang_stop_norms):
                break
            lang_lines.append(l.strip())

        # Classify each line
        languages_found = []
        proficiencies_found = []
        test_scores_found = []

        for line in lang_lines:
            # Check known language name
            if line in known_langs:
                languages_found.append(line)
            # Detailed proficiency: 聽/X、說/X、讀/X、寫/X
            elif re.match(r'聽/.+', line):
                proficiencies_found.append(line)
            # Simple proficiency word
            elif line in ["精通", "中等", "略懂", "不會"]:
                proficiencies_found.append(line)
            # Test scores (TOEIC, GEPT, etc.)
            elif any(kw in line for kw in ["TOEIC", "多益", "GEPT", "英檢"]):
                test_scores_found.append(line)

        # Simplify detailed proficiency if all 4 skills are the same level
        def simplify_prof(prof):
            if not prof.startswith("聽/"):
                return prof
            levels = re.findall(r'[聽說讀寫]/([^\s、]+)', prof)
            if levels and len(set(levels)) == 1:
                return levels[0]
            return prof

        # Pair languages with proficiencies positionally
        lang_prof_map = {}
        for i, lang in enumerate(languages_found):
            prof = proficiencies_found[i] if i < len(proficiencies_found) else ""
            if prof:
                prof = simplify_prof(prof)
            lang_prof_map[lang] = prof

        # Build output: English first with proficiency + test score, then others (name only)
        parts = []

        # English first
        if "英文" in lang_prof_map:
            eng_prof = lang_prof_map["英文"]
            eng_str = f"英文({eng_prof})" if eng_prof else "英文"
            if test_scores_found:
                eng_str += " " + " ".join(test_scores_found)
            parts.append(eng_str)

        # Other languages (no proficiency, just name)
        for lang in languages_found:
            if lang != "英文":
                parts.append(lang)

        language_skills = "、".join(parts) if parts else ""

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

    # 5. Work History for Previous 2 Companies & Recent Work Description
    exp_idx = -1
    for i, l in enumerate(lines):
        if "工作經歷" in l.replace(" ", ""):
            exp_idx = i
            break
            
    if exp_idx != -1:
        job_indices = []
        for j in range(exp_idx + 1, len(lines)):
            stop_kws = ["教育背景", "個⼈資料", "個人資料", "技能專長"]
            l_norm = normalize_text(lines[j]).replace(" ", "")
            if any(stop in l_norm for stop in stop_kws):
                break
            # Match company and date, e.g. "公司名稱 職稱 2020/01~"
            if re.search(r'\d{4}/\d{2}~', lines[j]):
                job_indices.append(j)
                parts = lines[j].split()
                if parts:
                    cname = parts[0].strip()
                    if cname and cname not in companies and not any(x in cname for x in ["總年資", "更新日", "代碼"]):
                        companies.append(cname)
                        
        if job_indices:
            start_idx = job_indices[0]
            end_idx = job_indices[1] if len(job_indices) > 1 else len(lines)
            desc_stop_kws = ["教育背景", "個人資料", "技能專長", "語文能力", "求職條件", "自傳"]
            desc_stop_norms = [normalize_text(kw).replace(" ", "") for kw in desc_stop_kws]

            desc_lines = []
            capturing = False
            for j in range(start_idx, end_idx):
                l_norm = normalize_text(lines[j]).replace(" ", "")
                if any(stop in l_norm for stop in desc_stop_norms):
                    break
                if "工作內容" in l_norm:
                    capturing = True
                    # Remove the prefix
                    first_line = lines[j]
                    for variant in ["工作內容", "⼯作內容"]:
                        first_line = first_line.replace(variant, "", 1).strip()
                    if first_line:
                        desc_lines.append(first_line)
                    continue
                if capturing and lines[j].strip():
                    desc_lines.append(lines[j].strip())
            recent_work_desc = " ".join(desc_lines).strip()

    # The first company is usually the recent one. We need the previous 2 (index 1 and 2)
    prev_companies = "、".join(companies[1:3]) if len(companies) > 1 else ""

    # Last resort fallback name from filename
    if not name:
        name = os.path.splitext(os.path.basename(file_path))[0]

    return [name, age, language_skills, education, recent_work, recent_work_desc, seniority, prev_companies]

def process_all():
    import random

    # 跨平台路徑解析（2026-04-30 新增）
    # - Windows：沿用使用者既有 HRMD 工作目錄（不變）
    # - macOS / Linux：從腳本位置往上推算專案根目錄
    #   scripts/ → hr-resume-parser/ → skills/ → .agent/ → 專案根
    if sys.platform == 'win32':
        base_dir = r"c:\Users\01102088\Desktop\HRMD"
    else:
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
        )

    # === 白名單邏輯：只處理有對應 .pdf 的 .md 檔案 ===
    pdf_set = {os.path.splitext(f)[0] for f in os.listdir(base_dir) if f.lower().endswith('.pdf')}
    md_files = sorted([
        f for f in os.listdir(base_dir)
        if f.lower().endswith('.md') and os.path.splitext(f)[0] in pdf_set
    ])

    data = []
    header = ['序號', '姓名', '年紀', '語文能力', '學歷', '近期工作', '近期工作內容', '總年資', '前二次任職公司']

    for f in md_files:
        row = extract_from_md(os.path.join(base_dir, f))
        data.append(row)

    # === 加入三位數序號 ===
    for i, row in enumerate(data):
        row.insert(0, f"{i+1:03d}")

    csv_path = os.path.join(base_dir, 'HR_Data_Summary.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        writer.writerows(data)

    print(f"Processed {len(data)} candidate files. Output: HR_Data_Summary.csv")

    # === 程式自動防幻覺檢驗（15 組）===
    print("\n--- 🤖 Python 自動防幻覺檢驗程序啟動 (零 Token 消耗) ---")
    indices = list(range(len(data)))
    sample_indices = random.sample(indices, min(15, len(data)))

    for idx in sample_indices:
        md_file = md_files[idx]
        seq, name, age = data[idx][0], data[idx][1], data[idx][2]

        md_path = os.path.join(base_dir, md_file)
        try:
            with open(md_path, 'r', encoding='utf-8') as f_read:
                raw_text = unicodedata.normalize('NFKC', f_read.read()).replace('\x0c', '\n').replace('\r', '\n')

            name_ok = (name in raw_text) if name else False
            age_ok = (age in raw_text) if age else False

            print(f"📌 抽檢 [{seq}] {md_file}")
            print(f"  ✓ 擷取姓名: {name} (原檔比對: {'通過' if name_ok else '未通過'})")
            print(f"  ✓ 擷取年紀: {age} (原檔比對: {'通過' if age_ok else '未通過'})")
        except Exception as e:
            print(f"📌 抽檢 [{seq}] {md_file} 讀檔比對失敗 ({e})")
    print("----------------------------------------------------------")

    # === PDF/MD 重新命名：加上序號前綴 ===
    print("\n--- 📂 PDF/MD 序號重新命名 ---")
    renamed_count = 0
    rename_map = []  # (seq, original_name, new_pdf, new_md)

    for i, md_file in enumerate(md_files):
        seq = data[i][0]
        base_name = os.path.splitext(md_file)[0]
        # 若檔名已有序號前綴（如 001_），跳過
        if re.match(r'^\d{3}_', base_name):
            rename_map.append((seq, base_name, base_name + '.pdf', md_file))
            continue

        new_base = f"{seq}_{base_name}"
        old_pdf = os.path.join(base_dir, base_name + '.pdf')
        new_pdf = os.path.join(base_dir, new_base + '.pdf')
        old_md = os.path.join(base_dir, md_file)
        new_md = os.path.join(base_dir, new_base + '.md')

        # 安全檢查：目標檔名不可已存在
        if os.path.exists(new_pdf) and old_pdf != new_pdf:
            print(f"  ❌ 錯誤：目標檔案已存在 {new_base}.pdf，中止改名")
            sys.exit(1)
        if os.path.exists(new_md) and old_md != new_md:
            print(f"  ❌ 錯誤：目標檔案已存在 {new_base}.md，中止改名")
            sys.exit(1)

        if os.path.exists(old_pdf):
            os.rename(old_pdf, new_pdf)
        if os.path.exists(old_md):
            os.rename(old_md, new_md)
        renamed_count += 1
        rename_map.append((seq, base_name, new_base + '.pdf', new_base + '.md'))

    print(f"  完成：{renamed_count} 組檔案已加上序號前綴")

    # === 改名後抽檢：確認外部檔名與 PDF 內部人名一致 ===
    print("\n--- 🔍 改名後抽檢（外部檔名 vs 內部人名）---")
    check_indices = random.sample(range(len(rename_map)), min(15, len(rename_map)))
    all_passed = True

    for idx in check_indices:
        seq, orig_name, new_pdf_name, new_md_name = rename_map[idx]
        csv_name = data[idx][1]  # 姓名欄位

        # 從新檔名解析出人名部分
        filename_name = re.sub(r'^\d{3}_', '', os.path.splitext(new_pdf_name)[0])

        # 比對：檔名人名 == CSV 人名
        match_ok = (filename_name == csv_name)

        status = "✅ 通過" if match_ok else "❌ 不一致"
        if not match_ok:
            all_passed = False
        print(f"  [{seq}] 檔名={filename_name}, CSV={csv_name} → {status}")

    if all_passed:
        print("  🎉 全部通過！外部檔名與內部人名完全一致。")
    else:
        print("  ⚠️ 存在不一致，請人工檢查！")
    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    process_all()
