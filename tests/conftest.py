from pathlib import Path

import openpyxl
import pytest
import xlwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app import models  # noqa: F401


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def bom_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample_bom.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "BOM"
    sheet.append(["Supplier Part", "Comment", "Footprint", "Quantity", "Designator"])
    sheet.append(["C1001", "10kΩ", "R0603", 2, "R1,R2"])
    sheet.append(["C1002", "100nF", "C0603", 1, "C1"])
    sheet.append(["C1001", "10kΩ", "R0603", 3, "R3,R4,R5"])
    workbook.save(path)
    return path


@pytest.fixture
def order_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample_order.xls"
    workbook = xlwt.Workbook(encoding="utf-8")
    sheet = workbook.add_sheet("订单详情")
    sheet.write(0, 0, "订单编号：")
    sheet.write(0, 1, "SO-DEMO-001")
    sheet.write(3, 0, "商品明细列表")
    headers = [
        "序号",
        "商品编号",
        "品牌",
        "厂家型号",
        "封装",
        "商品名称",
        "订购数量（修改后）",
        "发货数量",
        "商品单价",
        "商品金额",
    ]
    for column, header in enumerate(headers):
        sheet.write(5, column, header)
    rows = [
        [1, "C1001", "DEMO", "R-10K", "0603", "10kΩ ±1% 编带", "10个", "8个", "￥0.01/个", "￥0.08"],
        [2, "C9999", "DEMO", "C-1U", "0603", "1uF ±10% 16V 编带", "5个", "5个", "￥0.02/个", "￥0.10"],
    ]
    for row_index, row in enumerate(rows, start=6):
        for column, value in enumerate(row):
            sheet.write(row_index, column, value)
    workbook.save(str(path))
    return path
