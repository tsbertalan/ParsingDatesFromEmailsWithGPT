# https://beta.openai.com/docs/guides/fine-tuning
import json
from pprint import pprint

EMAILTOKEN = '====Email:===='
PARSEDTOKEN = '====Parsed:===='
DATA_SEPARATOR = '######'


def prepare_prompt(email):
    return mangle(email) + EMAILTOKEN[::-1]


def get_stop_tokens():
    return [PARSEDTOKEN[::-1]]

# MANGLINGS = (
#     ('"',  '<QT>'),
#     ('{',  '<CBO>'),
#     ('}',  '<CBC>'),
#     ('\n', '<NL>'),
# )

mangle = demangle = lambda s: s
# def mangle(parsed):
#     return parsed
#     for source, target in MANGLINGS:
#         parsed = parsed.replace(source, target)
#     return parsed
    
# def demangle(parsed):
#     for source, target in MANGLINGS:
#         parsed = parsed.replace(target, source)
#     return parsed


def load_txt(src_path):

    with open (src_path, 'r') as fp:
        prompt_template = fp.read()

    examples = prompt_template.split(DATA_SEPARATOR)

    data = []
    unmodified_data = []
    stop_tokens = get_stop_tokens()
    
    for txt in examples:
        if EMAILTOKEN not in txt and PARSEDTOKEN not in txt:
            raise ValueError('Failed to parse data from example:', txt)
        else:
            iemail1 = txt.index(EMAILTOKEN)+len(EMAILTOKEN)
            iemail2 = txt.index(PARSEDTOKEN)
            iparsed1 = txt.index(PARSEDTOKEN)+len(PARSEDTOKEN)

            email = txt[iemail1:iemail2]
            parsed = txt[iparsed1:]

            datum = {
                'prompt': prepare_prompt(email),
                'completion': ' ' + mangle(parsed) + stop_tokens[0],
            }
            data.append(datum)
            unmodified_data.append(dict(
                email=email,
                parsed=parsed,
            ))
    return data, unmodified_data


def fix_quotes(src_path):
    data, unmodified_data = load_txt(src_path)
    lines = []
    for i, datum in enumerate(unmodified_data):
        fixed_parsed = datum['parsed'].replace("'", '"')
        lines.extend([
            EMAILTOKEN,
            datum['email'],
            PARSEDTOKEN,
            fixed_parsed,
        ])
        if i != len(unmodified_data) - 1:
            lines.append(DATA_SEPARATOR+'\n')

    with open(src_path+'_fixed.txt', 'w') as fp:
        fp.writelines(lines)


def write_jsonl(src_path):
    data, unmodified_data = load_txt(src_path)
    with open(src_path + '.jsonl', 'w') as fp:
      for datum in data:
          fp.write(json.dumps(datum) + '\n')


if __name__ == '__main__':

    if False:
        fix_quotes('/home/tsbertalan/Dropbox/Projects/Parsing Dates from Emails/event_parsing_GPT_dataset.txt')
    else:
        write_jsonl('/home/tsbertalan/Dropbox/Projects/Parsing Dates from Emails/event_parsing_GPT_dataset.txt_fixed.txt')
