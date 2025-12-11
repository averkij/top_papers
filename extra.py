import io
import json
import os
import re
from io import BytesIO
from pathlib import Path

import fitz
import numpy as np
import requests
from arxiv import Client, Search
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTTextContainer
from PIL import Image

import api as api_helper
import constants as con
from helper import log

Path(con.PAPER_PDF_DIR).mkdir(parents=True, exist_ok=True)
Path(con.PAPER_JSON_DIR).mkdir(parents=True, exist_ok=True)
Path(con.PAPER_IMG_DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(con.PAPER_PDF_TITLE_IMG).mkdir(parents=True, exist_ok=True)


class ArxivParser:
    def __init__(self, url, delete_pdf=False, recalculate_pdf=False, recalculate_html=False):
        self.section_patterns = [
            r"^(?:\d+\.)*\d+\s+[A-Z]",
            r"^[A-Z][a-zA-Z\s]{2,}$",
        ]
        self.arxiv_id = url.strip("/").split("/")[-1]
        self.arxiv_id_no_version = self.arxiv_id.lower().split("v")[0]
        self.delete_pdf = delete_pdf
        self.recalculate_pdf = recalculate_pdf
        self.recalculate_html = recalculate_html

    def clean_text(self, text):
        text = re.sub(
            r"\d+\s*v\s*o\s*N\s*\d+\s*]\s*I\s*A\s*\.\s*s\s*c\s*\[\s*\d+", "", text
        )
        text = re.sub(r"arXiv:\d+\.\d+v\d+\s*\[\w+\.\w+\]", "", text)
        text = re.sub(r"\f|\d+\s*$", "", text)
        text = re.sub(r"(\w+)-\s*\n(\w+)", lambda m: m.group(1) + m.group(2), text)
        text = re.sub(r"(\w+)-\s+(\w+)", lambda m: m.group(1) + m.group(2), text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+[a-zA-Z]\s+", " ", text)
        text = re.sub(
            r"\(([Ff]ig\.|[Tt]able)\s*\d+\)", lambda m: f" {m.group(0)} ", text
        )
        text = re.sub(r'[^\w\s.,;:?!()\[\]{}"\'`@#$%^&*+=<>/-]', "", text)

        return text.strip()

    def is_section_header(self, text):
        text = text.strip()
        return any(re.match(pattern, text) for pattern in self.section_patterns)

    def get_font_size(self, text_element):
        if not list(text_element):
            return None

        for text_line in text_element:
            for char in text_line:
                if isinstance(char, LTChar):
                    return char.size
        return None

    def download_and_parse_pdf(self):
        #debug

        # if not '2411.07133' in self.arxiv_id_no_version:
        #     print('skip')
        #     return

        pdf_path = os.path.join(con.PAPER_PDF_DIR, f"{self.arxiv_id_no_version}.pdf")
        json_path = os.path.join(con.PAPER_JSON_DIR, f"{self.arxiv_id_no_version}.json")

        pdf_title_img_path = os.path.join(
            con.PAPER_PDF_TITLE_IMG, f"{self.arxiv_id_no_version}.jpg"
        )

        if os.path.exists(json_path) and not self.recalculate_pdf:
            log(f"Extra JSON file exists ({json_path}), skip PDF parsing.")
            return None
        
        client = Client()
        search = Search(id_list=[self.arxiv_id])
        paper = next(client.results(search))

        if not paper:
            log(f"Error. Paper with ID {self.arxiv_id} not found.")
            return
        else:
            log(f"Downloading paper {self.arxiv_id} from {paper.pdf_url}...")

        try:
            if not os.path.exists(pdf_path):
                response = requests.get(paper.pdf_url)
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                pdf_file = BytesIO(response.content)
            else:
                log(f"PDF exists ({pdf_path}), skip download.")
                pdf_file = open(pdf_path, "rb")
        except Exception as e:
            log(f"Error downloading PDF ({paper.pdf_url}). Details: {str(e)}")
            return None
    
        abstract = paper.summary
        abstract = abstract.replace("\n", " ")
        abstract = re.sub(r"\s+", " ", abstract)
        sections = [{"title": "Abstract", "content": abstract}]
        current_section = "Start"
        current_text = []
        font_sizes = {}

        for page_layout in extract_pages(pdf_file):
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text = element.get_text().strip()
                    if text:
                        font_size = self.get_font_size(element)
                        if font_size:
                            font_sizes[font_size] = font_sizes.get(font_size, 0) + 1

        body_font_size = max(font_sizes.items(), key=lambda x: x[1])[0]

        pdf_file.seek(0)

        # Second pass: extract text with section structure
        buffer = []  # Buffer for handling hyphenation across elements

        for page_layout in extract_pages(pdf_file):
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text = element.get_text().strip()
                    if not text:
                        continue

                    font_size = self.get_font_size(element)

                    # Check if this is a potential section header
                    if (
                        font_size
                        and font_size > body_font_size
                        and self.is_section_header(text)
                    ):
                        if buffer:
                            current_text.append(self.clean_text(" ".join(buffer)))
                            buffer = []

                        if current_text:
                            sections.append(
                                {
                                    "title": current_section,
                                    "content": self.clean_text(" ".join(current_text)),
                                }
                            )

                        if not 'Start' in [section['title'] for section in sections]:
                            current_section = 'Start'
                        else:
                            current_section = text

                        current_text = []
                    else:
                        buffer.append(text)

                        if len(buffer) > 5:
                            current_text.append(self.clean_text(" ".join(buffer)))
                            buffer = []

        if buffer:
            current_text.append(self.clean_text(" ".join(buffer)))

        if current_text:
            sections.append(
                {
                    "title": current_section,
                    "content": self.clean_text(" ".join(current_text)),
                }
            )

        parsed_data = {
            "paper_title": paper.title,
            "authors": [author.name for author in paper.authors],
            "sections": sections,
        }

        get_pdf_image(pdf_path, pdf_title_img_path)

        if 'Start' in [section['title'] for section in sections]:
            acc = ""
            start = False
            for section in sections:
                if start and section['title'].lower().strip() == 'abstract':
                    break
                if section['title'] == 'Start':
                    start = True
                if start:
                    acc += section['content'] + " "

            affiliations = get_affiliations(acc[:2000], api="claude", model="claude-haiku-4-5")

            #fallback
            if "error" in affiliations:
                affiliations = get_affiliations(acc[:2000])

            parsed_data['affiliations'] = affiliations
        else:
            log('No Start section detected to extract affiliations.')
            parsed_data['affiliations'] = []

        #Search deeper for affiliations
        aff_limit = 10000
        if not parsed_data['affiliations'] or "error" in parsed_data['affiliations']:
            acc = ""
            rest_len = aff_limit
            for section in sections[1:]:
                if rest_len >= 0:
                    take_text = section["content"][:rest_len]
                    acc += take_text
                    rest_len -= len(acc)
                else:
                    break
            affiliations = get_affiliations(acc[:6500], api='mistral', model='mistral-large-latest')
            if affiliations and not "error" in affiliations:
                parsed_data['affiliations'] = affiliations

        with open(f"{json_path}", "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=4, ensure_ascii=False)

        pdf_file.close()

        if self.delete_pdf:            
            log(f"Deleting PDF {pdf_path}.")
            os.unlink(pdf_path)

    def parse_html(self):
        img_data_path = os.path.join(
            con.PAPER_IMG_DATA_DIR, f"{self.arxiv_id_no_version}.json"
        )
        if os.path.exists(img_data_path) and not self.recalculate_html:
            log(f"Paper image links file exists ({img_data_path}), skip HTML parsing.")
            return
        
        url = f"https://arxiv.org/html/{self.arxiv_id}"
        response = requests.get(url)
        html_content = response.content
        soup = BeautifulSoup(html_content, "html.parser")

        headers = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]
        header_positions = [h2.sourceline for h2 in soup.find_all("h2")]

        result = [{"header": "Abstract", "images": []}] + [
            {"header": header, "images": []} for header in headers
        ]

        figures = []
        for fig in soup.find_all("figure"):
            img = fig.find("img")
            figcaption = fig.find("figcaption")
            if img:
                img_src = img["src"]
                item = {
                    "img": img_src,
                    "caption": "",
                    "position": fig.sourceline,
                }
                if figcaption:
                    item["caption"] = figcaption.get_text(strip=True)
                figures.append(item)

        for img in soup.find_all("img", class_="ltx_graphics"):
            existed_figures = [figure["img"] for figure in figures]
            if img and not img["src"] in existed_figures:
                img_src = img["src"]
                figures.append(
                    {
                        "img": img_src,
                        "caption": "",
                        "position": img.sourceline,
                    }
                )

        figures = sorted(figures, key=lambda x: x["position"])

        current_header_index = 0
        for figure in figures:
            while (
                current_header_index < len(header_positions) - 1
                and figure["position"] > header_positions[current_header_index]
            ):
                current_header_index += 1
            result[current_header_index]["images"].append(
                {
                    "img": f"https://arxiv.org/html/{self.arxiv_id}/{figure['img']}",
                    "caption": figure["caption"],
                    "position": figure["position"],
                }
            )

        json.dump(
            result,
            open(img_data_path, "w", encoding="utf8"),
            indent=4,
            ensure_ascii=False,
        )


def get_pdf_image(pdf_path, output_path, zoom=2, crop_percent=30, threshold=250):
    try:
        pdf_document = fitz.open(pdf_path)
        first_page = pdf_document[0]
        mat = fitz.Matrix(zoom, zoom)
        pix = first_page.get_pixmap(matrix=mat)

        samples_per_pixel = 3 if pix.n == 3 else 4
        img_array = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_array.reshape(pix.height, pix.width, samples_per_pixel)
        
        if samples_per_pixel == 4:
            grayscale = np.mean(img_array[:, :, :3], axis=2)
        else:
            grayscale = np.mean(img_array, axis=2)
        
        non_white_cols = np.where(np.min(grayscale, axis=0) < threshold)[0]
        if len(non_white_cols) > 0:
            # first_content_col = int(non_white_cols[0])
            last_content_col = int(non_white_cols[-1])
        else:
            # first_content_col = 0
            last_content_col = pix.width - 1

        non_white_rows = np.where(np.min(grayscale, axis=1) < threshold)[0]
        if len(non_white_rows) > 0:
            first_content_row = non_white_rows[0]
        else:
            first_content_row = 0
            
        content_height = pix.height - first_content_row
        
        if crop_percent > 5:
            crop_percent = max(0, min(100, crop_percent))
            keep_height = int((crop_percent / 100) * content_height)
        else:
            keep_height = content_height
            
        x0 = int(pix.width - min(pix.width, last_content_col + 20))
        y0 = int(max(0,first_content_row-20))
        x1 = int(min(pix.width, last_content_col + 20))
        y1 = int(first_content_row + keep_height)
        
        irect = fitz.IRect(x0, y0, x1, y1)
        cropped_pix = fitz.Pixmap(pix.colorspace, irect, False)
        cropped_pix.copy(pix, irect)

        img_data = cropped_pix.tobytes("png")
        pil_image = Image.open(io.BytesIO(img_data))

        # pil_image = pil_image.convert("RGBA")

        # bg = Image.new("RGBA", pil_image.size, (255, 255, 255, 0))
        # bg.paste(pil_image, (0, 0), pil_image)

        #transparent bg
        
        # pixdata = pil_image.load()
        # width, height = pil_image.size
        # for y in range(height):
        #     for x in range(width):
        #         if pixdata[x, y] == (255, 255, 255, 255):
        #             pixdata[x, y] = (255, 255, 255, 0)
        pil_image.save(output_path, "JPEG", quality=65)

        pdf_document.close()
        
        return output_path
        
    except Exception as e:
        log(f"Error generating title image for PDF (pdf_path): {str(e)}")
        return None
    
def get_affiliations(text, api='mistral', model='open-mistral-nemo'):
    log("Extracting affiliations from text.")
    prompt = f"I give you a contaminated text with start of ML paper. Extract all authors affiliations as a single institute, firm, company, etc. Return items as a Python plain list only with affiliations. Do not provide commentaries. If there are no affiliations return empty list.\n\nText:\"{text}\""

    res = api_helper.get_json(
        prompt, api=api, model=model, temperature=0.0
    )

    if isinstance(res, list):
        res = sorted(list(set(res)))

    return res