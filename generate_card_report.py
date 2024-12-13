import json
import os
import re
import urllib.request

import requests

# VAULT = '~/Dochub/obsidian/KnowledgeHub'
HOME = os.environ['HOME']
REPORT_LOCATION = 'Enoch/Learning Center/Flashcards/CardReport.md'
REPORT_PATH = os.path.join(HOME, REPORT_LOCATION) 



def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}


def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode('utf-8')
    response = json.load(urllib.request.urlopen(
        urllib.request.Request('http://127.0.0.1:8765', requestJson)))

    if len(response) != 2:
        raise Exception('response has an unexpected number of fields')

    if 'error' not in response:
        raise Exception('response is missing required error field')

    if 'result' not in response:
        raise Exception('response is missing required result field')

    if response['error'] is not None:
        raise Exception(response['error'])

    return response['result']


deck = 'Maths'


def generate_report():
    flags = ['red', 'orange', 'green', 'blue', 'pink', 'turqoise', 'purple']
    flag_legend = ['Major Flaw', 'Ambiguous', 'Needs Refactoring',
                   'Look into', 'Reevaluate', 'turqoise', 'purple']

    
    md = ""

    card_count = 0

    not_found = []

    for i, flag in enumerate(flags):
        cards = invoke(
            'findCards', query=f'deck:{deck} flag:{i+1} tag:obsidian')

        if len(cards) == 0:
            continue
        md += f"## <span style='color: {flags[i]};'> {flag_legend[i]}</span>\n"

        md += "\n\n"
        cards_info = invoke('cardsInfo', cards=cards)

        for c in cards_info:
            card_text = ""

            if c['modelName'] == 'Cloze':
                card_text = c['fields']['Text']['value']
                card_back = None
            elif c['modelName'] == 'Basic':
                card_text = c['fields']['Front']['value']
                card_back = c['fields']['Back']['value']

            else:
                print('Error: model not supported')

                continue

            card_urls = re.findall('href="(.*?)"', card_text)

            if len(card_urls) == 0:
                print('Error: file not found')

                continue

            file_url = card_urls[-1]
            file_url = file_url.replace('amp;', '&')
            url = urllib.parse.urlparse(file_url)

            try:
                file = urllib.parse.parse_qs(url.query)['filepath'][0]
            except:
                not_found.append((card_text, card_back, c['cardId']))

                continue
            md += f"- [ ] ![[{file}#^ID{c['note']}]]\n"
            note = re.search(r'nts:(.*?)(?:<br>|$)', card_text)

            if note is not None:
                md += f"> [!Remark]\n>{note.group(1)}\n"
            md += '\n---\n'
            card_count += 1

    if len(not_found):
        md += '\n\n# Cards with no associated files\n'

        for front, back, cid in not_found:
            md += f"- [ ]  ID{cid}\n" 



    print(f'{card_count} cards to process')

    return md


def update_flag_status():
    report_path = os.path.expanduser(REPORT_PATH)

    if not os.path.exists(report_path):
        return
    md = open(report_path, 'r').read()
    fixed_cards = re.findall(r'- \[x\] !\[\[.*?#\^ID(\d+)\]\]', md)

    for cid in fixed_cards:
        res = invoke('setSpecificValueOfCard', card=int(
            cid), keys=["flags"], newValues=[0], warning_check=True)
        print(cid, res)

    return fixed_cards


if __name__ == '__main__':

    update_flag_status()
    report = generate_report()
    with open(REPORT_PATH, 'w') as report_file:
        report_file.write(report)
