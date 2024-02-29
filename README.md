# 📖 介绍

nonebot-plugin-npu，翱翔门户成绩监控插件，能获取成绩、排名、绩点，当出现新成绩时推送给使用者

- [x] 获取成绩、绩点、排名

- [x] 出现新成绩时推送

- [x] 排名变动时推送

- [ ] 排考检测

# 💿 安装

目前仅文件夹插件的安装（放在`pyproject.toml`的`plugin_dirs`字段的文件夹里）

```
git clone https://github.com/qllokirin/nonebot-plugin-npu.git ./{你的插件目录}
```

依赖安装

* 1.激活python环境

  ```
  .\.venv\Scripts\activate   				(Windows)
  source \.venv\Scripts\activate			(Ubuntu)
  ```

* 2.安装

  ```
  pip install requests
  nb plugin install nonebot_plugin_apscheduler
  ```

* 3.安装wkhtmltopdf

  ```
  打开https://wkhtmltopdf.org/downloads.html安装	 (Windows)
  sudo apt-get install wkhtmltopdf				(Ubuntu)
  ```

- [ ] nb plugin安装方法

# 🎉 使用

### 指令表

|     指令      | 范围 |         说明         |
| :-----------: | :--: | :------------------: |
|   **/翱翔**   | 私聊 |     登陆翱翔门户     |
|   /翱翔成绩   | 私聊 | 获取最近一学期的成绩 |
| /翱翔全部成绩 | 私聊 |     获取全部成绩     |
|   /翱翔排名   | 私聊 |   获取排名以及绩点   |

# 效果图

![图层 1.png](https://s2.loli.net/2024/02/20/lyNCOXUaczwBIr3.png)

![图层 0.png](https://s2.loli.net/2024/02/20/CyQ5IAcN61YD4wG.png)

# nonebot使用

> 其实是为了方便自己后续再搭建一个  b站大佬的详细[教程](https://www.bilibili.com/video/BV1984y1b7JY)

```
pip install nb-cli
nb
> 创建一个nonebot项目
> simple
> 名字
> FastAPI
> OneBot V11
> Y
> Y
cd {项目名称}
# 激活python环境（可选）
.\.venv\Scripts\activate   				(Windows)
source \.venv\Scripts\activate			(Ubuntu)
# 启动
nb run --reload 
```

打开`.env.prod`追加如下内容

```
HOST=0.0.0.0  # 配置 NoneBot 监听的 IP / 主机名
PORT=22330  # 配置 NoneBot 监听的端口
SUPERUSER=["123456"] # QQ账号 超级用户
```

安装插件

```
nb plugin install nonebot_plugin_gocqhttp
# 再次启动后打开 http://127.0.0.1:22330/go-cqhttp/ 进行登陆QQ号
nb run
```

> 扫码时需要在同网络环境下，云服务器上登录需要在本地登陆好之后把accounts文件夹复制过去，accounts文件夹里面的binary文件夹要删掉

# 致谢

翱翔门户登陆以及数据获取参考了：https://github.com/cheanus/Automation/blob/main/GradesMonitorLinux.py

