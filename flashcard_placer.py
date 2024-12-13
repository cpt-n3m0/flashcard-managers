import heapq
import os
import re
from collections import defaultdict
import numpy as np
import shutil
import pandas as pd
import sys

import bs4
import markdown
import yaml
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from typing import List

import toc


def get_cards(note_md: str) -> pd.DataFrame:

    note_html = markdown.markdown(note_md)
    soup = BeautifulSoup(note_html, 'html.parser')
    cards = []

    for text in soup.findAll(string=re.compile(r'\^ID\d+')):
        card = text.parent
        text = card.text
        page = re.search(r'page=(\d*)', text)

        # if page is None or not page.group(1).isnumeric():
            # continue

        if page is not None:
            page = int(page.group(1))
        # page_num = int(page

        cards.append({'content': card, 'page': page})

    return pd.DataFrame(cards)




def update_frontmatter(frontmatter: dict, cards: pd.DataFrame) -> str:

    if 'cards' in frontmatter:
        frontmatter['cards'] = len(cards)

    if 'checkpoint' in frontmatter:
        last_page = int(cards.sort_values(by='page').iloc[-1].page)
        frontmatter['checkpoint'] = re.sub(r'page=(\d*)', f'page={last_page}', frontmatter['checkpoint'])
        # frontmatter['checkpoint'] = last_page

    fm_text = "---\n"
    fm_text += yaml.dump(frontmatter, default_flow_style=False)
    fm_text += "---\n"

    return fm_text


def extract_fontmatter(note_md):
    frontmatter = re.match('^---(.*?)^---', note_md, re.MULTILINE | re.DOTALL)

    # if frontmatter is None:
        # return None

    fm_dict = yaml.load(frontmatter.group(1), Loader=yaml.FullLoader)
    note_md = note_md.replace(frontmatter.group(0), '')

    return fm_dict, note_md


def md(soup, **options):
    return MarkdownConverter(**options).convert_soup(soup)





def create_card_toc(headings: pd.DataFrame, heading_cards: dict, separator: str = 'hr')  -> BeautifulSoup:
    card_toc_soup = BeautifulSoup('', 'html.parser')
    headings_with_cards = headings.loc[list(heading_cards.keys())]
    seen_ancestors = set()

    for i, h in headings_with_cards.iterrows():

        heading_ancestry = headings[headings.page <= h.page].drop_duplicates(subset='level', keep='last')['tag'].values

        for parent_heading in heading_ancestry:
            if parent_heading not in seen_ancestors:
                seen_ancestors.add(parent_heading)
                card_toc_soup.append(parent_heading)

        for card in heading_cards[i]:
            card_toc_soup.append(card)
            sep = card_toc_soup.new_tag(separator)
            card_toc_soup.append(sep)

    return card_toc_soup

def get_headings(pdf_path: str) -> pd.DataFrame:

    file_toc = toc.pdf_to_toc(pdf_path)
    toc_html = markdown.markdown(file_toc)
    toc_soup = BeautifulSoup(toc_html, 'html.parser')
    headings = []

    for lvl in [0, 1]:
        headings += toc.get_headings(toc_soup, lvl)
    headings =  pd.DataFrame(headings)
    headings = headings.sort_values(by='page')
    headings['has_cards'] = np.nan

    return headings

def main(vault_path: str, file_path: str, write: bool=True) -> str:
    library_root = os.path.join(vault_path, 'Library')
    file = os.path.join(vault_path, file_path )

    with open(file, 'r') as f:
        note_md = f.read()

    note_md = note_md.replace('\\', '\\\\')
    fms, note_md = extract_fontmatter(note_md)
    cards =  get_cards(note_md)

    reference_pdf = re.match(r'\[\[(.*)\]\]', fms['reference'])

    if reference_pdf is None:
        print('No reference pdf found')
        sys.exit(1)
    ref_pdf_path = os.path.join(library_root, reference_pdf.group(1))

    headings = get_headings(ref_pdf_path)
    heading_cards = defaultdict(list)
    assigned_cards = []

    for i, card in cards.iterrows():
        if card.page is None or pd.isna(card.page):
            continue
        header_id  = headings.page[headings.page < card.page].idxmax()
        heading_cards[header_id].append(card.content)
        headings.loc[header_id].has_cards = True
        assigned_cards.append(i)

    card_toc_soup = create_card_toc(headings, heading_cards)

    unassigned_cards = cards[~cards.index.isin(assigned_cards)]

    if not unassigned_cards.empty:
        trailing_paragraphs_header = card_toc_soup.new_tag('h1')
        trailing_paragraphs_header.string = 'Non-card paragraphs'
        card_toc_soup.append(trailing_paragraphs_header)


        for i, c in unassigned_cards.iterrows():
            card_toc_soup.append(c.content)

    updated_fms = update_frontmatter(fms, cards[cards.index.isin(assigned_cards)])
    result = updated_fms + md(card_toc_soup, heading_style='atx', bullets='dash', escape_underscores=False)


    if write:
        shutil.copy(file, file + '.bak')
        with open(file, 'w') as f:
            f.write(result)

    return result

if __name__ == '__main__':

    # arguments passed from the obsidian plugin (Python scripter)
    vault_path = sys.argv[1]
    file_path = sys.argv[2] 
    main(vault_path, file_path)
