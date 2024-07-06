# 📖 介绍

nonebot-plugin-npu，翱翔门户成绩监控插件，能获取成绩、排名、绩点，当出现新成绩时推送给使用者

- [x] 获取成绩、绩点、排名
- [x] 出现新成绩时推送
- [x] 排名变动时推送
- [x] 宿舍电费监控
- [x] 排考检测
- [ ] 课表提取

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
  pip install requests imgkit==1.0.2 paho-mqtt==1.6.1 bs4 rsa
  nb plugin install nonebot-plugin-apscheduler
  ```

* 3.安装wkhtmltopdf

  ```
  打开https://wkhtmltopdf.org/downloads.html安装
  ```

- [ ] nb plugin安装方法

在`.env.prod`中新增字段`npu_check_time=30`，代表每多少分钟检测一次成绩

# 🎉 使用

### 指令表

|     指令      |   范围    |                说明                |
| :-----------: | :-------: | :--------------------------------: |
|   **/翱翔**   | 私聊/艾特 |            登陆翱翔门户            |
|   /翱翔成绩   | 私聊/艾特 |          获取本学期的成绩          |
|   /翱翔排名   | 私聊/艾特 |            获取排名信息            |
|   /翱翔考试   | 私聊/艾特 |        获取未结束的考试信息        |
| /翱翔全部成绩 | 私聊/艾特 |            获取全部成绩            |
| /翱翔全部考试 | 私聊/艾特 |          获取全部考试信息          |
| /翱翔电费绑定 | 私聊/艾特 | 绑定宿舍，当电费小于25时会推送消息 |
| /翱翔电费查询 | 私聊/艾特 |            查询当前电费            |

# 效果图

<details>
<summary>演示效果</summary>

![mail.png](images/demo.jpg)

</details>

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
SUPERUSERS=["123456"] # QQ账号 超级用户
```

gocq基本已g，登陆建议使用[NapCatQQ](https://github.com/NapNeko/NapCatQQ)或[Lagrange](https://github.com/LagrangeDev/Lagrange.Core)

# 致谢

翱翔门户登陆以及数据获取参考了：https://github.com/cheanus/Automation/blob/main/GradesMonitorLinux.py

