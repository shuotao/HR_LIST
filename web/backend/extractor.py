# -*- coding: utf-8 -*-
"""
extractor.py — Resume field extraction (ported from extract_hr_data.py)

Accepts markdown text string, returns structured candidate data dict.
No file I/O, no CSV, no renaming — pure extraction logic only.
"""

import re
import unicodedata


def normalize_text(text):
    """Convert Kangxi Radicals and other variants to standard CJK characters."""
    return unicodedata.normalize('NFKC', text)


def extract_from_markdown(md_text):
    """
    Extract structured candidate fields from markdown text.

    Returns dict with keys:
      name, age, language_skills, education, recent_work,
      recent_work_desc, seniority, prev_companies, full_text
    """
    content = normalize_text(md_text)
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
        if "\u6b72" in line and ("\u7537" in line or "\u5973" in line):  # 歲, 男, 女
            m = re.search(r'^([^\s\d]+?)\s+(\d+)\u6b72', line)
            if m:
                name = m.group(1).strip()
                age = m.group(2).strip()
                break
            else:
                m2 = re.search(r'(\d+)\u6b72', line)
                if m2:
                    age = m2.group(1)
                    name = line.split(age)[0].strip()
                    break

    # Block extraction helper
    def get_block(start_kw, stop_kws):
        start_kw_norm = normalize_text(start_kw).replace(" ", "")
        stop_kws_norm = [normalize_text(kw).replace(" ", "") for kw in stop_kws]

        start_idx = -1
        for i, l in enumerate(lines):
            l_norm = normalize_text(l).replace(" ", "")
            if start_kw_norm in l_norm and len(l) < 20:
                start_idx = i
                break

        if start_idx == -1:
            return ""

        block_lines = []
        for j in range(start_idx + 1, len(lines)):
            l = lines[j]
            if not l:
                continue
            l_norm = normalize_text(l).replace(" ", "")
            if any(stop in l_norm for stop in stop_kws_norm):
                break
            block_lines.append(l)

        return " ".join(block_lines).strip()

    # 2. Language Skills
    known_langs = [
        "\u4e2d\u6587", "\u82f1\u6587", "\u53f0\u8a9e", "\u65e5\u6587",
        "\u7cb5\u8a9e", "\u5ba2\u5bb6\u8a9e", "\u5370\u5c3c\u6587",
        "\u897f\u73ed\u7259\u6587", "\u6cf0\u6587", "\u4e0a\u6d77\u8a71",
        "\u97d3\u6587", "\u6cd5\u6587", "\u5fb7\u6587", "\u8d8a\u5357\u6587",
    ]
    lang_stop_kws = [
        "\u6280\u80fd\u5c08\u9577", "\u5c08\u9577",
        "\u8a8d\u8b49\u8cc7\u683c", "\u81ea\u50b3",
        "\u6c42\u8077\u689d\u4ef6", "\u9644\u4ef6",
        "\u6700\u9ad8\u5b78\u6b77", "\u6559\u80b2\u80cc\u666f",
    ]
    lang_stop_norms = [normalize_text(kw).replace(" ", "") for kw in lang_stop_kws]

    lang_start = -1
    for i, l in enumerate(lines):
        l_norm = normalize_text(l).replace(" ", "")
        if "\u8a9e\u6587\u80fd\u529b" in l_norm and len(l) < 20:
            lang_start = i
            break

    if lang_start != -1:
        lang_lines = []
        for j in range(lang_start + 1, len(lines)):
            l = lines[j]
            if not l:
                continue
            l_norm = normalize_text(l).replace(" ", "")
            if any(stop in l_norm for stop in lang_stop_norms):
                break
            lang_lines.append(l.strip())

        languages_found = []
        proficiencies_found = []
        test_scores_found = []

        for line in lang_lines:
            if line in known_langs:
                languages_found.append(line)
            elif re.match(r'\u807d/.+', line):
                proficiencies_found.append(line)
            elif line in ["\u7cbe\u901a", "\u4e2d\u7b49", "\u7565\u61c2", "\u4e0d\u6703"]:
                proficiencies_found.append(line)
            elif any(kw in line for kw in ["TOEIC", "\u591a\u76ca", "GEPT", "\u82f1\u6aa2"]):
                test_scores_found.append(line)

        def simplify_prof(prof):
            if not prof.startswith("\u807d/"):
                return prof
            levels = re.findall(r'[\u807d\u8aaa\u8b80\u5beb]/([^\s\u3001]+)', prof)
            if levels and len(set(levels)) == 1:
                return levels[0]
            return prof

        lang_prof_map = {}
        for i, lang in enumerate(languages_found):
            prof = proficiencies_found[i] if i < len(proficiencies_found) else ""
            if prof:
                prof = simplify_prof(prof)
            lang_prof_map[lang] = prof

        parts = []
        if "\u82f1\u6587" in lang_prof_map:
            eng_prof = lang_prof_map["\u82f1\u6587"]
            eng_str = f"\u82f1\u6587({eng_prof})" if eng_prof else "\u82f1\u6587"
            if test_scores_found:
                eng_str += " " + " ".join(test_scores_found)
            parts.append(eng_str)

        for lang in languages_found:
            if lang != "\u82f1\u6587":
                parts.append(lang)

        language_skills = "\u3001".join(parts) if parts else ""

    # 3. Education
    education = get_block("\u6700\u9ad8\u5b78\u6b77",
                          ["\u5e0c\u671b\u8077\u7a31", "\u6700\u8fd1\u5de5\u4f5c",
                           "\u7e3d\u5e74\u8cc7", "\u5c45\u4f4f\u5730", "\u4ee3\u78bc"])

    # 4. Recent Work
    recent_work = get_block("\u6700\u8fd1\u5de5\u4f5c",
                            ["\u5c45\u4f4f\u5730", "E-mail", "\u806f\u7d61\u96fb\u8a71",
                             "\u66f4\u65b0\u65e5", "\u5de5\u4f5c\u7d93\u6b77", "Email"])

    # 5. Total Seniority
    seniority_block = get_block("\u7e3d\u5e74\u8cc7",
                                 ["\u6700\u8fd1\u5de5\u4f5c", "\u5c45\u4f4f\u5730",
                                  "\u96fb\u6a5f\u88dd\u4fee", "\u4ee3\u78bc", "\u5de5\u4f5c\u7d93\u6b77"])
    if seniority_block:
        num_m = re.search(r'(\d+)', seniority_block)
        if num_m:
            seniority = num_m.group(1)

    if not seniority:
        for i, l in enumerate(lines):
            if "\u7e3d\u5e74\u8cc7" in l.replace(" ", ""):
                for j in range(i + 1, min(i + 4, len(lines))):
                    num = re.search(r'(\d+)', lines[j])
                    if num:
                        seniority = num.group(1)
                        break
                if seniority:
                    break

    # 6. Work History for Previous 2 Companies & Recent Work Description
    exp_idx = -1
    for i, l in enumerate(lines):
        if "\u5de5\u4f5c\u7d93\u6b77" in l.replace(" ", ""):
            exp_idx = i
            break

    if exp_idx != -1:
        job_indices = []
        for j in range(exp_idx + 1, len(lines)):
            stop_kws = ["\u6559\u80b2\u80cc\u666f", "\u500b\u4eba\u8cc7\u6599",
                        "\u500b\u2fbc\u8cc7\u6599", "\u6280\u80fd\u5c08\u9577"]
            l_norm = normalize_text(lines[j]).replace(" ", "")
            if any(stop in l_norm for stop in stop_kws):
                break
            if re.search(r'\d{4}/\d{2}~', lines[j]):
                job_indices.append(j)
                parts_list = lines[j].split()
                if parts_list:
                    cname = parts_list[0].strip()
                    if (cname and cname not in companies
                            and not any(x in cname for x in ["\u7e3d\u5e74\u8cc7", "\u66f4\u65b0\u65e5", "\u4ee3\u78bc"])):
                        companies.append(cname)

        if job_indices:
            start_idx = job_indices[0]
            end_idx = job_indices[1] if len(job_indices) > 1 else len(lines)
            desc_stop_kws = ["\u6559\u80b2\u80cc\u666f", "\u500b\u4eba\u8cc7\u6599",
                             "\u6280\u80fd\u5c08\u9577", "\u8a9e\u6587\u80fd\u529b",
                             "\u6c42\u8077\u689d\u4ef6", "\u81ea\u50b3"]
            desc_stop_norms = [normalize_text(kw).replace(" ", "") for kw in desc_stop_kws]

            desc_lines = []
            capturing = False
            for j in range(start_idx, end_idx):
                l_norm = normalize_text(lines[j]).replace(" ", "")
                if any(stop in l_norm for stop in desc_stop_norms):
                    break
                if "\u5de5\u4f5c\u5167\u5bb9" in l_norm:
                    capturing = True
                    first_line = lines[j]
                    for variant in ["\u5de5\u4f5c\u5167\u5bb9", "\u2f23\u4f5c\u5167\u5bb9"]:
                        first_line = first_line.replace(variant, "", 1).strip()
                    if first_line:
                        desc_lines.append(first_line)
                    continue
                if capturing and lines[j].strip():
                    desc_lines.append(lines[j].strip())
            recent_work_desc = " ".join(desc_lines).strip()

    prev_companies = "\u3001".join(companies[1:3]) if len(companies) > 1 else ""

    # Collect work_lines for scoring use
    work_lines = []
    if exp_idx != -1:
        for j in range(exp_idx + 1, len(lines)):
            if re.match(r'\d{4}/\d{2}', lines[j]):
                work_lines.append(lines[j])

    return {
        'name': name,
        'age': age,
        'language_skills': language_skills,
        'education': education,
        'recent_work': recent_work,
        'recent_work_desc': recent_work_desc,
        'seniority': seniority,
        'prev_companies': prev_companies,
        'work_lines': work_lines,
        'full_text': content,
    }
