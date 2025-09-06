"""
TMWS Unified Server - Module Entry Point
python -m tmws でのモジュール実行をサポート
"""

if __name__ == "__main__":
    from unified_server import main
    import asyncio
    
    asyncio.run(main())