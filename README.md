# 元件管理系统

一个本地运行的单用户元器件库存原型。系统使用 `LCSC + Supplier Part` 作为立创元件的精确匹配键，用 Comment 和 Footprint 保留参数与封装信息。

## 已实现

- 元件库页面集成“BOM 建库”和手动添加，支持元件查询、修改、删除和库存调整。
- 导入立创商城 `.xls` 订单，以“发货数量”入库。
- 订单记录默认折叠；无格位的元件可通过可视化收纳盒网格快速归位并入库。
- 收纳盒支持新增、查看、改名、调整行列和删除；格位可修改标识、更换元件或清空。
- “BOM 领料”导入后首次展开明细，之后默认折叠；格位内显示需取数量和 Designator 焊接位号，支持删除尚未领料的 BOM。
- BOM Supplier Part 不存在或库存不足时，按规范化 Comment 精确匹配库存候选；Footprint 仅展示供人工确认，确认替代后仍按格位逐项领料。
- 手动新建元件、手动调整库存，并记录每笔库存变动。
- 库存流水支持关键字和类型筛选；手动库存调整可通过反向流水安全撤销。
- 数据管理支持五张工作表的 Excel 导出、SQLite 在线备份和完整恢复；恢复前会自动保存当前数据库。

## 运行

需要 Python 3.12。

```powershell
python -m pip install -r requirements.txt
python main.py
```

然后打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。数据默认保存在项目根目录的 `component_inventory.db`。

## 导入列

BOM 建库与 BOM 领料使用相同的文件列，但是两个独立流程。BOM 必须包含：

- `Supplier Part`
- `Comment`
- `Footprint`
- `Quantity`

可选列包括 `Designator`、`Manufacturer`和 `Manufacturer Part`。重复 Supplier Part 会自动合并数量与位号。

立创订单会自动定位包含“商品编号”、“订购数量（修改后）”和“发货数量”的表头行。同一订单编号不能重复导入。

## 备份与测试

“数据管理”页面可直接下载数据库快照或 Excel 文件。恢复数据库时，系统会先在项目根目录的 `backups/` 中保存恢复前快照。

```powershell
python -m pytest -q
```

## 模块边界

- `app/importers/`：只解析文件，不读写数据库。
- `app/services/`：处理匹配、格位、入库、领料等事务规则。
- `app/routes/`：处理 HTTP 和页面输入输出。
- `app/models/`：定义 SQLite 数据结构。
