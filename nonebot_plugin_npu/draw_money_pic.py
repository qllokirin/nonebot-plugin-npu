"""
财务信息图片生成模块
使用htmlkit库将财务信息转换为优美的图片
"""

from pathlib import Path
from nonebot import logger
from io import BytesIO
import json
from typing import List, Dict, Any
from nonebot.utils import run_sync
from nonebot import require
require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import html_to_pic

@run_sync
def draw_money_info_pic(money_info: List[Dict[str, Any]], save_path: str = None):
    """
    生成财务信息的优美图片
    
    Args:
        money_info: 财务信息列表
        save_path: 保存路径，默认为test文件夹
        
    Returns:
        保存的图片字节数据
    """
    
    if save_path is None:
        save_path = Path(__file__).parent / "test" / "money_info.png"
    else:
        save_path = Path(save_path)
    
    # 确保保存目录存在
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 生成HTML内容
    html_content = generate_money_html(money_info)
    
    try:
        pic_bytes = html_to_pic(html_content)
        print(type(pic_bytes))
        print(pic_bytes)
        # 保存图片到文件
        save_path.write_bytes(pic_bytes)
        logger.info(f"财务信息图片生成成功，已保存到: {save_path}")
        return pic_bytes
    except Exception as e:
        logger.error(f"生成财务信息图片失败: {e}")
        raise


@run_sync
def generate_money_html(money_info: List[Dict[str, Any]]) -> str:
    """
    生成财务信息的HTML内容
    
    Args:
        money_info: 财务信息列表
        
    Returns:
        HTML字符串
    """
    
    # 计算总金额
    total_amount = sum(item.get("sfje", 0) for item in money_info)
    
    # 构建表格行
    rows_html = ""
    for idx, item in enumerate(money_info, 1):
        nian = item.get("nian", "")
        yue = item.get("yue", "")
        ffxmmc = item.get("ffxmmc", "").strip()
        xmmc = item.get("xmmc", "").strip()
        lrrq = item.get("lrrq", "")
        pzrq = item.get("pzrq", "")
        sfje = item.get("sfje", 0)
        
        rows_html += f"""
        <tr>
            <td class="cell-center">{idx}</td>
            <td class="cell-center">{nian}-{yue}</td>
            <td class="cell-left">{ffxmmc}</td>
            <td class="cell-left">{xmmc}</td>
            <td class="cell-center">{lrrq}</td>
            <td class="cell-center">{pzrq}</td>
            <td class="cell-right">¥ {sfje}</td>
        </tr>
        """
    
    # 完整HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>财务信息</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                padding: 30px;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }}
            
            .container {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            
            .header p {{
                font-size: 14px;
                opacity: 0.9;
            }}
            
            .content {{
                padding: 30px;
            }}
            
            .summary {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            
            .summary-item {{
                text-align: center;
            }}
            
            .summary-label {{
                font-size: 12px;
                color: #666;
                margin-bottom: 8px;
                text-transform: uppercase;
            }}
            
            .summary-value {{
                font-size: 24px;
                font-weight: bold;
                color: #667eea;
            }}
            
            table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
            }}
            
            thead {{
                background: #f0f2f5;
            }}
            
            th {{
                padding: 15px;
                text-align: left;
                font-weight: 600;
                color: #333;
                border-bottom: 2px solid #667eea;
                font-size: 13px;
            }}
            
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
                font-size: 13px;
            }}
            
            tbody tr {{
                transition: background-color 0.3s;
            }}
            
            tbody tr:hover {{
                background-color: #f8f9fa;
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
                color: #e74c3c;
                font-weight: 600;
            }}
            
            .footer {{
                padding: 20px 30px;
                background: #f8f9fa;
                text-align: right;
                border-top: 1px solid #e9ecef;
                font-size: 12px;
                color: #666;
            }}
            
            .total-row {{
                background: #f0f2f5;
                font-weight: 600;
            }}
            
            .total-row td {{
                border-top: 2px solid #667eea;
                border-bottom: 2px solid #667eea;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 财务信息</h1>
                <p>学生财务收支详情</p>
            </div>
            
            <div class="content">
                <div class="summary">
                    <div class="summary-item">
                        <div class="summary-label">记录总数</div>
                        <div class="summary-value">{len(money_info)}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">总金额</div>
                        <div class="summary-value">¥ {total_amount}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">平均金额</div>
                        <div class="summary-value">¥ {total_amount / len(money_info) if money_info else 0:.0f}</div>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th style="width: 5%;">#</th>
                            <th style="width: 10%;">年月</th>
                            <th style="width: 20%;">发放项目</th>
                            <th style="width: 20%;">项目名称</th>
                            <th style="width: 15%;">录入日期</th>
                            <th style="width: 15%;">凭证日期</th>
                            <th style="width: 15%;">实发金额</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                        <tr class="total-row">
                            <td colspan="6" style="text-align: right;">合计</td>
                            <td class="cell-right">¥ {total_amount}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>生成时间: 2026-03-21 00:00:00</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
