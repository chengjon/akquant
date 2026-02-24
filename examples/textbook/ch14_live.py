"""
第 11 章：实盘交易系统 (Live Trading).

本示例展示了如何将策略部署到实盘环境。
AKQuant 支持通过 CTP 接口连接期货公司柜台，实现行情接收和自动交易。

注意：
1. 实盘交易涉及真实资金，请务必在模拟盘 (SimNow) 充分测试。
2. 本代码仅为配置演示，无法直接运行，因为需要有效的 CTP 账户信息。
3. 你需要安装 CTP 驱动 (通常只支持 Linux/Windows)。

配置流程：
1. 准备 CTP 账户 (BrokerID, UserID, Password, AuthCode, AppID)。
2. 获取前置机地址 (MD Front, TD Front)。
3. 配置 LiveRunner 并启动。
"""

import akquant as aq
from akquant import Bar, Instrument, Strategy
from akquant.live import LiveRunner  # 导入实盘运行器


# 定义一个简单的策略 (与回测完全一致)
class LiveDemoStrategy(Strategy):
    """实盘演示策略."""

    def on_bar(self, bar: Bar) -> None:
        """收到 Bar 事件的回调."""
        self.log(f"[Live] Received Bar: {bar.symbol} @ {bar.close}")

        # 简单的双均线逻辑
        closes = self.get_history(20, bar.symbol, "close")
        if len(closes) < 20:
            return

        ma5 = closes[-5:].mean()
        ma20 = closes[-20:].mean()

        pos = self.get_position(bar.symbol)

        if ma5 > ma20 and pos == 0:
            self.log("金叉 -> 买入开仓")
            self.buy(bar.symbol, 1)
        elif ma5 < ma20 and pos > 0:
            self.log("死叉 -> 卖出平仓")
            self.close_position(bar.symbol)


if __name__ == "__main__":
    print("正在配置实盘环境...")

    # 1. 定义交易标的
    # 实盘中，合约乘数等信息通常可以从柜台自动查询，但显式配置更安全
    rb2310 = Instrument(
        symbol="rb2310",
        asset_type=aq.AssetType.Futures,
        multiplier=10,
        margin_ratio=0.1,
    )

    # 2. CTP 账户配置 (请替换为你的真实账户或 SimNow 模拟账户)
    CTP_CONFIG = {
        "md_front": "tcp://180.168.146.187:10131",  # SimNow 行情前置
        "td_front": "tcp://180.168.146.187:10130",  # SimNow 交易前置
        "broker_id": "9999",
        "user_id": "YOUR_USER_ID",
        "password": "YOUR_PASSWORD",
        "app_id": "simnow_client_test",
        "auth_code": "0000000000000000",
    }

    # 3. 创建实盘运行器
    try:
        runner = LiveRunner(
            strategy_cls=LiveDemoStrategy,
            instruments=[rb2310],
            md_front=CTP_CONFIG["md_front"],
            td_front=CTP_CONFIG["td_front"],
            broker_id=CTP_CONFIG["broker_id"],
            user_id=CTP_CONFIG["user_id"],
            password=CTP_CONFIG["password"],
            app_id=CTP_CONFIG["app_id"],
            auth_code=CTP_CONFIG["auth_code"],
        )

        # 4. 启动实盘
        # run() 会阻塞主线程，直到手动停止 (Ctrl+C)
        print("启动 CTP 接口...")
        runner.run(cash=500_000)

    except ImportError:
        print(
            "错误: 未找到 CTP 接口库。请确保已安装 akquant[ctp] 或手动配置 "
            "thosttraderapi。"
        )
    except Exception as e:
        print(f"实盘启动失败: {e}")
