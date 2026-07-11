# 股票交易训练沙盘

这是一个不依赖真实交易时间的股票交易训练软件原型。它的目标不是复制同花顺模拟盘，而是提供一个可以暂停、快进、复盘、重复训练的市场沙盘。

当前版本已经具备一个最小可运行闭环：

- 虚拟市场时钟：按 K 线推进，可加速、跳转、暂停。
- 结构化行情生成：包含牛市、熊市、震荡、恐慌、修复等市场状态。
- 行业联动与个股扰动：行情不是完全随机，而是由市场因子、行业因子、个股因子和事件冲击共同驱动。
- 订单撮合：支持市价单、限价单、手续费、印花税、滑点、部分成交。
- A 股约束：默认启用 T+1、100 股一手。
- 网页训练台：K 线画布、账户、持仓、下单、快进和复盘报告。
- 交易标记：买入/卖出会以 B/S 标记显示在对应 K 线上，并展示成交价格。
- 鼠标悬浮：移动到 K 线可查看日期、开高低收、成交量、涨跌幅和指针价。
- 持仓细节：显示持股、可卖、成本价、现价、市值和浮动盈亏。
- 资产曲线：记录每一步训练后的账户权益，显示当前收益表现和初始资金线。
- 历史盲测：支持从 `data/historical/*.csv` 导入真实历史行情，随机抽取片段并隐藏真实代码和日期。
- 交易计划：下单时可记录交易理由、止损价、目标价和备注，并随成交记录一起复盘。
- 单笔复盘：卖出后自动配对买入批次，统计盈亏、持有 K 线数、最大浮盈/浮亏和计划触发情况。
- 训练记录：可手动保存每轮训练摘要，记录收益率、最大回撤、胜率、盈亏比和交易次数。

## 启动网页训练台

```powershell
python scripts/serve.py
```

然后打开：

```text
http://127.0.0.1:8765
```

也可以让程序自动打开浏览器：

```powershell
python scripts/serve.py --open
```

在 PowerShell 里不要直接输入 `http://127.0.0.1:8765/` 当命令；如果想从 PowerShell 打开网址，可以用：

```powershell
Start-Process "http://127.0.0.1:8765/"
```

## 命令行演示

```powershell
python scripts/demo.py
```

## 导入真实历史行情

把 CSV 放入：

```text
data/historical/
```

CSV 至少包含字段：

```csv
date,open,high,low,close,volume
2023-01-03,10.20,10.50,10.10,10.32,1234567
```

也可以包含：

```csv
symbol,industry
```

然后启动网页训练台，选择“历史盲测”，点击“重置”。系统会随机抽取历史片段，并显示为 `STOCK_A`、`STOCK_B`，避免你直接记住真实股票和日期。

## 训练记录

网页右上角点击“保存本轮”会把当前训练摘要写入：

```text
data/training_runs.jsonl
```

该文件使用 JSON Lines 格式，一行代表一轮训练，便于后续统计个人成长曲线。

## 运行测试

```powershell
python -m unittest discover -s tests
```

## 可选 FastAPI 入口

如果后面要接专业前端或移动端，可以安装可选依赖启动 FastAPI：

```powershell
pip install -e .[api]
uvicorn api.app:app --reload
```

API 启动后可以访问：

- `GET /state` 查看当前行情和账户
- `POST /step?bars=1` 推进市场
- `POST /orders` 提交订单
- `GET /report` 查看训练报告

## 目录结构

```text
stock_trainer/
  clock.py       虚拟市场时钟
  data.py        训练行情生成器
  historical.py  真实历史 CSV 导入和匿名盲测
  broker.py      撮合、费用、T+1、持仓
  simulator.py   训练会话主入口
  analytics.py   复盘报告和交易诊断
  models.py      数据模型
api/
  app.py         FastAPI 服务入口
scripts/
  demo.py        命令行演示
  serve.py       本地网页训练台服务
web/
  index.html     交易训练界面
  styles.css     页面样式
  app.js         前端交互、K 线绘制、买卖点和悬浮提示
tests/
  test_engine.py 核心行为测试
```

## 后续路线

第一阶段建议继续做三件事：

1. 接入真实历史日线或分钟线数据，并保留当前生成器作为训练场景补充。
2. 增强图表：均线、成交量均线、买卖点标记、资产曲线。
3. 增强复盘教练：识别追涨杀跌、过度交易、仓位过重、止损拖延等行为。

这个项目最重要的设计原则是：市场可以被加速，但训练反馈必须认真。收益率只是结果，交易纪律和错误模式才是系统真正要帮你磨出来的东西。
