from markitdown import MarkItDown
import os
from logzero import logger

class DocManager:
    """
    Manages project documentation and research reports using MarkItDown.
    """
    def __init__(self, research_dir="research", docs_dir="docs"):
        self.md = MarkItDown()
        self.research_dir = research_dir
        self.docs_dir = docs_dir
        
        for d in [self.research_dir, self.docs_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def import_to_markdown(self, file_path):
        """
        Converts a file (PDF, Docx, Excel, etc.) to Markdown and saves it in the research directory.
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
            
            filename = os.path.basename(file_path)
            name_only = os.path.splitext(filename)[0]
            output_path = os.path.join(self.research_dir, f"{name_only}.md")
            
            logger.info(f"Converting {filename} to Markdown...")
            result = self.md.convert(file_path)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
            
            logger.info(f"Saved converted documentation to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error during MarkItDown conversion: {str(e)}")
            return None

    def summarize_instruments(self, json_path="instruments.json"):
        """
        Example usage: summarizing the instruments list (though MarkItDown is better for binary docs, 
        we can show its integration).
        """
        # MarkItDown is not really for JSON, but we could convert an Excel version if it existed.
        pass

if __name__ == "__main__":
    manager = DocManager()
    print("DocManager initialized with MarkItDown.")
