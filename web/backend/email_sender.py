# -*- coding: utf-8 -*-
"""
email_sender.py — Send scoring results via email
"""

import os
import sys
import ssl
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Disable SSL verification for development (not recommended for production)
ssl._create_default_https_context = ssl._create_unverified_context


def send_scoring_result(recipient_email, recipient_name, general_score, bim_score):
    """
    Send scoring results to the candidate's email.

    Args:
        recipient_email: Candidate email
        recipient_name: Candidate name
        general_score: General engineering score dict
        bim_score: BIM position match dict

    Returns:
        True if successful, False otherwise
    """

    sg_api_key = os.getenv('SENDGRID_API_KEY')
    if not sg_api_key:
        print("ERROR: SENDGRID_API_KEY not set", file=sys.stderr)
        return False

    general_score_val = general_score.get('score', 0)
    bim_match = bim_score.get('match_percentage', 0)
    bim_level = bim_score.get('level', 'low')
    general_excluded = general_score.get('excluded', False)

    status = '不符合條件 (排除)' if general_excluded else '合格'

    html_body = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px; }}
            .score-box {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #3498db; }}
            .score-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .score-label {{ color: #666; font-size: 14px; }}
            .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>HRMD 履歷健康檢查 — 評分結果</h2>
                <p>親愛的 {recipient_name} 您好</p>
            </div>
            <div class="content">
                <p>感謝您上傳履歷參與 HRMD 履歷健康檢查。以下是您的評分結果：</p>

                <div class="score-box">
                    <div class="score-label">通用工程人才評分</div>
                    <div class="score-value">{general_score_val} 分</div>
                    <p>狀態：<strong>{status}</strong></p>
                </div>

                <div class="score-box">
                    <div class="score-label">BIM 主任職缺適配度</div>
                    <div class="score-value">{bim_match}%</div>
                    <p>評等：<strong>{bim_level}</strong></p>
                </div>

                <p>更多詳細評分內容，請回訪系統查看。</p>

                <p style="color: #999; font-size: 12px;">
                    本系統僅供履歷參考分析，不代表正式錄取結果。
                </p>
            </div>
            <div class="footer">
                <p>HRMD Resume Health Check © 2026 | Powered by CTCI Screening Engine</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        message = Mail(
            from_email='noreply@hrmd.ctci.com.tw',
            to_emails=recipient_email,
            subject='HRMD 履歷健康檢查 — 您的評分結果',
            html_content=html_body
        )

        sg = SendGridAPIClient(sg_api_key)
        response = sg.send(message)

        print(f"✓ Email sent to {recipient_email}, status: {response.status_code}", file=sys.stderr)
        return response.status_code == 202
    except Exception as e:
        print(f"✗ Error sending email: {type(e).__name__}: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False
