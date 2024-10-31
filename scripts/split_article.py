#%%
import arxiv
import requests
import os
import json
from PyPDF2 import PdfReader
import re
from pathlib import Path
import fitz  # PyMuPDF

class ArxivPaperProcessor:
    def __init__(self, save_dir='papers'):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
    
    def download_and_parse(self, arxiv_url):
        # Extract paper ID from URL
        paper_id = arxiv_url.split('/')[-1]
        
        # Create directory for this paper
        paper_dir = self.save_dir / paper_id
        paper_dir.mkdir(exist_ok=True)
        
        # Get paper metadata using arxiv API
        search = arxiv.Search(id_list=[paper_id])
        paper = next(search.results())
        
        # Download PDF
        pdf_path = paper_dir / 'paper.pdf'
        paper.download_pdf(filename=str(pdf_path))
        
        # Extract images
        self._extract_images(pdf_path, paper_dir / 'images')
        
        # Parse PDF content
        content = self._parse_pdf(pdf_path)
        
        # Save metadata and content
        metadata = {
            'title': paper.title,
            'authors': [str(author) for author in paper.authors],
            'summary': paper.summary,
            'published': str(paper.published),
            'url': paper.entry_id,
            'sections': content
        }
        
        with open(paper_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            
        return metadata
    
    def _extract_images(self, pdf_path, images_dir):
        images_dir = Path(images_dir)
        images_dir.mkdir(exist_ok=True)
        
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Save image
                image_path = images_dir / f'image_p{page_num + 1}_{img_idx + 1}.{base_image["ext"]}'
                with open(image_path, 'wb') as f:
                    f.write(image_bytes)
    
    def _parse_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        # Define common section headers
        sections = {
            'abstract': '',
            'introduction': '',
            'related work': '',
            'methodology': '',
            'experiments': '',
            'results': '',
            'discussion': '',
            'conclusion': '',
            'references': ''
        }
        
        # Simple section parsing based on common headers
        current_section = None
        for line in full_text.split('\n'):
            line = line.strip().lower()
            
            # Check if line is a section header
            for section in sections.keys():
                if line.startswith(section) or line == section:
                    current_section = section
                    break
            
            # Add content to current section
            if current_section and line:
                sections[current_section] += line + '\n'
        
        return sections
    
    def render_paper(self, paper_id):
        paper_dir = self.save_dir / paper_id
        
        if not paper_dir.exists():
            raise ValueError(f"Paper {paper_id} not found in {self.save_dir}")
        
        with open(paper_dir / 'metadata.json', 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Create a simple HTML representation
        html = f"""
        <html>
        <head>
            <title>{metadata['title']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <h1>{metadata['title']}</h1>
            <p><strong>Authors:</strong> {', '.join(metadata['authors'])}</p>
            <p><strong>Published:</strong> {metadata['published']}</p>
            
            <h2>Abstract</h2>
            <p>{metadata['sections']['abstract']}</p>
        """
        
        # Add other sections
        for section, content in metadata['sections'].items():
            if section != 'abstract' and content.strip():
                html += f"<h2>{section.title()}</h2>\n<p>{content}</p>\n"
        
        # Add images
        images_dir = paper_dir / 'images'
        if images_dir.exists():
            html += "<h2>Figures</h2>\n"
            for image_path in sorted(images_dir.glob('*')):
                html += f'<img src="{image_path}" alt="Figure from paper"><br><br>\n'
        
        html += "</body></html>"
        
        # Save HTML
        with open(paper_dir / 'paper.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        return paper_dir / 'paper.html'

#%%
link = "https://arxiv.org/abs/2410.19730"

processor = ArxivPaperProcessor()
metadata = processor.download_and_parse(link)

html_path = processor.render_paper(link.split('/')[-1])
print(f"Paper rendered to {html_path}")

# %%
