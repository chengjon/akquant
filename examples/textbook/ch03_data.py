"""
第 2 章：金融数据获取与处理.

本示例演示了量化交易中数据工程的核心步骤：
1. 获取数据：从 AKShare 获取 A 股历史日线数据
2. 数据清洗：将原始数据转换为 AKQuant 所需的标准格式
3. 数据存储：将清洗后的数据保存为高性能的 Parquet 格式
4. 数据读取：从本地加载数据进行验证

这些步骤是构建任何量化策略的基石。
"""

import os
from pathlib import Path

import akshare as ak
import pandas as pd


def fetch_and_clean_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取 A 股日线数据并清洗为 AKQuant 标准格式.

    :param symbol: 股票代码 (如 "600000")
    :param start_date: 开始日期 (如 "20230101")
    :param end_date: 结束日期 (如 "20231231")
    :return: 清洗后的 DataFrame
    """
    print(f"正在获取 {symbol} 的历史数据 ({start_date}-{end_date})...")

    # 1. 获取数据
    # 使用 stock_zh_a_hist 接口获取历史行情
    # adjust="qfq" 表示前复权，这是回测中最常用的复权方式
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception as e:
        print(f"数据获取失败: {e}")
        return pd.DataFrame()

    if df.empty:
        print("警告: 获取到的数据为空")
        from typing import cast

        return cast(pd.DataFrame, df)

    # 2. 重命名列 (AKShare 中文列名 -> AKQuant 标准英文列名)
    # 标准列名: date, open, high, low, close, volume
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    df = df.rename(columns=rename_map)

    # 3. 格式转换与清洗
    # 转换日期列为 pandas datetime 类型
    df["date"] = pd.to_datetime(df["date"])

    # 筛选必要的列，去除多余字段 (如涨跌幅、换手率等，除非策略需要)
    required_cols = ["date", "open", "high", "low", "close", "volume"]
    df = df[required_cols]

    # 添加 symbol 列 (多标的回测时必需)
    df["symbol"] = symbol

    # 处理缺失值 (简单的丢弃策略)
    df = df.dropna()

    # 按日期升序排序
    df = df.sort_values("date").reset_index(drop=True)

    print(f"数据清洗完成，共 {len(df)} 条记录")
    return df  # type: ignore


def save_to_parquet(df: pd.DataFrame, file_path: str) -> None:
    """
    将 DataFrame 保存为 Parquet 格式.

    Parquet 是一种高性能列式存储格式，读写速度远快于 CSV。
    """
    # 确保父目录存在
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(file_path)
    print(f"数据已保存至: {file_path}")


def load_from_parquet(file_path: str) -> pd.DataFrame:
    """从 Parquet 文件读取数据."""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return pd.DataFrame()

    df = pd.read_parquet(file_path)
    print(f"从本地加载数据成功，共 {len(df)} 条记录")
    return df


if __name__ == "__main__":
    # 配置参数
    SYMBOL = "600000"  # 浦发银行
    START_DATE = "20230101"
    END_DATE = "20231231"
    DATA_DIR = "data"  # 数据存储目录

    # 1. 获取并清洗数据
    df_clean = fetch_and_clean_data(SYMBOL, START_DATE, END_DATE)

    if not df_clean.empty:
        # 打印前 5 行预览
        print("\n数据预览 (Head):")
        print(df_clean.head())

        # 打印数据类型信息
        print("\n数据信息 (Info):")
        df_clean.info()

        # 2. 保存数据
        file_path = f"{DATA_DIR}/{SYMBOL}.parquet"
        save_to_parquet(df_clean, file_path)

        # 3. 验证读取
        print("\n正在验证读取...")
        df_loaded = load_from_parquet(file_path)

        # 简单验证
        assert len(df_clean) == len(df_loaded)
        print("验证通过：读取的数据与原始数据一致")
