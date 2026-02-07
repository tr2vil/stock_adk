"""
Dashboard - Streamlit 기반 모니터링 대시보드 (Stub)

실행 방법:
    streamlit run monitoring/dashboard.py

TODO: 실제 구현 시 아래 기능 추가
- 포트폴리오 현황
- 거래 내역
- 에이전트 상태
- 실시간 시세
"""
import streamlit as st


def main():
    st.set_page_config(
        page_title="Trading System Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Trading System Dashboard")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["Overview", "Portfolio", "Trades", "Agents", "Settings"],
        )

    if page == "Overview":
        show_overview()
    elif page == "Portfolio":
        show_portfolio()
    elif page == "Trades":
        show_trades()
    elif page == "Agents":
        show_agents()
    elif page == "Settings":
        show_settings()


def show_overview():
    """Overview 페이지"""
    st.header("Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Value", "₩10,000,000", "+2.5%")
    with col2:
        st.metric("Today's P&L", "₩250,000", "+2.5%")
    with col3:
        st.metric("Open Positions", "5")
    with col4:
        st.metric("Today's Trades", "3")

    st.markdown("---")
    st.subheader("Recent Activity")
    st.info("No recent activity to display. (Stub)")


def show_portfolio():
    """Portfolio 페이지"""
    st.header("Portfolio")
    st.info("Portfolio view is not yet implemented. (Stub)")


def show_trades():
    """Trades 페이지"""
    st.header("Trade History")
    st.info("Trade history is not yet implemented. (Stub)")


def show_agents():
    """Agents 페이지"""
    st.header("Agent Status")

    agents = [
        ("News Agent", 8001, "🟢 Running"),
        ("Fundamental Agent", 8002, "🟢 Running"),
        ("Technical Agent", 8003, "🟢 Running"),
        ("Expert Agent", 8004, "🟢 Running"),
        ("Risk Agent", 8005, "🟢 Running"),
        ("Orchestrator", 8000, "🟢 Running"),
    ]

    for name, port, status in agents:
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            st.write(name)
        with col2:
            st.write(f":{port}")
        with col3:
            st.write(status)


def show_settings():
    """Settings 페이지"""
    st.header("Settings")
    st.info("Settings page is not yet implemented. (Stub)")


if __name__ == "__main__":
    main()
