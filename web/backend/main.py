# -*- coding: utf-8 -*-
"""
main.py — Flask API for HRMD Resume Health Check

POST /api/analyze — Upload PDF resume, get scoring results.
"""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_cors import CORS
from markitdown import MarkItDown

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

from extractor import extract_from_markdown
from scoring import score_candidate_from_resume
from bim_scorer import score_bim_manager
from email_sender import send_scoring_result

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

md_converter = MarkItDown()


@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'resume' not in request.files:
        return jsonify({'error': '請上傳履歷 PDF 檔案'}), 400

    file = request.files['resume']
    if not file.filename:
        return jsonify({'error': '未選擇檔案'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': '僅支援 PDF 格式'}), 400

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name
        file.save(tmp_path)

    try:
        # Check file size
        if os.path.getsize(tmp_path) > MAX_FILE_SIZE:
            return jsonify({'error': '檔案大小超過 10MB 限制'}), 400

        # Step 1: PDF -> Markdown
        try:
            result = md_converter.convert(tmp_path)
            md_text = result.text_content
        except Exception as e:
            return jsonify({'error': f'PDF 轉換失敗: {str(e)}'}), 500

        if not md_text or len(md_text.strip()) < 50:
            return jsonify({
                'error': '無法從 PDF 中擷取文字內容。可能是掃描圖片型 PDF，請使用文字型 PDF 履歷。'
            }), 400

        # Step 2: Extract structured fields
        candidate = extract_from_markdown(md_text)

        if not candidate['name']:
            candidate['name'] = os.path.splitext(file.filename)[0]

        # Step 3: General scoring (M/N/E/D)
        general_result = score_candidate_from_resume(candidate)

        # Step 4: Role-aware position scoring (default = BIM Manager legacy)
        role = request.form.get('role', 'default')
        if role not in ('default', 'mep-design', 'space-manager'):
            role = 'default'
        bim_result = score_bim_manager(candidate, role=role)

        # Build response
        response = {
            'candidate': {
                'name': candidate['name'],
                'age': candidate['age'],
                'education': candidate['education'],
                'language_skills': candidate['language_skills'],
                'recent_work': candidate['recent_work'],
                'recent_work_desc': candidate['recent_work_desc'][:200],
                'seniority': candidate['seniority'],
                'prev_companies': candidate['prev_companies'],
            },
            'general_score': general_result,
            'bim_score': bim_result,
        }

        return jsonify(response)

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.route('/api/submit-result', methods=['POST'])
def submit_result():
    """Save result to Firestore."""
    data = request.get_json()

    if not data:
        return jsonify({'error': '無效的請求'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    general_score = data.get('general_score')
    bim_score = data.get('bim_score')

    if not name or not email:
        return jsonify({'error': '請提供姓名和 Email'}), 400

    if not general_score or not bim_score:
        return jsonify({'error': '缺少評分資料'}), 400

    return jsonify({'status': 'success', 'message': '感謝！評分已儲存'})


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
