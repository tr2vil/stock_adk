"""
Risk Agent Tools - 리스크 관리 도구
포지션 사이징, 손절/익절 설정, 포트폴리오 리스크 평가
"""
import yfinance as yf


async def calculate_position_size(
    ticker: str,
    market: str = "US",
    account_balance: float = 10000000,  # 기본 1000만원
    risk_per_trade: float = 0.02,       # 1회 거래당 최대 리스크 2%
) -> dict:
    """켈리 기준 + ATR 기반 포지션 사이징을 계산합니다.

    계좌 잔고와 리스크 허용 범위를 고려하여 최적의 매수 수량을 계산합니다.
    ATR을 사용하여 손절 거리를 산출하고, 이를 기반으로 포지션 크기를 결정합니다.

    Args:
        ticker: 종목코드 (예: "AAPL", "005930.KS")
        market: "US" 또는 "KR"
        account_balance: 계좌 잔고 (기본 1000만원)
        risk_per_trade: 1회 거래당 최대 리스크 비율 (기본 2%)

    Returns:
        dict: 포지션 사이징 결과. position_size, stop_loss_price,
              take_profit_price, risk_level, max_loss_amount 포함.
    """
    try:
        # 티커 심볼 처리
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"

        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")

        if hist.empty:
            return {
                "status": "error",
                "ticker": ticker,
                "market": market,
                "error": f"가격 데이터를 찾을 수 없습니다: {ticker}",
            }

        current_price = float(hist["Close"].iloc[-1])

        # ATR 계산 (14일)
        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = tr1.combine(tr2, max).combine(tr3, max)
        atr = float(tr.rolling(window=14).mean().iloc[-1])

        # 손절 거리 (ATR 2배)
        stop_loss_distance = atr * 2
        stop_loss_price = current_price - stop_loss_distance

        # 익절 거리 (손익비 1.5:1 기준)
        take_profit_distance = stop_loss_distance * 1.5
        take_profit_price = current_price + take_profit_distance

        # 최대 리스크 금액
        max_risk_amount = account_balance * risk_per_trade

        # 포지션 사이즈 계산
        risk_per_share = stop_loss_distance
        position_size = int(max_risk_amount / risk_per_share)

        # 단일 종목 최대 투자비율 20% 제한
        max_single_stock_value = account_balance * 0.20
        max_position_by_value = int(max_single_stock_value / current_price)

        position_size = min(position_size, max_position_by_value)
        position_size = max(1, position_size)  # 최소 1주

        # 실제 투자 금액과 리스크
        investment_amount = position_size * current_price
        max_loss_amount = position_size * stop_loss_distance
        risk_reward_ratio = take_profit_distance / stop_loss_distance

        # 리스크 레벨 판단
        volatility_pct = (atr / current_price) * 100
        if volatility_pct > 5:
            risk_level = "high"
        elif volatility_pct > 2.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "status": "success",
            "ticker": ticker,
            "market": market,
            "current_price": round(current_price, 2),
            "atr_14": round(atr, 2),
            "volatility_pct": round(volatility_pct, 2),
            "position_size": position_size,
            "stop_loss_price": round(stop_loss_price, 2),
            "take_profit_price": round(take_profit_price, 2),
            "investment_amount": round(investment_amount, 2),
            "max_loss_amount": round(max_loss_amount, 2),
            "risk_level": risk_level,
            "risk_reward_ratio": round(risk_reward_ratio, 2),
            "confidence": 0.8 if len(hist) >= 60 else 0.5,
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "market": market,
            "error": str(e),
        }


async def assess_portfolio_risk(
    new_ticker: str,
    market: str = "US",
    current_positions: list[dict] = None,
) -> dict:
    """신규 매매가 포트폴리오에 미치는 리스크를 평가합니다.

    기존 보유 종목과의 상관관계, 섹터 집중도, 전체 포트폴리오 리스크를 분석합니다.

    Args:
        new_ticker: 신규 매수 고려 종목코드
        market: "US" 또는 "KR"
        current_positions: 현재 보유 포지션 리스트
            예: [{"ticker": "AAPL", "quantity": 10, "avg_price": 150.0}, ...]

    Returns:
        dict: 포트폴리오 리스크 평가 결과. risk_level, correlation_risk,
              sector_concentration, max_positions_warning 포함.
    """
    if current_positions is None:
        current_positions = []

    try:
        # 티커 심볼 처리
        if market == "KR" and not new_ticker.endswith((".KS", ".KQ")):
            if new_ticker.isdigit() and len(new_ticker) == 6:
                new_ticker = f"{new_ticker}.KS"

        stock = yf.Ticker(new_ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return {
                "status": "error",
                "ticker": new_ticker,
                "market": market,
                "error": f"종목 정보를 찾을 수 없습니다: {new_ticker}",
            }

        new_sector = info.get("sector", "Unknown")

        # 현재 포지션 수 확인
        current_count = len(current_positions)
        max_positions = 10

        # 동일 섹터 종목 수 계산
        sector_count = 0
        for pos in current_positions:
            try:
                pos_ticker = pos.get("ticker", "")
                pos_stock = yf.Ticker(pos_ticker)
                pos_sector = pos_stock.info.get("sector", "Unknown")
                if pos_sector == new_sector:
                    sector_count += 1
            except Exception:
                continue

        # 섹터 집중도 위험
        sector_concentration = sector_count / max(current_count, 1)

        # 리스크 레벨 판단
        warnings = []

        if current_count >= max_positions:
            risk_level = "high"
            warnings.append(f"최대 보유 종목 수({max_positions}개) 도달")
        elif current_count >= max_positions - 2:
            risk_level = "medium"
            warnings.append(f"보유 종목 수 {current_count}/{max_positions}")
        else:
            risk_level = "low"

        if sector_concentration > 0.4:
            risk_level = "high"
            warnings.append(f"섹터 집중도 높음: {new_sector}에 {sector_count + 1}개 종목")
        elif sector_concentration > 0.25:
            if risk_level != "high":
                risk_level = "medium"
            warnings.append(f"섹터 주의: {new_sector}")

        return {
            "status": "success",
            "ticker": new_ticker,
            "market": market,
            "sector": new_sector,
            "current_positions_count": current_count,
            "max_positions": max_positions,
            "sector_concentration": round(sector_concentration, 2),
            "same_sector_count": sector_count,
            "risk_level": risk_level,
            "warnings": warnings,
            "can_add_position": current_count < max_positions,
            "confidence": 0.7,
        }

    except Exception as e:
        return {
            "status": "error",
            "ticker": new_ticker,
            "market": market,
            "error": str(e),
        }
