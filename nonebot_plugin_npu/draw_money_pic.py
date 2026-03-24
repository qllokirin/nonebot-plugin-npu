"""
财务信息图片生成模块
使用htmlkit库将财务信息转换为优美的图片
"""
from datetime import datetime
from pathlib import Path
from nonebot import logger
from io import BytesIO
import json
from typing import List, Dict, Any
from nonebot.utils import run_sync
from nonebot import require
require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import html_to_pic

async def draw_money_info_pic(money_info: List[Dict[str, Any]]):
    """
    生成财务信息的优美图片
    
    Args:
        money_info: 财务信息列表
        
    Returns:
        保存的图片字节数据
    """
    # 生成HTML内容
    html_content = await generate_money_html(money_info)
    try:
        money_img_bytes = await html_to_pic(html_content, max_width=1500, dpi=600.0,default_font_size=18.0)
        return money_img_bytes
    except Exception as e:
        logger.error(f"生成财务信息图片失败: {e}")
        raise

async def generate_money_html(money_info: List[Dict[str, Any]]) -> str:
    """
    生成财务信息的HTML内容

    Args:
        money_info: 财务信息列表

    Returns:
        HTML字符串
    """

    # 当前年月
    now = datetime.now()
    current_year = str(now.year)
    current_month = str(now.month).zfill(2)

    # 统计本月发钱次数
    current_month_count = 0
    for item in money_info:
        nian = str(item.get("nian", "")).strip()
        yue = str(item.get("yue", "")).strip().zfill(2)
        if nian == current_year and yue == current_month:
            current_month_count += 1

    # 根据本月发钱次数决定emoji和说明
    if current_month_count >= 2:
        status_emoji = "😊"
        status_text = "这个月已发两次"
    elif current_month_count == 1:
        status_emoji = "😐"
        status_text = "这个月发了一次"
    else:
        status_emoji = "😞"
        status_text = "这个月还没发"

    # 构建表格行
    rows_html = ""
    for idx, item in enumerate(money_info, 1):
        nian = str(item.get("nian", "")).strip()
        yue = str(item.get("yue", "")).strip().zfill(2)
        ffxmmc = str(item.get("ffxmmc", "")).strip()
        xmmc = str(item.get("xmmc", "")).strip()
        lrrq = str(item.get("lrrq", "")).strip()
        pzrq = str(item.get("pzrq", "")).strip()
        sfje = item.get("sfje", 0)

        is_current_month = (nian == current_year and yue == current_month)
        row_class = "current-month-row" if is_current_month else ""

        rows_html += f"""
        <tr class="{row_class}">
            <td class="cell-center">{idx}</td>
            <td class="cell-center">{nian}-{yue}</td>
            <td class="cell-left">{ffxmmc}</td>
            <td class="cell-left">{xmmc}</td>
            <td class="cell-center">{lrrq}</td>
            <td class="cell-center">{pzrq}</td>
            <td class="cell-right">¥ {sfje}</td>
        </tr>
        """

    # 无数据时的占位内容
    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="7" class="empty-cell">暂无发放记录</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>这个月发钱了吗</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                min-height: 100vh;
                padding: 32px;
                background:
                    radial-gradient(circle at top left, rgba(129, 199, 255, 0.22), transparent 35%),
                    radial-gradient(circle at top right, rgba(170, 140, 255, 0.18), transparent 30%),
                    linear-gradient(135deg, #eef4ff 0%, #f7f9fc 45%, #edf2f7 100%);
                color: #1f2937;
            }}
            .current-month-row td {{
                background: #dfe9ff;
            }}

            .current-month-row:hover td {{
                background: #d2e0ff;
            }}

            .current-month-row td:first-child {{
                border-left: 4px solid #6366f1;
            }}
            .container {{
                max-width: 1180px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.88);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(255, 255, 255, 0.65);
                border-radius: 24px;
                box-shadow:
                    0 20px 60px rgba(31, 41, 55, 0.10),
                    0 8px 24px rgba(99, 102, 241, 0.08);
                overflow: hidden;
            }}

            .header {{
                position: relative;
                padding: 34px 40px 28px;
                background: linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%);
                color: #ffffff;
            }}

            .header::after {{
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(120deg, rgba(255,255,255,0.08), rgba(255,255,255,0));
                pointer-events: none;
            }}

            .title-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                flex-wrap: wrap;
            }}

            .header h1 {{
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}

            .status-badge {{
                display: inline-flex;
                align-items: center;
                gap: 10px;
                padding: 10px 16px;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.16);
                border: 1px solid rgba(255, 255, 255, 0.22);
                font-size: 15px;
                font-weight: 600;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.12);
            }}

            .status-emoji {{
                font-size: 22px;
                line-height: 1;
            }}

            .header p {{
                margin-top: 12px;
                font-size: 14px;
                opacity: 0.92;
            }}

            .content {{
                padding: 28px;
            }}

            .table-wrap {{
                overflow-x: auto;
                border-radius: 18px;
                border: 1px solid #e8edf5;
                background: #ffffff;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
            }}

            table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                min-width: 900px;
            }}

            thead {{
                background: linear-gradient(180deg, #f8fbff 0%, #f2f6fb 100%);
            }}

            th {{
                padding: 16px 14px;
                text-align: left;
                font-size: 13px;
                font-weight: 700;
                color: #334155;
                border-bottom: 1px solid #dbe4f0;
                white-space: nowrap;
            }}

            td {{
            padding: 14px;
            font-size: 13px;
            color: #374151;
            border-bottom: 1px solid #eef2f7;
            background: rgba(255,255,255,0.92);
            white-space: nowrap;
            }}

            tbody tr {{
                transition: transform 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
            }}

            tbody tr:hover td {{
                background: #f8fbff;
            }}

            tbody tr:last-child td {{
                border-bottom: none;
            }}

            .cell-center {{
                text-align: center;
            }}

            .cell-left {{
                text-align: left;
            }}

            .cell-right {{
                text-align: right;
                color: #0f766e;
                font-weight: 700;
                font-variant-numeric: tabular-nums;
            }}

            .empty-cell {{
                text-align: center;
                color: #64748b;
                padding: 36px 16px;
                font-size: 14px;
            }}

            @media (max-width: 768px) {{
                body {{
                    padding: 16px;
                }}

                .header {{
                    padding: 24px 20px 20px;
                }}

                .header h1 {{
                    font-size: 26px;
                }}

                .content {{
                    padding: 16px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title-row">
                    <h1>这个月发钱了吗</h1>
                    <div class="status-badge">
                        <span class="status-emoji">{status_emoji}</span>
                        <span>{status_text}</span>
                    </div>
                </div>
                <p>本月发放次数：{current_month_count}</p>
            </div>

            <div class="content">
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 6%;">#</th>
                                <th style="width: 10%;">年月</th>
                                <th style="width: 22%;">发放项目</th>
                                <th style="width: 22%;">项目名称</th>
                                <th style="width: 15%;">录入日期</th>
                                <th style="width: 15%;">凭证日期</th>
                                <th style="width: 10%;">实发金额</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return html