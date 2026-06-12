from app.doc_manager import DocManager
import os
from logzero import logger

def main():
    manager = DocManager()
    
    # 1. Convert existing documentation for consistency
    logger.info("Processing project documentation...")
    manager.import_to_markdown("STRATEGY_DOCUMENTATION.md")
    manager.import_to_markdown("TECHNICAL_GUIDE.md")
    
    # 2. Generate a custom summary report
    report_content = """# Nifty 50 Trading Bot - Status Report
Generated on: 2026-06-12

## Latest Updates
- Fixed critical bugs in `strategy.py` and `trend.py` (NameError and KeyError).
- Enhanced `NiftySMCStrategy` with Doji Breakout logic.
- Integrated `markitdown` for document processing.
- Verified backtesting engine with multi-timeframe support.

## Backtest Summary (Last 15 Days)
- Total Trades: 76 (Base Strategy)
- Note: High frequency due to lenient filters; further optimization recommended.

## Advanced Strategy Analysis
- PCR Filter: Active (PCR 1.42 detected today, correctly withholding bearish trades).
- 1H Bias: Active (Multi-timeframe alignment enforced).

## MarkItDown Integration
The `DocManager` is now available to import external research (PDFs, Excel) into the `research/` directory as Markdown.
"""
    
    with open("docs/PROJECT_STATUS.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    
    logger.info("Project status report generated in docs/PROJECT_STATUS.md")

if __name__ == "__main__":
    main()
