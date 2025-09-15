import asyncio
import httpx
import re
import uuid
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup


async def get_new_cookie_Fkjfy9yPdPQuP(folder_path, html):
    """
    瑞数6代解密
    第一次访问网页出现412状态码，在附带的html中有一些变量和代码
    在模拟环境中运行这个js后，会更新Fkjfy9yPdPQuP这个cookie的值
    再访问一次网页就200了
    """
    # 解析第一次412中html的内容
    soup = BeautifulSoup(html, "html.parser")
    meta_tag = soup.find("meta", {"id": True, "content": True})
    rs6_id = meta_tag.get("id")
    rs6_content = meta_tag.get("content")
    inline_scripts = soup.find("script", src=False).get_text()
    external_scripts = soup.find("script", src=True).get("src")
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        url = "https://jwxt.nwpu.edu.cn" + external_scripts
        response = await client.get(url)
    # 组装js代码并运行
    with open(Path(__file__).parent / "rs6.js", "r", encoding="utf-8") as f:
        rs6_code = (
            f.read().replace("_rs6_id_", rs6_id).replace("_rs6_content_", rs6_content)
        )
    rs6_code += f"\n{inline_scripts}\n{response.text}\nconsole.log(document.cookie);"
    temp_file = folder_path / f"temp_{uuid.uuid4().hex}.js"
    temp_file.write_text(rs6_code, encoding="utf-8")
    result = subprocess.run(
        ["node", temp_file],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    temp_file.unlink(missing_ok=True)
    cookies = result.stdout.strip()
    match = re.search(r"Fkjfy9yPdPQuP=([^;]+);?", cookies)
    if match:
        new_cookie_Fkjfy9yPdPQuP = match.group(1)
        return new_cookie_Fkjfy9yPdPQuP
    else:
        return None


if __name__ == "__main__":
    html = ""
    asyncio.run(get_new_cookie_Fkjfy9yPdPQuP(html))
